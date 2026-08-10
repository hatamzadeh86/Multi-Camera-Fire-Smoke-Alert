import cv2
import time
import json
from datetime import datetime
from pathlib import Path
from collections import deque
from ultralytics import YOLO
import numpy as np
from typing import List, Dict, Optional, Tuple
import threading
import queue
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from notifier import Notifier
from database import DatabaseManager

class FireAlertSystem:
    def __init__(self, config: dict, camera_id: int = 0, source: str = None, alert_queue: queue.Queue = None):
        self.config = config
        self.camera_id = camera_id
        self.source = source or config.get('source', 0)
        self.alert_queue = alert_queue or queue.Queue()
        
        # بارگذاری مدل‌ها
        print(f"📥 [Camera {camera_id}] بارگذاری مدل آتش/دود...")
        self.fire_model = YOLO(config['fire_model'])
        print(f"📥 [Camera {camera_id}] بارگذاری مدل انسان...")
        self.person_model = YOLO(config['person_model'])
        
        # تنظیمات تلگرام (برای ارسال مستقیم)
        self.telegram_token = config.get('telegram_token')
        self.telegram_chat_id = config.get('telegram_chat_id')
        
        # آستانه‌ها
        self.distance_threshold = config.get('distance_threshold', 150)
        self.fire_frames_threshold = config.get('fire_frames_threshold', 3)
        self.cooldown_seconds = config.get('cooldown_seconds', 15)
        self.conf_fire = config.get('conf_fire', 0.5)
        self.conf_person = config.get('conf_person', 0.5)
        
        # تاریخچه‌ها
        self.fire_history = deque(maxlen=self.fire_frames_threshold)
        self.proximity_history = {}
        self.last_alert_time = 0
        self.alerted_pairs = {}
        
        # شناسه جلسه و پوشه ذخیره
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.capture_dir = Path(f"captures/camera_{camera_id}")
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        
        # وضعیت اجرا
        self.running = False
        self.frame_count = 0
        
        print(f"✅ [Camera {camera_id}] سیستم هشدار راه‌اندازی شد.")
        print(f"📸 عکس‌ها در: {self.capture_dir}")
        print(f"📏 آستانه فاصله: {self.distance_threshold} پیکسل")
    
    def process_frame(self, frame: np.ndarray) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """پردازش یک فریم و تولید هشدارها"""
        try:
            current_time = time.time()
            alerts = []
            
            # تشخیص‌ها
            person_results = self.person_model.track(
                frame, conf=self.conf_person, classes=[0],
                persist=True, verbose=False
            )
            persons = self._extract_detections(person_results)
            
            fire_results = self.fire_model.track(
                frame, conf=self.conf_fire,
                persist=True, verbose=False
            )
            all_fires = self._extract_detections(fire_results)
            fires = [f for f in all_fires if f['class_name'] == 'fire' and f['confidence'] >= self.conf_fire]
            persons = [p for p in persons if p['confidence'] >= self.conf_person]
            
            # ---------- هشدار آتش (تداوم) ----------
            if self._check_fire_persistence(fires):
                if current_time - self.last_alert_time > self.cooldown_seconds:
                    alert_type = "FIRE_DETECTED"
                    caption = self._build_caption(alert_type, {'fires': fires})
                    img_path = self._save_alert_frame(frame, alert_type)
                    alerts.append({
                        'type': alert_type,
                        'caption': caption,
                        'image_path': img_path,
                        'frame': self.frame_count,
                        'camera_id': self.camera_id,
                        'timestamp': datetime.now().isoformat(),
                        'severity': 'HIGH',
                        'details': {'fires': len(fires)}
                    })
                    self.last_alert_time = current_time
            
            # ---------- هشدار نزدیکی انسان به آتش ----------
            current_proximity = {}
            for person in persons:
                p_id = person.get('track_id', -1)
                if p_id == -1:
                    continue
                p_center = get_bbox_center(person['bbox'])
                for fire in fires:
                    f_id = fire.get('track_id', -1)
                    if f_id == -1:
                        continue
                    f_center = get_bbox_center(fire['bbox'])
                    distance = calculate_distance(p_center, f_center)
                    iou = calculate_iou(person['bbox'], fire['bbox'])
                    
                    # هشدار فوری
                    if distance < self.distance_threshold / 2 or iou > 0.1:
                        pair_key = f"{p_id}_{f_id}"
                        if current_time - self.alerted_pairs.get(pair_key, 0) > self.cooldown_seconds:
                            alert_type = "PERSON_NEAR_FIRE_URGENT"
                            caption = self._build_caption(alert_type, {
                                'person': person,
                                'fire': fire,
                                'distance': distance
                            })
                            img_path = self._save_alert_frame(frame, alert_type)
                            alerts.append({
                                'type': alert_type,
                                'caption': caption,
                                'image_path': img_path,
                                'frame': self.frame_count,
                                'camera_id': self.camera_id,
                                'timestamp': datetime.now().isoformat(),
                                'severity': 'URGENT',
                                'details': {'person_id': p_id, 'fire_id': f_id, 'distance': distance}
                            })
                            self.alerted_pairs[pair_key] = current_time
                            self.last_alert_time = current_time
                            continue
                    
                    # منطق عادی (تأیید چند فریم)
                    is_near = (distance < self.distance_threshold or iou > 0.05)
                    pair_key = f"{p_id}_{f_id}"
                    current_proximity[pair_key] = is_near
                    if pair_key not in self.proximity_history:
                        self.proximity_history[pair_key] = deque(maxlen=self.fire_frames_threshold)
                    self.proximity_history[pair_key].append(is_near)
            
            # بررسی تاریخچه برای هشدارهای عادی
            for key, history in self.proximity_history.items():
                if len(history) < self.fire_frames_threshold:
                    continue
                near_count = sum(1 for status in history if status)
                if near_count >= int(self.fire_frames_threshold * 0.7):
                    p_id, f_id = map(int, key.split('_'))
                    if current_time - self.alerted_pairs.get(key, 0) > self.cooldown_seconds:
                        person = next((p for p in persons if p.get('track_id', -1) == p_id), None)
                        fire = next((f for f in fires if f.get('track_id', -1) == f_id), None)
                        if person and fire:
                            alert_type = "PERSON_NEAR_FIRE"
                            caption = self._build_caption(alert_type, {
                                'person': person,
                                'fire': fire,
                                'near_count': near_count
                            })
                            img_path = self._save_alert_frame(frame, alert_type)
                            alerts.append({
                                'type': alert_type,
                                'caption': caption,
                                'image_path': img_path,
                                'frame': self.frame_count,
                                'camera_id': self.camera_id,
                                'timestamp': datetime.now().isoformat(),
                                'severity': 'HIGH',
                                'details': {'person_id': p_id, 'fire_id': f_id, 'near_count': near_count}
                            })
                            self.alerted_pairs[key] = current_time
                            self.last_alert_time = current_time
            
            # حذف جفت‌های منقضی‌شده
            for key in list(self.proximity_history.keys()):
                if key not in current_proximity:
                    del self.proximity_history[key]
            
            return alerts, persons, fires
        
        except Exception as e:
            print(f"❌ [Camera {self.camera_id}] خطا در پردازش فریم: {e}")
            return [], [], []
    
    def _extract_detections(self, results):
        """استخراج اطلاعات تشخیص از خروجی YOLO"""
        detections = []
        if not results or len(results) == 0:
            return detections
        boxes = results[0].boxes
        if boxes is None:
            return detections
        track_ids = None
        if boxes.id is not None:
            track_ids = boxes.id.cpu().numpy().astype(int)
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf[0])
            class_id = int(box.cls[0])
            class_name = results[0].names[class_id]
            detection = {'class_name': class_name, 'class_id': class_id,
                        'confidence': confidence, 'bbox': [x1, y1, x2, y2]}
            if track_ids is not None and i < len(track_ids):
                detection['track_id'] = int(track_ids[i])
            else:
                detection['track_id'] = -1
            detections.append(detection)
        return detections
    
    def _check_fire_persistence(self, fires: List[Dict]) -> bool:
        has_fire = len(fires) > 0
        self.fire_history.append(has_fire)
        if len(self.fire_history) < self.fire_frames_threshold:
            return False
        fire_count = sum(1 for f in self.fire_history if f)
        return fire_count >= int(self.fire_frames_threshold * 0.7)
    
    def _save_alert_frame(self, frame: np.ndarray, alert_type: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"alert_{alert_type}_{timestamp}.jpg"
        filepath = self.capture_dir / filename
        annotated = frame.copy()
        cv2.rectangle(annotated, (10, 10), (600, 80), (0, 0, 0), -1)
        cv2.putText(annotated, f"🚨 {alert_type}", (20, 45),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.putText(annotated, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", (20, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imwrite(str(filepath), annotated)
        return str(filepath)
    
    def _build_caption(self, alert_type: str, details: dict) -> str:
        """ساخت متن هشدار"""
        if alert_type == "FIRE_DETECTED":
            return (f"🔥 <b>هشدار آتش‌سوزی!</b>\n"
                    f"⏱️ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📹 دوربین: {self.camera_id}\n"
                    f"⚠️ سطح خطر: <b>بالا</b>")
        elif alert_type == "PERSON_NEAR_FIRE_URGENT":
            return (f"🚨 <b>هشدار فوری! فرد در نزدیکی بسیار خطرناک آتش!</b>\n"
                    f"⏱️ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"👤 شخص ID: {details.get('person', {}).get('track_id', '?')}\n"
                    f"📏 فاصله: {details.get('distance', 0):.0f} پیکسل\n"
                    f"⚠️ سطح خطر: <b>فوری</b>")
        else:
            return f"🚨 {alert_type} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

def get_bbox_center(bbox):
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

def calculate_distance(center1, center2):
    return np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)

def calculate_iou(bbox1, bbox2):
    x1 = max(bbox1[0], bbox2[0]); y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2]); y2 = min(bbox1[3], bbox2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0

