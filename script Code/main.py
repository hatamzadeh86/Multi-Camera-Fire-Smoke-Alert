# main.py
import asyncio
import threading
import queue
import time
import sys
from pathlib import Path
import cv2
# اضافه کردن مسیر فعلی به sys.path
sys.path.append(str(Path(__file__).parent))

from detector import FireAlertSystem
from camera_manager import CameraManager , CameraThread
from notifier import Notifier
from database import DatabaseManager

def main():
    # ========== تنظیمات ==========
    config = {
        # مدل‌ها
        'fire_model': r'D:\yolo_runs\test_evaluation_results\final_evaluation\best.pt',
        'person_model': "yolov8n.pt",
        
        # تلگرام
        'telegram_enabled': True,
        'telegram_token': '8850812817:AAGR8VJHuXU389uBdTz5epSv6gfLy_cDNXg',
        'telegram_chat_id': '5946158255',
        
        # ایمیل (اختیاری)
        'email_enabled': False,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender_email': 'your_email@gmail.com',
        'sender_password': 'your_password',
        'receiver_email': 'receiver@gmail.com',
        
        # وب‌هوک (اختیاری)
        'webhook_enabled': False,
        'webhook_url': 'https://your-server.com/webhook',
        
        # اسلک (اختیاری)
        'slack_enabled': False,
        'slack_webhook_url': 'https://hooks.slack.com/services/...',
        
        # آستانه‌ها
        'distance_threshold': 100,
        'fire_frames_threshold': 3,
        'cooldown_seconds': 15,
        'conf_fire': 0.5,
        'conf_person': 0.5,
        
        # تنظیمات نمایش
        'show_preview': True,
        'save_video': True,
        
        # تنظیمات Notifier
        'notifier_cooldown': 5,
    }
    
    # ========== دوربین‌ها ==========
    cameras = [
        {'id': 1, 'source': r"C:\Users\E-PART.iR\Desktop\system_fire\0f97520627641f41c8300e5cb48ed28038425690-240p.mp4"},  # وب‌کم
        {'id': 2, 'source': r"D:\Dataset_F_S\project_fire_smoke\video_labels\4_6016872667682973507.mp4"},  # IP Camera
        # {'id': 3, 'source': },  # فایل ویدیویی
    ]
    
    # ========== راه‌اندازی مدیر دوربین‌ها ==========
    manager = CameraManager(
        cameras=cameras,
        config=config,
        detector_class=FireAlertSystem
    )
    manager.start_all()
    
    # ========== راه‌اندازی Notifier ==========
    notifier = Notifier(config)
    
    # ========== راه‌اندازی دیتابیس ==========
    db = DatabaseManager("alerts.db")
    
    # ========== ترد پردازش هشدارها ==========
    def process_alerts():
        while manager.running:
            try:
                alert = manager.alert_queue.get(timeout=1)
                
                # ارسال به Notifier
                notifier.send_alert(alert)
                
                # ذخیره در دیتابیس
                db.save_alert(alert)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ خطا در پردازش هشدار: {e}")
    
    collector_thread = threading.Thread(target=process_alerts, daemon=True)
    collector_thread.start()
    
    print("\n" + "="*60)
    print("🔥 سیستم تشخیص آتش و هشدار چند دوربین")
    print("="*60)
    print(f"📹 تعداد دوربین‌ها: {len(cameras)}")
    print(f"📊 آستانه فاصله: {config['distance_threshold']} پیکسل")
    print(f"📊 فریم‌های متوالی: {config['fire_frames_threshold']}")
    print(f"📨 کانال‌های فعال: {[c for c, v in notifier.channels.items() if v]}")
    print("="*60)
    print("🔴 برای خروج، کلید 'q' را در پنجره تصویر بزنید.")
    print("🔄 Watchdog برای بررسی سلامت دوربین‌ها فعال است.")
    print("="*60 + "\n")
    
    # ========== Watchdog ساده ==========
    def watchdog():
        while manager.running:
            time.sleep(10)
            status = manager.get_status()
            for s in status:
                # ✅ فقط اگه تمام نشده و زنده نیست، کرش حساب کن
                # ✅ فقط اگه تموم نشده و زنده نیست، کرش حساب کن
                if not s.get('is_alive', False) and not s.get('finished', False) and manager.running:
                    print(f"⚠️ [Watchdog] دوربین {s['camera_id']} کرش کرده! راه‌اندازی مجدد...")
                    # ... راه‌اندازی مجدد ...
                    for thread in manager.threads:
                        if thread.camera_id == s['camera_id'] and not thread.is_alive():
                            thread.stop()
                            new_thread = CameraThread(
                                camera_id=s['camera_id'],
                                source=s['source'],
                                alert_queue=manager.alert_queue,
                                config=config,
                                detector_class=FireAlertSystem
                            )
                            new_thread.start()
                            idx = manager.threads.index(thread)
                            manager.threads[idx] = new_thread
                            print(f"✅ [Watchdog] دوربین {s['camera_id']} مجدداً راه‌اندازی شد.")
    
    watchdog_thread = threading.Thread(target=watchdog, daemon=True)
    watchdog_thread.start()
    
    # ========== حلقه اصلی (نگه‌داشتن برنامه) ==========
    try:
        while manager.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 توقف توسط کاربر...")
    
    # ========== توقف همه چیز ==========
    print("\n🛑 در حال توقف سیستم...")
    manager.stop_all()
    db.close()
    cv2.destroyAllWindows()
    print("✅ سیستم متوقف شد.")

if __name__ == "__main__":
    main()