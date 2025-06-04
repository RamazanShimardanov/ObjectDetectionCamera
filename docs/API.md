# API Documentation

This document describes the REST API endpoints provided by the Object Detection Camera System server. The server handles user authentication, camera management, video streaming, image storage, and admin functions.

## Base URL
```
http://127.0.0.1:5000
```

## Authentication
Most endpoints require a `token` parameter, obtained via `/login` or `/register`. Include the token in query parameters or request body as specified.

## Endpoints

### 1. User Authentication

#### POST /login
Authenticates a user and returns a session token.

**Request**:
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```

**Response**:
- **200 OK**:
  ```json
  {
    "token": "string",
    "role": "user|admin",
    "auth_codes": {"code": ["username", "chat_id"]},
    "detection_settings": {"class_id": {"detect": boolean, "notify": boolean}}
  }
  ```
- **401 Unauthorized**:
  ```json
  {"error": "Invalid credentials"}
  ```

**Example**:
```bash
curl -X POST http://127.0.0.1:5000/login \
-H "Content-Type: application/json" \
-d '{"username": "user1", "password": "pass123"}'
```

#### POST /register
Registers a new user and returns a session token.

**Request**:
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```

**Response**:
- **201 Created**:
  ```json
  {
    "token": "string",
    "role": "user",
    "auth_codes": {},
    "detection_settings": {}
  }
  ```
- **400 Bad Request**:
  ```json
  {"error": "Username already exists"}
  ```

**Example**:
```bash
curl -X POST http://127.0.0.1:5000/register \
-H "Content-Type: application/json" \
-d '{"username": "user1", "password": "pass123"}'
```

#### POST /logout
Logs out a user, invalidating the session token.

**Request**:
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "username": "string",
    "token": "string"
  }
  ```

**Response**:
- **200 OK**:
  ```json
  {"message": "Logged out successfully"}
  ```
- **401 Unauthorized**:
  ```json
  {"error": "Invalid token"}
  ```

### 2. Camera Management

#### POST /add_camera
Adds a new camera for the user.

**Request**:
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "username": "string",
    "name": "string",
    "url": "string",
    "token": "string"
  }
  ```

**Response**:
- **200 OK**:
  ```json
  {"message": "Camera added successfully"}
  ```
- **400 Bad Request**:
  ```json
  {"error": "Camera name already exists"}
  ```

**Example**:
```bash
curl -X POST http://127.0.0.1:5000/add_camera \
-H "Content-Type: application/json" \
-d '{"username": "user1", "name": "cam1", "url": "rtsp://example.com/stream", "token": "your-token"}'
```

#### POST /delete_camera
Deletes a camera for the user.

**Request**:
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "username": "string",
    "name": "string",
    "token": "string"
  }
  ```

**Response**:
- **200 OK**:
  ```json
  {"message": "Camera deleted successfully"}
  ```
- **404 Not Found**:
  ```json
  {"error": "Camera not found"}
  ```

#### GET /get_cameras
Retrieves the list of cameras for the user.

**Request**:
- **Query Parameters**:
  - `username`: string
  - `token`: string

**Response**:
- **200 OK**:
  ```json
  {
    "cameras": {
      "cam1": "rtsp://example.com/stream",
      "cam2": "http://example.com/video"
    }
  }
  ```
- **401 Unauthorized**:
  ```json
  {"error": "Invalid token"}
  ```

**Example**:
```bash
curl http://127.0.0.1:5000/get_cameras?username=user1&token=your-token
```

### 3. Video and Image Handling

#### GET /video_feed
Streams video feed for a specific camera (MJPEG format).

**Request**:
- **Query Parameters**:
  - `username`: string
  - `camera_name`: string
  - `token`: string

**Response**:
- **200 OK**: MJPEG stream (`Content-Type: multipart/x-mixed-replace; boundary=frame`)
- **404 Not Found**:
  ```json
  {"error": "Camera not found"}
  ```

**Example**:
```bash
curl http://127.0.0.1:5000/video_feed?username=user1&camera_name=cam1&token=your-token
```

#### GET /get_images
Retrieves snapshots for the user, organized by camera.

**Request**:
- **Query Parameters**:
  - `username`: string
  - `token`: string

**Response**:
- **200 OK**:
  ```json
  {
    "images": {
      "cam1": {
        "static/captures/user1/cam1/2025-05-16_10-30-00.jpg": "2025-05-16 10:30:00",
        "static/captures/user1/cam1/2025-05-16_10-31-00.jpg": "2025-05-16 10:31:00"
      }
    }
  }
  ```
- **401 Unauthorized**:
  ```json
  {"error": "Invalid token"}
  ```

#### POST /delete_image
Deletes a specific snapshot.

**Request**:
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "username": "string",
    "image_path": "string",
    "token": "string"
  }
  ```

