import cv2
import asyncio
import json
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import uvicorn

from camera_manager import CameraManager
from detector import FireAlertSystem
from database import DatabaseManager

# ============================================
# ۱. تنظیمات اولیه
# ============================================
CONFIG = {
    'fire_model':r"C:\Users\E-PART.iR\Desktop\system_fire\best.onnx" ,  # یا best.engine
    'person_model': "yolov8n.pt",
    'distance_threshold': 150,
    'fire_frames_threshold': 3,
    'cooldown_seconds': 20,
    'conf_fire': 0.5,
    'conf_person': 0.4,
}

# ============================================
# ۲. مدیر دوربین‌ها (همون کلاس قبلی)
# ============================================
camera_manager = CameraManager(
    cameras=[],  # ابتدا خالی، از طریق API اضافه میشن
    config=CONFIG,
    detector_class=FireAlertSystem
)

app = FastAPI()

# ============================================
# ۳. مدل داده برای اضافه کردن دوربین
# ============================================
class CameraInput(BaseModel):
    source: str
    name: Optional[str] = "دوربین"

# ============================================
# ۴. استریم ویدیو برای هر دوربین
# ============================================
import time  # اول فایل مطمئن شو که import time رو داری

def generate_frames(camera_id: int):
    """استریم MJPEG از یک دوربین خاص"""
    print(f"🔄 [STREAM] شروع استریم برای دوربین {camera_id}")
    while True:
        found = False
        for thread in camera_manager.threads:
            if thread.camera_id == camera_id:
                found = True
                if hasattr(thread, 'current_frame') and thread.current_frame is not None:
                    ret, jpeg = cv2.imencode('.jpg', thread.current_frame)
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               jpeg.tobytes() + b'\r\n\r\n')
                else:
                    # اگر فریمی هنوز نیومده، یه پیام ساده بفرست
                    # (اینجا می‌تونیم یه تصویر سیاه با متن بفرستیم)
                    pass
                break
        
        if not found:
            print(f"⚠️ [STREAM] دوربین {camera_id} پیدا نشد!")
            break
        
        time.sleep(0.03)  # ← اینجا رو عوض کن (قبلاً asyncio.sleep بود)

