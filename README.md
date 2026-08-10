# Multi-Camera-Fire-Smoke-Alert


# Smart Fire & Smoke Monitoring System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/YOLOv8-ultralytics-red" alt="YOLOv8">
  <img src="https://img.shields.io/badge/FastAPI-0.110.0-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

<p align="center">
  A real-time intelligent monitoring system for Fire and Smoke detection using YOLOv8, with multi-channel alerting and a web-based dashboard.
</p>

---

## Table of Contents
- [About the Project](#about-the-project)
- [System Architecture](#system-architecture)
- [Dataset & Training](#dataset--training)
- [Model Performance](#model-performance)
- [Features](#features)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [Docker Deployment](#docker-deployment)
- [Sample Outputs](#sample-outputs)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## About the Project

This project is a real-time intelligent monitoring system designed to detect Fire and Smoke using YOLOv8. The system supports multiple simultaneous cameras, real-time processing, and sends alerts through multiple channels including Telegram, Email, and Webhook.

### Why This Project?
- Early detection of fire and smoke.
- High accuracy with low false alarm rate.
- Scalable architecture supporting multiple cameras.
- Deployable on local servers, cloud, or edge devices.

---

## System Architecture

┌─────────────────────────────────────────────────────────────────┐
│                      Cameras (IP / USB / RTSP)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Camera 1 │  │ Camera 2 │  │ Camera 3 │  │ Camera 4 │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Camera Manager (Multi-Thread)              │
│           Concurrent frame acquisition and decoding          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      YOLOv8 Detection Engine                  │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │  Fire & Smoke    │    │   Person         │                  │
│  │  Detector        │    │   Detector       │                  │
│  │  (best.onnx)     │    │   (yolov8n.pt)   │                  │
│  └──────────────────┘    └──────────────────┘                  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Risk Analysis Engine                     │
│         Calculates distance and overlap of person to fire     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Notification System                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Telegram │  │  Email   │  │ Webhook  │  │  Slack   │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Web Dashboard (FastAPI)                      │
│        Real-time monitoring, camera management, alerts       │
└─────────────────────────────────────────────────────────────────┘
### Dataset
The model is trained on a combination of the following datasets:

| Dataset | Images | Description |
|---------|--------|-------------|
| D-Fire | 21,000+ | Comprehensive fire and smoke dataset with high diversity |
| Custom Dataset | 38,000+ | Includes fire, smoke, and human images from various sources |

The D-Fire dataset is a specialized dataset for fire and smoke detection containing over 21,000 images. It has been widely used in academic papers for evaluating fire and smoke detection models.

### Training Process
- Architecture: YOLOv8 (Nano and S)
- Optimizer: AdamW with learning rate 0.01
- Input Size: 640x640 pixels
- Epochs: 100 to 150
- Data Augmentation: Mosaic, MixUp, Horizontal Flip, HSV Augmentation

### Model Conversion
The final model is converted to ONNX format to:
- Increase inference speed.
- Enable deployment on various hardware platforms.
- Reduce model size.

---

## Model Performance

### Evaluation Results on Test Set

| Class | Precision | Recall | mAP50 | mAP50-95 |
|-------|-----------|--------|-------|----------|
| Fire | 85.7% | 81.1% | 88.5% | 60.8% |
| Smoke | 92.7% | 90.8% | 95.8% | 78.2% |
| All | 89.2% | 85.9% | 92.2% | 69.5% |

> Results are based on evaluation on the test set and are consistent with results reported in peer-reviewed papers.

### Comparison with Other Models

| Model | mAP50 | FPS | Model Size |
|-------|-------|-----|------------|
| YOLOv8n (This Project) | 92.2% | 97 | 6.2 MB |
| YOLOv5s | 88.1% | 75 | 14.5 MB |
| Faster R-CNN | 85.3% | 15 | 108 MB |

### Key Performance Insights
- Smoke detection is more accurate than fire detection (95.8% vs 88.5% mAP50).
- Suitable for real-world environments due to evaluation on D-Fire which includes diverse lighting and angles.
- High speed (97 FPS) makes it ideal for real-time processing.

---

## Features

### Detection
- Fire and Smoke detection with high accuracy.
- Person detection for risk analysis (proximity to fire).
- Support for multiple simultaneous cameras.
- Object tracking with Track ID for temporal analysis.

### Alert System
- Telegram alerts with real-time image capture.
- Email alerts with full reports and attached images.
- Webhook support for integration with other systems.
- In-dashboard alert notifications independent of internet.

### Web Dashboard
- Real-time display of all camera feeds.
- Camera management: add and remove cameras.
- Alert history listing.
- Dynamic configuration updates without restart.

### Storage
- SQLite database for alert storage.
- JSONL export for alerts.
- Video storage for processed feeds.

---

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip
- (Optional) GPU with CUDA for faster processing

### Installation

1. Clone the repository
git clone https://github.com/hatamzadeh86/Multi-Camera-Fire-Smoke-Alert.git
cd smart-fire-monitoring
2. Install dependencies
pip install -r requirements.txt
3. Download models
# Fire and Smoke detection model (ONNX)
# Person detection model (YOLOv8n)
4. Configure Telegram
- Create a bot via BotFather on Telegram.
- Set the bot token and chat ID in main.py or Dashboard.py.

5. Run the system
# Run web dashboard
python Dashboard.py

# Or run command-line version
python main.py
6. Access dashboard
http://localhost:8000
---

## Configuration

### config in main.py

`python
config = {
    # Models
    'fire_model': 'best.onnx',
    'person_model': 'yolov8n.pt',
    
    # Telegram
    'telegram_enabled': True,
    'telegram_token': 'YOUR_BOT_TOKEN',
    'telegram_chat_id': 'YOUR_CHAT_ID',
    
    # Email
    'email_enabled': False,
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your_email@gmail.com',
    'sender_password': 'your_password',
    'receiver_email': 'receiver@gmail.com',
    
    # Webhook
    'webhook_enabled': False,
    'webhook_url': 'https://your-server.com/webhook',
    
    # Thresholds
    'distance_threshold': 150,        # Distance threshold (pixels)
    'fire_frames_threshold': 3,       # Consecutive frames for fire alert
    'cooldown_seconds': 15,           # Cooldown between alerts (seconds)
    'conf_fire': 0.5,                 # Fire confidence threshold
    'conf_person': 0.5,               # Person confidence threshold
    
    # Display
    'show_preview': True,
    'save_video': True,
}

### Camera Configuration

python
cameras = [
    {'id': 1, 'source': 0},                              # Webcam
    {'id': 2, 'source': 'video.mp4'},                    # Video file
    {'id': 3, 'source': 'rtsp://admin:pass@192.168.1.100:554/stream1'},  # IP Camera
]

---


yaml
version: '3.8'
services:
  fire-detection:
    build: .
    container_name: fire_system
    ports:
      - "8000:8000"
    volumes:
      - ./captures:/app/captures
      - ./outputs:/app/outputs
      - ./alerts.db:/app/alerts.db
      - ./best.onnx:/app/best.onnx
    environment:
      - TZ=Asia/Tehran
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
`

---

## Sample Outputs


# Web Dashboard
<p align="center">
  <img src="Screenshot 2026-08-10 120815.png" alt="result_Images" width="400">
</p>




### Telegram Alert
https://github.com/hatamzadeh86/Multi-Camera-Fire-Smoke-Alert/blob/main/result_Images/Screenshot%202026-08-10%20120931.png?raw=true

### Video Output
<p align="center">
  <img src="screenshots/video_output.gif" alt="Video Output" width="600">
</p>

---

## Roadmap

- [ ] TensorRT support for faster inference.
- [ ] Segmentation model for more precise detection.
- [ ] LLM integration for automated report generation.
- [ ] Advanced admin panel with danger zone configuration.
- [ ] Support for additional protocols (MQTT, ZMQ).

---

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## License

Distributed under the MIT License. See LICENSE for more information.

---

## Contact

- Email: your-email@example.com
- LinkedIn: Your LinkedIn Profile
- Github : https://github.com/hatamzadeh86

---

<p align="center">
  Made with ❤️ and ☕
</p>
---

## Dataset & Training
