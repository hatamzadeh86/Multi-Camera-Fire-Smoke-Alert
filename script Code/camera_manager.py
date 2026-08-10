# camera_manager.py
import cv2
import threading
import queue
import time
from typing import List, Dict, Optional
from pathlib import Path

class CameraThread(threading.Thread):
    """هر دوربین در یک ترد مجزا اجرا میشه"""
    def __init__(self, camera_id: int, source: str, alert_queue: queue.Queue, config: dict, detector_class):
        super().__init__()
        self.finished = False
        self.camera_id = camera_id
        self.source = source
        self.alert_queue = alert_queue
        self.config = config
        self.detector_class = detector_class
        self.detector = None
        self.running = False
        self.daemon = True
        self.frame_count = 0
        self.out_writer = None
        self.current_frame = None
        
        # زمان شروع برای نامگذاری فایل
        self.start_time = time.strftime("%Y%m%d_%H%M%S")
        
        # پوشه خروجی
        self.output_dir = Path("outputs")
        self.output_dir.mkdir(exist_ok=True)

    def run(self):
        """حلقه اصلی پردازش دوربین"""
        self.running = True
        
        print(f"📹 [Camera {self.camera_id}] شروع به کار روی منبع: {self.source}")
        
        # راه‌اندازی دیتکتور برای این دوربین
        self.detector = self.detector_class(
            
            config=self.config,
            camera_id=self.camera_id,
            source=self.source,
            alert_queue=self.alert_queue
        )
        
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            print(f"❌ [Camera {self.camera_id}] خطا در باز کردن منبع: {self.source}")
            self.running = False
            return
        
        # تنظیمات ویدیو
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cv2.namedWindow(f"Camera {self.camera_id}", cv2.WINDOW_NORMAL)
        cv2.resizeWindow(f"Camera {self.camera_id}", 1280, 720)  # یا هر سایز دیگه‌ای
        
        # ذخیره ویدیو (اگر فعال باشه)
        if self.config.get('save_video', True):
            video_filename = self.output_dir / f"camera_{self.camera_id}_{self.start_time}.mp4"
            self.out_writer = cv2.VideoWriter(
                str(video_filename),
                cv2.VideoWriter_fourcc(*'mp4v'),
                fps, (width, height)
            )
            print(f"💾 [Camera {self.camera_id}] ذخیره ویدیو در: {video_filename}")
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                print(f"⚠️ [Camera {self.camera_id}] پایان ویدیو یا خطا در خواندن فریم")
                self.finished = True
                break
            # بعد از ساخت annotated
            print(f"🔍 [DEBUG] دوربین {self.camera_id} - annotated ساخته شد، در حال ست کردن current_frame")

            
            
            self.frame_count += 1
            self.detector.frame_count = self.frame_count
            
            # پردازش فریم
            alerts, persons, fires = self.detector.process_frame(frame)
            
            # اضافه کردن هشدارها به صف مرکزی
            for alert in alerts:
                if 'image_path' in alert:
                    alert['image_path'] = str(alert['image_path'])
                alert['camera_id'] = self.camera_id
                alert['source'] = self.source
                alert['frame_number'] = self.frame_count
                self.alert_queue.put(alert)

            annotated = None
            try :

            # Annotation و ذخیره ویدیو
                annotated = self._annotate_frame(frame, persons, fires, alerts)
            except :
                print(f"❌ [Camera {self.camera_id}] خطا در annotation: {e}")
                annotated = frame

            self.current_frame = annotated

            
            if self.out_writer:
                self.out_writer.write(annotated)
            
            # نمایش (اختیاری)
            if self.config.get('show_preview', False):
                cv2.imshow(f"Camera {self.camera_id}", annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.running = False
                    break
        
        cap.release()
        if self.out_writer:
            self.out_writer.release()
        print(f"🛑 [Camera {self.camera_id}] متوقف شد. کل فریم‌ها: {self.frame_count}")
    
    def _annotate_frame(self, frame, persons, fires, alerts):
        """رسم annotation روی فریم"""
        annotated = frame.copy()
        
        # رسم انسان‌ها
        for p in persons:
            x1, y1, x2, y2 = map(int, p['bbox'])
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)
            label = f"P{p.get('track_id', '?')} {p['confidence']:.2f}"
            cv2.putText(annotated, label, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        # رسم آتش/دود
        for f in fires:
            x1, y1, x2, y2 = map(int, f['bbox'])
            color = (0, 0, 255) if f['class_name'] == 'fire' else (128, 128, 128)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"F{f.get('track_id', '?')} {f['confidence']:.2f}"
            cv2.putText(annotated, label, (x1, y1-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # نمایش هشدارها
        if alerts:
            cv2.rectangle(annotated, (10, 10), (500, 60), (0, 0, 0), -1)
            cv2.putText(annotated, f"🚨 {len(alerts)} ALERT(S)!", (20, 45),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        
        # اطلاعات فریم
        h, w = annotated.shape[:2]
        cv2.putText(annotated, f"Cam:{self.camera_id} Frame:{self.frame_count}", 
                   (w-200, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return annotated
    
    def stop(self):
        self.running = False


class CameraManager:
    """مدیریت چندین دوربین همزمان"""
    def __init__(self, cameras: List[Dict], config: dict, detector_class):
        """
        cameras: لیست دوربین‌ها
        [
            {'id': 1, 'source': 0},
            {'id': 2, 'source': 'rtsp://...'},
            {'id': 3, 'source': 'video.mp4'}
        ]
        """
        self.cameras = cameras
        self.config = config
        self.detector_class = detector_class
        self.alert_queue = queue.Queue()
        self.threads = []
        self.running = False
        
        # خروجی JSON لاگ
        self.log_path = Path("alerts_log.jsonl")
        self.alert_log = []
        self.total_alerts = 0

    def _start_camera(self, camera_id: int, source: str):
        """راه‌اندازی یک دوربین جدید (برای API)"""
        thread = CameraThread(
            camera_id=camera_id,
            source=source,
            alert_queue=self.alert_queue,
            config=self.config,
            detector_class=self.detector_class
        )
        thread.start()
        self.threads.append(thread)
        return thread
    
    def start_all(self):
        """شروع همه دوربین‌ها"""
        self.running = True
        for cam in self.cameras:
            thread = CameraThread(
                camera_id=cam['id'],
                source=cam['source'],
                alert_queue=self.alert_queue,
                config=self.config,
                detector_class=self.detector_class
            )
            thread.start()
            self.threads.append(thread)
        
        # ترد جمع‌آوری هشدارها
        collector = threading.Thread(target=self._collect_alerts, daemon=True)
        collector.start()
        
        print(f"✅ {len(self.threads)} دوربین راه‌اندازی شد.")
        return self.threads
    
    def _collect_alerts(self):
        """جمع‌آوری هشدارها از صف و ذخیره در JSON"""
        while self.running:
            try:
                alert = self.alert_queue.get(timeout=1)
                self.total_alerts += 1
                alert['alert_id'] = self.total_alerts
                self.alert_log.append(alert)
                
                # ذخیره در فایل JSONL
                import json
                with open(self.log_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(alert, ensure_ascii=False) + '\n')
                
                print(f"📨 [ALERT #{self.total_alerts}] {alert['type']} از دوربین {alert.get('camera_id')}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ خطا در جمع‌آوری هشدار: {e}")
    
    def stop_all(self):
        """توقف همه دوربین‌ها"""
        self.running = False
        for thread in self.threads:
            thread.stop()
            thread.join(timeout=3)
        print(f"🛑 همه دوربین‌ها متوقف شدند. کل هشدارها: {self.total_alerts}")
    
    def get_alerts(self, limit=100):
        """دریافت آخرین هشدارها"""
        return self.alert_log[-limit:]
    
    def get_status(self):
        """وضعیت همه دوربین‌ها"""
        status = []
        for thread in self.threads:
            status.append({
                'camera_id': thread.camera_id,
                'source': thread.source,
                'is_alive': thread.is_alive(),
                'finished':thread.finished,
                'frame_count': thread.frame_count,
                'running': thread.running
            })
        return status