@app.get("/video_feed/{camera_id}")
async def video_feed(camera_id: int):
    return StreamingResponse(
        generate_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# ============================================
# ۵. API برای مدیریت دوربین‌ها
# ============================================
@app.post("/add_camera")
async def add_camera(cam: CameraInput):
    """اضافه کردن دوربین جدید"""

    max_id = 0
    for thread in camera_manager.threads:
        if thread.camera_id > max_id:
            max_id = thread.camera_id
    new_id = max_id + 1

    thread = camera_manager._start_camera(new_id, cam.source)
    print(f"✅ دوربین {new_id} اضافه شد. وضعیت: {thread.is_alive()}")
    if thread:
        return {"status": "ok", "camera_id": new_id, "source": cam.source}
    else:
        raise HTTPException(status_code=400, detail="خطا در راه‌اندازی دوربین")

@app.get("/cameras")
async def get_cameras():
    """لیست دوربین‌های فعال"""
    return [{
        'id': t.camera_id,
        'source': t.source,
        'is_alive': t.is_alive(),
        'frame_count': t.frame_count
    } for t in camera_manager.threads]

@app.delete("/remove_camera/{camera_id}")
async def remove_camera(camera_id: int):
    """حذف یک دوربین"""
    for thread in camera_manager.threads:
        if thread.camera_id == camera_id:
            thread.stop()
            camera_manager.threads.remove(thread)
            return {"status": "ok", "message": f"دوربین {camera_id} حذف شد"}
    raise HTTPException(status_code=404, detail="دوربین پیدا نشد")

# ============================================
# ۶. API برای هشدارها و تنظیمات
# ============================================
@app.get("/alerts")
async def get_alerts(limit: int = 20):
    db = DatabaseManager("alerts.db")
    alerts = db.get_alerts(limit=limit)
    db.close()
    return alerts

@app.get("/config")
async def get_config():
    return CONFIG

@app.post("/config")
async def update_config(new_config: dict):
    for key, value in new_config.items():
        if key in CONFIG:
            CONFIG[key] = value
    # به‌روزرسانی در تردها
    for thread in camera_manager.threads:
        if hasattr(thread, 'detector'):
            thread.detector.distance_threshold = CONFIG['distance_threshold']
            thread.detector.conf_fire = CONFIG['conf_fire']
            thread.detector.conf_person = CONFIG['conf_person']
    return {"status": "ok"}

# ============================================
# ۷. WebSocket برای هشدارهای لحظه‌ای
# ============================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    last_alert_count = 0
    try:
        while True:
            db = DatabaseManager("alerts.db")
            alerts = db.get_alerts(limit=10)
            db.close()
            if len(alerts) > last_alert_count:
                await websocket.send_text(json.dumps(alerts[:5]))
                last_alert_count = len(alerts)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        print("WebSocket disconnected")

# ============================================
# ۸. صفحه اصلی داشبورد (HTML)
# ============================================
@app.get("/")
async def dashboard():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>سیستم نظارت هوشمند آتش</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f0f1a; color: white; }
            .header { background: #1a1a2e; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #e94560; }
            .header h1 { font-size: 22px; }
            .header .badge { background: #e94560; padding: 5px 15px; border-radius: 20px; font-size: 14px; }
            .container { display: flex; height: calc(100vh - 70px); }
            .main { flex: 1; padding: 20px; overflow-y: auto; }
            .sidebar { width: 320px; background: #1a1a2e; padding: 15px; border-left: 1px solid #333; overflow-y: auto; }
            .controls { background: #16213e; padding: 15px; border-radius: 10px; margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; }
            .controls input { flex: 1; padding: 10px; border: none; border-radius: 5px; background: #0f0f1a; color: white; min-width: 200px; }
            .controls button { padding: 10px 20px; border: none; border-radius: 5px; background: #e94560; color: white; cursor: pointer; font-weight: bold; }
            .controls button:hover { background: #c73652; }
            .controls .btn-danger { background: #c0392b; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 15px; }
            .cam-box { background: #16213e; border-radius: 10px; padding: 10px; border: 1px solid #333; transition: 0.3s; }
            .cam-box:hover { border-color: #e94560; }
            .cam-box h4 { margin-bottom: 8px; font-size: 14px; color: #aaa; }
            .cam-box img { width: 100%; border-radius: 5px; background: #000; }
            .cam-box .status { font-size: 12px; color: #4ecdc4; margin-top: 5px; }
            .sidebar h3 { margin-bottom: 15px; color: #e94560; border-bottom: 1px solid #333; padding-bottom: 10px; }
            .alert-item { background: #0f0f1a; padding: 10px; border-radius: 5px; margin-bottom: 8px; border-right: 3px solid #e94560; }
            .alert-item .time { font-size: 11px; color: #888; }
            .alert-item .type { font-weight: bold; color: #ff6b6b; }
            .alert-item .cam { color: #4ecdc4; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔥 سیستم نظارت هوشمند آتش و دود</h1>
            <span class="badge" id="alertCount">۰ هشدار</span>
        </div>
        <div class="container">
            <div class="main">
                <div class="controls">
                    <input id="sourceInput" placeholder="آدرس دوربین (0, video.mp4, rtsp://...)" size="40">
                    <button onclick="addCamera()">➕ افزودن دوربین</button>
                    <button class="btn-danger" onclick="removeLastCamera()">✖ حذف آخرین</button>
                </div>
                <div class="grid" id="cameraGrid"></div>
            </div>
            <div class="sidebar">
                <h3>📨 هشدارهای لحظه‌ای</h3>
                <div id="alertList"></div>
            </div>
        </div>
        <script>
            let cameraIds = [];
            let ws = null;

            // ===== WebSocket =====
            function connectWebSocket() {
                ws = new WebSocket(`ws://${window.location.host}/ws`);
                ws.onmessage = function(e) {
                    const alerts = JSON.parse(e.data);
                    const list = document.getElementById('alertList');
                    list.innerHTML = alerts.map(a => `
                        <div class="alert-item">
                            <div class="type">🚨 ${a.alert_type || a.type}</div>
                            <div class="cam">دوربین ${a.camera_id}</div>
                            <div class="time">${a.timestamp || ''}</div>
                        </div>
                    `).join('');
                    document.getElementById('alertCount').textContent = alerts.length + ' هشدار';
                };
            }

            // ===== اضافه کردن دوربین =====
            async function addCamera() {
                const source = document.getElementById('sourceInput').value.trim();
                if (!source) return alert('لطفاً آدرس دوربین را وارد کنید');
                
                const res = await fetch('/add_camera', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({source: source})
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    document.getElementById('sourceInput').value = '';
                    loadCameras();
                } else {
                    alert('خطا: ' + (data.detail || 'مشخص نیست'));
                }
            }

            // ===== حذف آخرین دوربین =====
            async function removeLastCamera() {
                const res = await fetch('/cameras');
                const cams = await res.json();
                if (cams.length === 0) return alert('هیچ دوربینی وجود ندارد');
                const lastId = cams[cams.length-1].id;
                const del = await fetch(`/remove_camera/${lastId}`, {method: 'DELETE'});
                if (del.ok) loadCameras();
            }

            // ===== بارگذاری دوربین‌ها =====
            async function loadCameras() {
                const res = await fetch('/cameras');
                const cams = await res.json();
                const grid = document.getElementById('cameraGrid');
                grid.innerHTML = '';
                cams.forEach(cam => {
                    const box = document.createElement('div');
                    box.className = 'cam-box';
                    box.id = 'cam_' + cam.id;
                    box.innerHTML = `
                        <h4>📹 دوربین ${cam.id} ${cam.source.includes('://') ? '(IP)' : cam.source.includes('.') ? '(فیلم)' : '(وب‌کم)'}</h4>
                        <img src="/video_feed/${cam.id}" alt="دوربین ${cam.id}" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MDAiIGhlaWdodD0iMjUwIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjI1MCIgZmlsbD0iIzIyMiIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjNjY2IiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMjAiPueLseeggeWPr+iDvemBkzwvdGV4dD48L3N2Zz4='">
                        <div class="status">${cam.is_alive ? '🟢 فعال' : '🔴 غیرفعال'} | ${cam.frame_count} فریم</div>
                    `;
                    grid.appendChild(box);
                });
            }

            // ===== بارگذاری اولیه و WebSocket =====
            connectWebSocket();
            loadCameras();
            setInterval(loadCameras, 10000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html_content)

# ============================================
# ۹. اجرا
# ============================================
if __name__ == "__main__":
    # راه‌اندازی اولیه دوربین‌ها (می‌تونه خالی باشه)
    print("🚀 داشبورد در حال اجرا...")
    print("🌐 آدرس: http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)