**Response**:
- **200 OK**:
  ```json
  {"message": "Image deleted successfully"}
  ```
- **404 Not Found**:
  ```json
  {"error": "Image not found"}
  ```

#### GET /new_images_count
Checks for new (unviewed) snapshots.

**Request**:
- **Query Parameters**:
  - `username`: string
  - `token`: string

**Response**:
- **200 OK**:
  ```json
  {
    "new_images": {
      "cam1": {
        "static/captures/user1/cam1/2025-05-16_10-32-00.jpg": "2025-05-16 10:32:00"
      }
    }
  }
  ```

### 4. Detection Settings

#### POST /update_detection_settings
Updates object detection and notification settings.

**Request**:
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "username": "string",
    "detection_settings": {
      "0": {"detect": true, "notify": true},
      "2": {"detect": true, "notify": false}
    },
    "token": "string"
  }
  ```

**Response**:
- **200 OK**:
  ```json
  {"message": "Settings updated successfully"}
  ```

**Note**: Class IDs correspond to YOLOv8 classes (e.g., 0=person, 2=car).

### 5. Telegram Integration

#### POST /update_auth_code
Generates or updates a Telegram auth code for the user.

**Request**:
- **Content-Type**: application/json
- **Body**:
  ```json
  {
    "username": "string",
    "code": "string",
    "token": "string"
  }
  ```

**Response**:
- **200 OK**:
  ```json
  {"message": "Auth code updated successfully"}
  ```

### 6. Admin Endpoints

#### GET /admin/users
Lists all users (admin only).

**Request**:
- **Query Parameters**:
  - `token`: string

**Response**:
- **200 OK**:
  ```json
  {
    "users": {
      "user1": {
        "role": "user",
        "cameras": {"cam1": "rtsp://example.com"},
        "detection_settings": {}
      }
    }
  }
  ```

#### GET /admin/user/{username}
Retrieves details for a specific user (admin only).

**Request**:
- **Query Parameters**:
  - `token`: string

**Response**:
- **200 OK**:
  ```json
  {
    "user": {
      "role": "user",
      "cameras": {"cam1": "rtsp://example.com"},
      "detection_settings": {}
    }
  }
  ```

#### POST /admin/user/{username}
Updates user details (admin only).

**Request**:
- **Content-Type**: application/json
- **Query Parameters**:
  - `token`: string
- **Body**:
  ```json
  {
    "role": "user|admin",
    "cameras": {"cam1": "rtsp://example.com"},
    "detection_settings": {"0": {"detect": true, "notify": true}}
  }
  ```

**Response**:
- **200 OK**:
  ```json
  {"message": "User updated successfully"}
  ```

#### POST /admin/user/{username}/delete
Deletes a user (admin only).

**Request**:
- **Query Parameters**:
  - `token`: string
- **Body**: Empty JSON (`{}`)

**Response**:
- **200 OK**:
  ```json
  {"message": "User deleted successfully"}
  ```

#### GET /admin/logs
Retrieves server logs (admin only).

**Request**:
- **Query Parameters**:
  - `token`: string

**Response**:
- **200 OK**:
  ```json
  {
    "logs": [
      "2025-05-16 10:30:00 - User user1 logged in",
      "2025-05-16 10:31:00 - Camera cam1 added"
    ]
  }
  ```

## Error Handling
All endpoints return JSON error responses with appropriate HTTP status codes:
- **400 Bad Request**: Invalid input data.
- **401 Unauthorized**: Missing or invalid token.
- **404 Not Found**: Resource not found.
- **500 Internal Server Error**: Unexpected server error.

**Example**:
```json
{"error": "Invalid token"}
```

## Notes
- Ensure the `token` is included in requests where required.
- The `/video_feed` endpoint streams MJPEG, suitable for browser or client display.
- Admin endpoints are restricted to users with `role: admin`.
