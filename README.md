# Object Detection Camera System

A comprehensive video surveillance system with real-time object detection using YOLOv8, a user-friendly GUI built with CustomTkinter, and Telegram notifications for detected objects.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Setup and Running](#setup-and-running)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Contributing](#contributing)
- [Support](#support)
- [Demo](#demo)

## Overview
This project provides a video surveillance system that:
- Streams video from cameras (RTSP/HTTP or test video files).
- Detects objects in real-time using the YOLOv8 model.
- Saves snapshots of detected objects.
- Displays video feeds and snapshots in a graphical interface.
- Sends notifications via Telegram for specified objects.
- Includes an admin panel for user and camera management.

The system consists of a Flask-based server, a Telegram bot for notifications, and a desktop client with a GUI.

## Features
- **Real-time Video Streaming**: Supports RTSP/HTTP camera feeds and local video files.
- **Object Detection**: Uses YOLOv8 to detect objects like people, cars, animals, and more.
- **Snapshot Management**: Saves and displays snapshots of detected objects.
- **Telegram Notifications**: Configurable notifications for specific object detections.
- **User Management**: Supports user registration, authentication, and admin roles.
- **Admin Panel**: Manage users, cameras, and view server logs.
- **Customizable Settings**: Configure object detection and notification preferences.
- **Cross-Platform GUI**: Built with CustomTkinter for a modern, responsive interface.

## Requirements
- **Python**: 3.10 or higher (recommended).
- **Operating System**: Windows, macOS, or Linux.
- **Dependencies**: Listed in `requirements.txt`:
  - flask>=2.0.0
  - flask-cors>=4.0.0
  - opencv-python>=4.8.0
  - numpy>=1.24.0
  - Pillow>=10.0.0
  - bcrypt>=4.0.0
  - ultralytics>=8.0.0
  - requests>=2.31.0
  - python-telegram-bot>=21.0
  - customtkinter>=5.2.0
  - pyperclip>=1.8.0

## Installation

### Standard Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/object-detection-camera.git
   cd object-detection-camera
   ```

2. **Create a Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Up Telegram Bot**:
   - Create a bot via [BotFather](https://t.me/BotFather) and get the token.
   - Update the token in `config/config.py`.

### Docker Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/object-detection-camera.git
   cd object-detection-camera
   ```

2. **Configure the Application**:
   - Copy `config/config.example.py` to `config/config.py`
   - Set your Telegram bot token in `config/config.py`

3. **Run with Docker Compose (Recommended)**:
   ```bash
   docker-compose up -d
   ```
   This will start both the server and bot services in detached mode.

4. **Or Run with Docker Directly**:
   ```bash
   # Build the image
   docker build -t object-detection-camera .

   # Run the server
   docker run -d -p 5000:5000 \
     -v ./server/static/captures:/app/server/static/captures \
     -v ./server/users.json:/app/server/users.json \
     object-detection-camera

   # Run the bot
   docker run -d -p 5001:5001 \
     object-detection-camera python bot/bot.py
   ```

After installation, the services will be available at:
- Web interface: http://localhost:5000
- Admin panel: http://localhost:5000/admin/login
- Bot server: http://localhost:5001

### Running the Client
The client is a GUI application that runs locally on your computer, regardless of how the server is deployed (locally or via Docker).

1. **Install Client Dependencies** (if not already installed):
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Client**:
   ```bash
   python client/client.py
   ```

When running the server via Docker, ensure the client configuration points to the correct addresses:
- For local access: `http://localhost:5000`
- For network access: `http://YOUR_COMPUTER_IP:5000`

**Note**: Even when using Docker, the client must be run locally as it's a graphical application.

## Project Structure
```
object-detection-camera/
├── server.py               # Flask server for video processing and API
├── telegram_bot.py         # Telegram bot for notifications
├── client.py               # Desktop GUI client
├── config/
│   └── config.py           # Configuration (server port, bot URL, allowed extensions)
├── static/
│   └── captures/           # Directory for storing snapshots
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
└── API.md                  # API documentation
```

## Setup and Running
1. **Ensure Configuration**:
   - Verify `config/config.py` contains:
     ```python
     SERVER_PORT = 5000
     BOT_SERVER_URL = "http://127.0.0.1:5001"
     ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
     ```

2. **Run the Server**:
   ```bash
   python server.py
   ```
   The server will start at `http://127.0.0.1:5000`.

3. **Run the Telegram Bot**:
   ```bash
   python telegram_bot.py
   ```
   The bot will start and connect to Telegram.

4. **Run the Client**:
   ```bash
   python client.py
   ```
   The GUI will open, prompting for login or registration.

**Note**: Run each component in a separate terminal, or use a process manager like `pm2` for production.

## Usage
1. **Register/Login**:
   - Open the client GUI and register a new user or log in with existing credentials.

2. **Add Cameras**:
   - In the "Video" tab, click "+ Добавить камеру".
   - Enter a camera name and either an RTSP/HTTP URL or select a test video file.

3. **Configure Detection**:
   - Go to Settings > Распознавание to select objects for detection and notifications (e.g., "Человек", "Машина").

4. **View Snapshots**:
   - In the "Снимки" tab, view snapshots of detected objects, organized by camera.

5. **Telegram Notifications**:
   - In Settings > Telegram, generate an auth code.
   - Send the code to the Telegram bot to link your account.
   - Receive notifications for detected objects based on your settings.

6. **Admin Panel** (for admin users):
   - Access the "Admin" tab to manage users, cameras, and view server logs.

## API Documentation
See [API.md](docs/API.md) for detailed information on server endpoints, including authentication, camera management, and image retrieval.

## Contributing
Contributions are welcome! Please:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/your-feature`).
3. Commit changes (`git commit -m 'Add your feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

## Support
I will be glad to support and work together 💖:
- Email: yokai1076@gmail.com
- Telegram: @gfyly
- GitHub Issues: [github.com/your-username/object-detection-camera/issues](https://github.com/your-username/object-detection-camera/issues)

## Demo
YouTube: [![System Demo](https://youtu.be/X2wapBE3Cos)](https://youtu.be/X2wapBE3Cos)

This video demonstrates the key features of the system:
- Connecting IP cameras and RTSP streams
- Configuring object detection
- Working with Telegram bot
- Viewing and managing snapshots
- System administration


