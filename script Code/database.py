# database.py
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

class DatabaseManager:
    """ذخیره‌سازی هشدارها در SQLite با قابلیت خروجی JSON"""
    
    def __init__(self, db_path: str = "alerts.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._init_db()
    
    def _init_db(self):
        """ایجاد جدول در دیتابیس"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER,
                timestamp TEXT,
                camera_id INTEGER,
                source TEXT,
                alert_type TEXT,
                severity TEXT,
                details TEXT,
                image_path TEXT,
                raw_data TEXT,
                created_at TEXT
            )
        ''')
        self.conn.commit()
    
    def save_alert(self, alert: Dict) -> bool:
        """ذخیره یک هشدار در دیتابیس"""
        try:
            created_at = datetime.now().isoformat()
            self.cursor.execute('''
                INSERT INTO alerts (
                    alert_id, timestamp, camera_id, source, alert_type,
                    severity, details, image_path, raw_data, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.get('alert_id'),
                alert.get('timestamp', datetime.now().isoformat()),
                alert.get('camera_id', -1),
                alert.get('source', ''),
                alert.get('type', ''),
                alert.get('severity', 'HIGH'),
                json.dumps(alert.get('details', {}), ensure_ascii=False),
                str(alert.get('image_path', '')),
                json.dumps(alert, ensure_ascii=False),
                created_at
            ))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ خطا در ذخیره دیتابیس: {e}")
            return False
    
    def get_alerts(self, limit: int = 100, camera_id: Optional[int] = None, 
                   alert_type: Optional[str] = None) -> List[Dict]:
        """دریافت هشدارها از دیتابیس با فیلتر"""
        query = "SELECT * FROM alerts WHERE 1=1"
        params = []
        
        if camera_id is not None:
            query += " AND camera_id = ?"
            params.append(camera_id)
        
        if alert_type:
            query += " AND alert_type = ?"
            params.append(alert_type)
        
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        
        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                'id': row[0],
                'alert_id': row[1],
                'timestamp': row[2],
                'camera_id': row[3],
                'source': row[4],
                'type': row[5],
                'severity': row[6],
                'details': json.loads(row[7]) if row[7] else {},
                'image_path': row[8],
                'raw_data': json.loads(row[9]) if row[9] else {},
                'created_at': row[10]
            })
        return alerts
    
    def export_to_json(self, output_path: str = "alerts_export.json", limit: Optional[int] = None) -> List[Dict]:
        """خروجی گرفتن از دیتابیس به صورت JSON"""
        query = "SELECT * FROM alerts ORDER BY id DESC"
        params = []
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append({
                'id': row[0],
                'alert_id': row[1],
                'timestamp': row[2],
                'camera_id': row[3],
                'source': row[4],
                'type': row[5],
                'severity': row[6],
                'details': json.loads(row[7]) if row[7] else {},
                'image_path': row[8],
                'raw_data': json.loads(row[9]) if row[9] else {},
                'created_at': row[10]
            })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
        
        print(f"✅ {len(alerts)} هشدار در {output_path} ذخیره شد.")
        return alerts
    
    def get_stats(self) -> Dict:
        """آمار هشدارها"""
        self.cursor.execute("SELECT COUNT(*), COUNT(DISTINCT camera_id) FROM alerts")
        total, cameras = self.cursor.fetchone()
        
        self.cursor.execute("SELECT alert_type, COUNT(*) FROM alerts GROUP BY alert_type")
        by_type = {row[0]: row[1] for row in self.cursor.fetchall()}
        
        return {
            'total_alerts': total,
            'total_cameras': cameras,
            'by_type': by_type
        }
    
    def close(self):
        if self.conn:
            self.conn.close()







