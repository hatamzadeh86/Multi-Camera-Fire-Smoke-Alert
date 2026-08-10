# notifier.py
import requests
import json
from typing import Dict, List, Optional
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

class Notifier:
    """ارسال هشدار به چندین کانال مختلف"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.channels = {
            'telegram': config.get('telegram_enabled', True),
            'email': config.get('email_enabled', False),
            'webhook': config.get('webhook_enabled', False),
            'slack': config.get('slack_enabled', False),
        }
        self.last_alert_time = {}
        self.cooldown = config.get('notifier_cooldown', 5)  # ثانیه
    
    def send_alert(self, alert: Dict) -> Dict:
        """ارسال هشدار به همه کانال‌های فعال"""
        results = {}
        
        # جلوگیری از ارسال تکراری (cooldown)
        alert_key = f"{alert.get('camera_id')}_{alert.get('type')}"
        import time
        current_time = time.time()
        if alert_key in self.last_alert_time:
            if current_time - self.last_alert_time[alert_key] < self.cooldown:
                return {'status': 'cooldown', 'message': 'در حال خنک‌سازی'}
        self.last_alert_time[alert_key] = current_time
        
        if self.channels.get('telegram'):
            results['telegram'] = self._send_telegram(alert)
        
        if self.channels.get('email'):
            results['email'] = self._send_email(alert)
        
        if self.channels.get('webhook'):
            results['webhook'] = self._send_webhook(alert)
        
        if self.channels.get('slack'):
            results['slack'] = self._send_slack(alert)
        
        return results
    
    def _send_telegram(self, alert: Dict) -> bool:
        """ارسال به تلگرام"""
        try:
            token = self.config.get('telegram_token')
            chat_id = self.config.get('telegram_chat_id')
            if not token or not chat_id:
                print("⚠️ Telegram credentials missing")
                return False
            
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            
            with open(alert['image_path'], 'rb') as photo:
                files = {'photo': photo}
                data = {
                    'chat_id': chat_id,
                    'caption': alert.get('caption', ''),
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, files=files, data=data, timeout=10)
            
            if response.status_code == 200:
                print("✅ Telegram: ارسال موفق")
                return True
            else:
                print(f"❌ Telegram: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Telegram error: {e}")
            return False
    
    def _send_email(self, alert: Dict) -> bool:
        """ارسال ایمیل"""
        try:
            smtp_server = self.config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = self.config.get('smtp_port', 587)
            sender_email = self.config.get('sender_email')
            sender_password = self.config.get('sender_password')
            receiver_email = self.config.get('receiver_email')
            
            if not sender_email or not receiver_email:
                return False
            
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = receiver_email
            msg['Subject'] = f"🚨 ALERT: {alert.get('type')}"
            
            body = alert.get('caption', '')
            msg.attach(MIMEText(body, 'plain'))
            
            # ضمیمه عکس
            img_path = Path(alert['image_path'])
            if img_path.exists():
                with open(img_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={img_path.name}')
                    msg.attach(part)
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            print("✅ Email: ارسال موفق")
            return True
        except Exception as e:
            print(f"❌ Email error: {e}")
            return False
    
    def _send_webhook(self, alert: Dict) -> bool:
        """ارسال به Webhook"""
        try:
            webhook_url = self.config.get('webhook_url')
            if not webhook_url:
                return False
            
            payload = {
                'type': alert.get('type'),
                'timestamp': alert.get('timestamp'),
                'camera_id': alert.get('camera_id'),
                'severity': alert.get('severity', 'HIGH'),
                'details': alert.get('details', {})
            }
            response = requests.post(webhook_url, json=payload, timeout=5)
            if response.status_code == 200:
                print("✅ Webhook: ارسال موفق")
                return True
            else:
                print(f"❌ Webhook: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Webhook error: {e}")
            return False
    
    def _send_slack(self, alert: Dict) -> bool:
        """ارسال به Slack"""
        try:
            webhook_url = self.config.get('slack_webhook_url')
            if not webhook_url:
                return False
            
            payload = {
                'text': f"🚨 {alert.get('type')}",
                'attachments': [{
                    'color': 'danger',
                    'fields': [
                        {'title': 'دوربین', 'value': alert.get('camera_id', 'N/A'), 'short': True},
                        {'title': 'زمان', 'value': alert.get('timestamp', 'N/A'), 'short': True},
                        {'title': 'جزئیات', 'value': str(alert.get('details', {})), 'short': False}
                    ]
                }]
            }
            response = requests.post(webhook_url, json=payload, timeout=5)
            if response.status_code == 200:
                print("✅ Slack: ارسال موفق")
                return True
            else:
                print(f"❌ Slack: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Slack error: {e}")
            return False