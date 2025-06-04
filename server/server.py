import os
import sys
import cv2
from flask import Flask, Response, request, jsonify, send_file, render_template, redirect, url_for
from ultralytics import YOLO
import threading
import json
import hashlib
from datetime import datetime
import logging
import requests
import time
import shutil

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from config.config import SERVER_PORT, BOT_SERVER_URL, ALLOWED_EXTENSIONS
# Настройка логирования для записи в файл и консоль
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация Flask-приложения
app = Flask(__name__)
app.logger.disabled = True
app.secret_key = 'supersecretkey123'

# Инициализация модели YOLO
model = YOLO("yolov8n.pt")

# Хранилища данных
captured_images = {}  # Снимки: {username: {camera_name: {path: timestamp}}}
new_images = {}  # Новые снимки для уведомлений
users_db = {}  # База пользователей: {username: {password, auth_codes, cameras, detection_settings, role}}
sessions = {}  # Сессии: {token: {username, expires}}
active_cameras = {}  # Активные камеры: {username: {camera_name: thread}}

# Константы и пути
DB_FILE = "users.json"
DB_LOCK = threading.Lock()

# Классы для обнаружения объектов
DETECTION_CLASSES = {
    0: "person", 2: "car", 16: "dog", 15: "cat", 1: "bicycle",
    3: "motorcycle", 14: "bird", 24: "backpack", 25: "umbrella", 26: "handbag"
}

# Данные администратора
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

# Загрузка базы данных из файла
def load_db():
    with DB_LOCK:
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        return data.get("users", {}), data.get("captured_images", {})
                    return {}, {}
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка загрузки базы данных: {e}")
                return {}, {}
        return {}, {}

# Сохранение базы данных в файл
def save_db():
    with DB_LOCK:
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                data = {"users": users_db, "captured_images": captured_images}
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info("База данных сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения базы данных: {e}")

# Инициализация базы данных
users_db, captured_images = load_db()
if not users_db:
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump({"users": {}, "captured_images": {}}, f)
    logger.info("Создана новая база данных")

# Генерация токена для сессии
def generate_token(username):
    token = hashlib.sha256(f"{username}{datetime.now()}".encode()).hexdigest()
    logger.info(f"Сгенерирован токен для пользователя {username}")
    return token

# Сохранение кадра в файловую систему
def save_frame(username, camera_name, frame):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    image_dir = os.path.join("static/captures", username, camera_name).replace("\\", "/")
    os.makedirs(image_dir, exist_ok=True)
    filename = f"{image_dir}/{timestamp}.jpg".replace("\\", "/")
    success = cv2.imwrite(filename, frame)
    if success:
        logger.info(f"Сохранен кадр: {filename}")
    else:
        logger.error(f"Не удалось сохранить кадр: {filename}")
    return filename, timestamp

# Генерация видеопотока для клиента
def generate_frames(username, camera_name):
    logger.info(f"Запрос стрима для пользователя {username}, камера {camera_name}")
    if username not in users_db:
        logger.error(f"Пользователь {username} не найден")
        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nUser not found\r\n'
        return
    if camera_name not in users_db[username]["cameras"]:
        logger.error(f"Камера {camera_name} не найдена для пользователя {username}")
        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera not found\r\n'
        return
    url = users_db[username]["cameras"][camera_name]
    logger.info(f"URL камеры: {url}")

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
    if not cap.isOpened():
        logger.error(f"Не удалось открыть стрим для {url}")
        time.sleep(2)
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            logger.error(f"Повторное подключение к {url} не удалось")
            yield b'--frame\r\nContent-Type: text/plain\r\n\r\nFailed to open stream\r\n'
            return

    try:
        logger.info(f"Стрим для {camera_name} успешно открыт")
        while True:
            success, frame = cap.read()
            if not success:
                logger.error(f"Не удалось прочитать кадр для {camera_name}")
                yield b'--frame\r\nContent-Type: text/plain\r\n\r\nStream interrupted\r\n'
                break

            results = model(frame, verbose=False)
            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls[0].item())
                    confidence = box.conf[0].item()
                    if str(class_id) in users_db[username]["detection_settings"] and \
                            users_db[username]["detection_settings"][str(class_id)]["detect"] and confidence > 0.5:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        label = f"{DETECTION_CLASSES[class_id]} {confidence:.2f}"
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                logger.warning(f"Не удалось закодировать кадр для {camera_name}")
                continue
            frame_bytes = buffer.tobytes()
            logger.debug(f"Отправка кадра для {camera_name}, размер: {len(frame_bytes)}")
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.033)
    except Exception as e:
        logger.error(f"Ошибка в стриме для {camera_name}: {e}")
        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nStream error\r\n'
    finally:
        cap.release()
        logger.info(f"Стрим для {camera_name} закрыт")

# Обработка камеры для обнаружения объектов
def process_camera(username, camera_name, url):
    logger.info(f"Запуск обработки камеры {camera_name} для {username}")
    retries = 3
    cap = None
    for attempt in range(retries):
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
        if cap.isOpened():
            logger.info(f"Камера {camera_name} успешно открыта на попытке {attempt + 1}")
            break
        logger.warning(f"Не удалось открыть камеру {camera_name}, попытка {attempt + 1}/{retries}")
        time.sleep(5)
    else:
        logger.error(f"Не удалось открыть камеру {camera_name} после {retries} попыток")
        if username in active_cameras and camera_name in active_cameras[username]:
            del active_cameras[username][camera_name]
        return

    last_snapshot_time = 0
    detection_interval = 5

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                logger.error(f"Не удалось получить кадр для {camera_name}")
                break

            results = model(frame, verbose=False)
            detected_classes = set()

            for result in results:
                for box in result.boxes:
                    class_id = int(box.cls[0].item())
                    confidence = box.conf[0].item()
                    if confidence > 0.5 and str(class_id) in users_db[username]["detection_settings"] and \
                            users_db[username]["detection_settings"][str(class_id)]["detect"]:
                        detected_classes.add(class_id)

            current_time = time.time()
            if detected_classes and current_time - last_snapshot_time >= detection_interval:
                last_snapshot_time = current_time
                filename, timestamp = save_frame(username, camera_name, frame)
                if username not in captured_images:
                    captured_images[username] = {}
                if camera_name not in captured_images[username]:
                    captured_images[username][camera_name] = {}
                captured_images[username][camera_name][filename] = timestamp
                if username not in new_images:
                    new_images[username] = {}
                if camera_name not in new_images[username]:
                    new_images[username][camera_name] = {}
                new_images[username][camera_name][filename] = timestamp
                save_db()

                if "auth_codes" in users_db[username] and users_db[username]["auth_codes"]:
                    for code, (user, chat_id) in users_db[username]["auth_codes"].items():
                        if chat_id:
                            for class_id in detected_classes:
                                if users_db[username]["detection_settings"].get(str(class_id), {}).get("notify", False):
                                    logger.info(f"Отправка уведомления для class_id={class_id}, chat_id={chat_id}")
                                    caption = (
                                        f"Обнаружен объект: {DETECTION_CLASSES[class_id]}\n"
                                        f"Камера: {camera_name}\n"
                                        f"Дата и время: {timestamp}"
                                    )
                                    for attempt in range(3):
                                        try:
                                            with open(filename, 'rb') as photo:
                                                files = {'photo': photo}
                                                data = {
                                                    'chat_id': chat_id,
                                                    'code': code,
                                                    'caption': caption
                                                }
                                                response = requests.post(
                                                    f"{BOT_SERVER_URL}/send_image",
                                                    files=files,
                                                    data=data,
                                                    timeout=5
                                                )
                                                logger.info(f"Уведомление отправлено: {response.text}")
                                                break
                                        except requests.RequestException as e:
                                            logger.warning(f"Попытка {attempt + 1}/3 не удалась: {e}")
                                            if attempt < 2:
                                                time.sleep(2)
                                            else:
                                                logger.error(f"Не удалось отправить уведомление: {e}")

            time.sleep(0.033)
    except Exception as e:
        logger.error(f"Ошибка обработки камеры {camera_name}: {e}")
    finally:
        cap.release()
        if username in active_cameras and camera_name in active_cameras[username]:
            del active_cameras[username][camera_name]
        logger.info(f"Обработка камеры {camera_name} завершена")

# Проверка валидности сессии
def check_session(token):
    if token in sessions and sessions[token]["expires"] > time.time():
        return sessions[token]["username"]
    logger.warning(f"Недействительный или истекший токен: {token}")
    return None

# Проверка админской сессии
def check_admin_session(token):
    if token in sessions and sessions[token]["expires"] > time.time():
        username = sessions[token]["username"]
        if username in users_db and users_db[username]["role"] == "admin":
            return username
    logger.warning(f"Недействительный или не админский токен: {token}")
    return None

# Обновление активных камер для пользователя
def update_active_cameras(username):
    if username not in users_db:
        logger.error(f"Пользователь {username} не найден для обновления камер")
        return
    if "detection_settings" not in users_db[username]:
        users_db[username]["detection_settings"] = {}
    if username in active_cameras:
        current_cameras = set(users_db[username]["cameras"].keys())
        active_camera_names = set(active_cameras[username].keys())
        for camera_name in active_camera_names - current_cameras:
            del active_cameras[username][camera_name]
            logger.info(f"Удалена неактивная камера {camera_name} для {username}")
    for name, url in users_db[username]["cameras"].items():
        if username not in active_cameras or name not in active_cameras[username]:
            thread = threading.Thread(target=process_camera, args=(username, name, url), daemon=True)
            if username not in active_cameras:
                active_cameras[username] = {}
            active_cameras[username][name] = thread
            thread.start()
            logger.info(f"Запущена обработка камеры {name} для {username}")

# Корневой маршрут
@app.route('/')
def index():
    logger.info("Доступ к корневому маршруту")
    return "Server is running"

# Эндпоинт для видеопотока
@app.route('/video_feed', methods=['GET'])
def video_feed():
    username = request.args.get("username")
    camera_name = request.args.get("camera_name")
    token = request.args.get("token")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для {username}, токен: {token}")
        return jsonify({"error": "Недействительная сессия"}), 401
    return Response(generate_frames(username, camera_name), mimetype='multipart/x-mixed-replace; boundary=frame')

# Эндпоинт для регистрации
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        logger.error("Регистрация: логин или пароль не указаны")
        return jsonify({"error": "Логин и пароль обязательны"}), 400
    if username in users_db:
        logger.error(f"Регистрация: пользователь {username} уже существует")
        return jsonify({"error": "Пользователь уже существует"}), 400
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    token = generate_token(username)
    users_db[username] = {
        "password": hashed_password,
        "auth_codes": {},
        "cameras": {},
        "detection_settings": {},
        "role": "user"
    }
    sessions[token] = {"username": username, "expires": time.time() + 3600}
    save_db()
    logger.info(f"Зарегистрирован пользователь {username}")
    return jsonify({
        "token": token,
        "auth_codes": {},
        "detection_settings": {},
        "role": "user"
    }), 201

# Эндпоинт для входа
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        logger.error("Логин: логин или пароль не указаны")
        return jsonify({"error": "Логин и пароль обязательны"}), 400
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    if username in users_db and users_db[username]["password"] == hashed_password:
        token = generate_token(username)
        sessions[token] = {"username": username, "expires": time.time() + 3600}
        if "detection_settings" not in users_db[username]:
            users_db[username]["detection_settings"] = {}
        if "role" not in users_db[username]:
            users_db[username]["role"] = "user"
        if "auth_codes" not in users_db[username]:
            users_db[username]["auth_codes"] = {}
        save_db()
        update_active_cameras(username)
        logger.info(f"Вход выполнен для {username}")
        return jsonify({
            "token": token,
            "auth_codes": users_db[username]["auth_codes"],
            "detection_settings": users_db[username]["detection_settings"],
            "role": users_db[username]["role"]
        }), 200
    logger.error(f"Неверный логин или пароль для {username}")
    return jsonify({"error": "Неверный логин или пароль"}), 401

# Эндпоинт для выхода
@app.route('/logout', methods=['POST'])
def logout():
    data = request.json
    username = data.get("username")
    token = data.get("token")
    if check_session(token) == username and token in sessions:
        del sessions[token]
        if username in active_cameras:
            del active_cameras[username]
        logger.info(f"Выход выполнен для {username}")
    return jsonify({"status": "success"}), 200

# Эндпоинт для обновления кода авторизации
@app.route('/update_auth_code', methods=['POST'])
def update_auth_code():
    data = request.json
    username = data.get("username")
    code = data.get("code")
    token = data.get("token")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для обновления auth_code: {username}")
        return jsonify({"error": "Недействительная сессия"}), 401
    if users_db[username]["auth_codes"]:
        existing_code = next(iter(users_db[username]["auth_codes"]))
        logger.info(f"Попытка обновления auth_code для {username}, но код уже существует: {existing_code}")
        return jsonify({"error": "Код уже сгенерирован для этого аккаунта", "auth_code": existing_code}), 400
    users_db[username]["auth_codes"][code] = [username, None]
    save_db()
    logger.info(f"Обновлен auth_code для {username}: {code}")
    return jsonify({"status": "success", "auth_code": code}), 200

# Эндпоинт для привязки chat_id
@app.route('/update_chat_id', methods=['POST'])
def update_chat_id():
    data = request.json
    code = data.get("code")
    chat_id = data.get("chat_id")
    logger.info(f"Получен запрос на обновление chat_id: code={code}, chat_id={chat_id}")

    username = None
    for user, user_data in users_db.items():
        if code in user_data.get("auth_codes", {}):
            username = user
            break

    if username is None:
        logger.error(f"Код {code} не найден ни для одного пользователя")
        return jsonify({"error": "Код не найден"}), 404

    users_db[username]["auth_codes"][code][1] = chat_id
    save_db()
    logger.info(f"Обновлен chat_id для {username}: {chat_id}")
    return jsonify({"status": "success"}), 200

# Эндпоинт для обновления настроек обнаружения
@app.route('/update_detection_settings', methods=['POST'])
def update_detection_settings():
    data = request.json
    username = data.get("username")
    token = data.get("token")
    detection_settings = data.get("detection_settings")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для обновления настроек: {username}")
        return jsonify({"error": "Недействительная сессия"}), 401
    users_db[username]["detection_settings"] = detection_settings
    save_db()
    logger.info(f"Настройки распознавания обновлены для {username}")
    return jsonify({"status": "success"}), 200

# Эндпоинт для добавления камеры
@app.route('/add_camera', methods=['POST'])
def add_camera():
    data = request.json
    username = data.get("username")
    name = data.get("name")
    url = data.get("url")
    token = data.get("token")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для добавления камеры: {username}")
        return jsonify({"error": "Недействительная сессия"}), 401
    users_db[username]["cameras"][name] = url
    save_db()
    update_active_cameras(username)
    logger.info(f"Добавлена камера {name} для {username}")
    return jsonify({"status": "success"}), 200

# Эндпоинт для удаления камеры
@app.route('/delete_camera', methods=['POST'])
def delete_camera():
    data = request.json
    username = data.get("username")
    name = data.get("name")
    token = data.get("token")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для удаления камеры: {username}")
        return jsonify({"error": "Недействительная сессия"}), 401
    if name in users_db[username]["cameras"]:
        del users_db[username]["cameras"][name]
        save_db()
        if username in active_cameras and name in active_cameras[username]:
            del active_cameras[username][name]
        logger.info(f"Удалена камера {name} для {username}")
        return jsonify({"status": "success"}), 200
    logger.error(f"Камера {name} не найдена для {username}")
    return jsonify({"error": "Камера не найдена"}), 404

# Эндпоинт для получения списка камер
@app.route('/get_cameras', methods=['GET'])
def get_cameras():
    username = request.args.get("username")
    token = request.args.get("token")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для получения камер: {username}")
        return jsonify({"error": "Недействительная сессия"}), 401
    logger.info(f"Возвращены камеры для {username}")
    return jsonify({"cameras": users_db[username]["cameras"]}), 200

# Эндпоинт для получения снимков
@app.route('/get_images', methods=['GET'])
def get_images():
    username = request.args.get("username")
    token = request.args.get("token")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для получения снимков: {username}")
        return jsonify({"error": "Недействительная сессия"}), 401
    images = captured_images.get(username, {})
    filtered_images = {}
    for camera_name, image_dict in images.items():
        filtered_images[camera_name] = {path: ts for path, ts in image_dict.items() if os.path.exists(path)}
    logger.info(f"Возвращены снимки для {username}")
    return jsonify({"images": filtered_images}), 200

# Эндпоинт для проверки новых снимков
@app.route('/new_images_count', methods=['GET'])
def new_images_count():
    username = request.args.get("username")
    token = request.args.get("token")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для проверки новых снимков: {username}")
        return jsonify({"error": "Недействительная сессия"}), 401
    new = new_images.get(username, {})
    new_images[username] = {}
    save_db()
    logger.info(f"Возвращены новые снимки для {username}")
    return jsonify({"new_images": new}), 200

# Эндпоинт для удаления снимка
@app.route('/delete_image', methods=['POST'])
def delete_image():
    data = request.json
    username = data.get("username")
    image_path = data.get("image_path").replace("\\", "/")
    token = data.get("token")
    if not check_session(token) or check_session(token) != username:
        logger.error(f"Недействительная сессия для удаления снимка: {username}")
        return jsonify({"error": "Недействительная сессия"}), 401
    for camera_name in captured_images.get(username, {}):
        if image_path in captured_images[username][camera_name]:
            del captured_images[username][camera_name][image_path]
            if os.path.exists(image_path):
                os.remove(image_path)
            save_db()
            logger.info(f"Удален снимок {image_path} для {username}")
            return jsonify({"status": "success"}), 200
    logger.error(f"Снимок {image_path} не найден для {username}")
    return jsonify({"error": "Изображение не найдено"}), 404

# Эндпоинт для отдачи изображений
@app.route('/static/captures/<path:path>')
def serve_image(path):
    token = request.args.get("token")
    if not token or not check_session(token):
        logger.error("Недействительный токен для доступа к изображению")
        return jsonify({"error": "Недействительная сессия"}), 401
    full_path = os.path.join('static/captures', path).replace("\\", "/")
    logger.info(f"Запрос изображения: {full_path}")
    if os.path.exists(full_path):
        logger.info(f"Файл найден, отправка: {full_path}")
        return send_file(full_path)
    logger.error(f"Файл не найден: {full_path}")
    return jsonify({"error": "Файл не найден"}), 404

# Эндпоинт для входа админа
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    logger.info("Запрос к /admin/login")
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        if username == ADMIN_USERNAME and hashed_password == ADMIN_PASSWORD_HASH:
            token = generate_token(username)
            sessions[token] = {"username": username, "expires": time.time() + 3600}
            if username not in users_db:
                users_db[username] = {
                    "password": hashed_password,
                    "auth_codes": {},
                    "cameras": {},
                    "detection_settings": {},
                    "role": "admin"
                }
                save_db()
            logger.info(f"Админ {username} вошел в систему")
            response = redirect(url_for('admin_panel'))
            response.set_cookie('admin_token', token, max_age=3600)
            return response
        else:
            logger.error("Неудачная попытка входа админа")
            return render_template('admin_login.html', error="Неверный логин или пароль")

    return render_template('admin_login.html')

# Эндпоинт для админ-панели
@app.route('/admin/panel')
def admin_panel():
    token = request.cookies.get('admin_token')
    if not check_admin_session(token):
        logger.warning("Неавторизованный доступ к /admin/panel")
        return redirect(url_for('admin_login'))

    logger.info("Доступ к админ-панели")
    return render_template('admin_panel.html', users=users_db)

# Эндпоинт для выхода админа
@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    token = request.cookies.get('admin_token')
    if token in sessions:
        del sessions[token]
        logger.info("Админ вышел из системы")
    response = jsonify({"status": "success"})
    response.delete_cookie('admin_token')
    return response

# Эндпоинт для удаления пользователя
@app.route('/admin/user/<username>/delete', methods=['POST'])
def delete_user(username):
    token = request.cookies.get('admin_token')
    if not check_admin_session(token):
        logger.error("Недействительная сессия или недостаточно прав для удаления пользователя")
        return jsonify({"error": "Недействительная сессия или недостаточно прав"}), 401

    if username in users_db:
        if username == check_admin_session(token):
            logger.error("Админ не может удалить сам себя")
            return jsonify({"error": "Нельзя удалить самого себя"}), 403

        del users_db[username]
        if username in active_cameras:
            del active_cameras[username]
        if username in captured_images:
            user_image_dir = os.path.join("static/captures", username).replace("\\", "/")
            if os.path.exists(user_image_dir):
                shutil.rmtree(user_image_dir)
            del captured_images[username]
        if username in new_images:
            del new_images[username]

        save_db()
        logger.info(f"Пользователь {username} удален админом")
        return jsonify({"status": "success"}), 200

    logger.error(f"Пользователь {username} не найден")
    return jsonify({"error": "Пользователь не найден"}), 404

# Эндпоинт для получения списка пользователей
@app.route('/admin/users', methods=['GET'])
def admin_users():
    token = request.args.get("token")
    if not check_admin_session(token):
        logger.error("Недействительная сессия или недостаточно прав для доступа к пользователям")
        return jsonify({"error": "Недействительная сессия или недостаточно прав"}), 401
    logger.info("Возвращены данные пользователей для админа")
    return jsonify({"users": users_db}), 200

# Эндпоинт для получения данных пользователя
@app.route('/admin/user/<username>', methods=['GET'])
def get_user(username):
    token = request.args.get("token")
    if not check_admin_session(token):
        logger.error("Недействительная сессия или недостаточно прав для получения данных пользователя")
        return jsonify({"error": "Недействительная сессия или недостаточно прав"}), 401
    if username in users_db:
        logger.info(f"Возвращены данные пользователя {username}")
        return jsonify({"user": users_db[username]}), 200
    logger.error(f"Пользователь {username} не найден")
    return jsonify({"error": "Пользователь не найден"}), 404

# Эндпоинт для обновления данных пользователя
@app.route('/admin/user/<username>', methods=['POST'])
def update_user(username):
    token = request.args.get("token")
    if not check_admin_session(token):
        logger.error("Недействительная сессия или недостаточно прав для обновления пользователя")
        return jsonify({"error": "Недействительная сессия или недостаточно прав"}), 401
    data = request.json
    if username in users_db:
        users_db[username]["cameras"] = data.get("cameras", users_db[username]["cameras"])
        users_db[username]["detection_settings"] = data.get("detection_settings",
                                                            users_db[username]["detection_settings"])
        users_db[username]["role"] = data.get("role", users_db[username]["role"])
        save_db()
        update_active_cameras(username)
        logger.info(f"Обновлены данные пользователя {username}")
        return jsonify({"status": "success"}), 200
    logger.error(f"Пользователь {username} не найден")
    return jsonify({"error": "Пользователь не найден"}), 404

# Эндпоинт для получения логов
@app.route('/admin/logs', methods=['GET'])
def get_logs():
    token = request.args.get("token")
    if not check_admin_session(token):
        logger.error("Недействительная сессия или недостаточно прав для доступа к логам")
        return jsonify({"error": "Недействительная сессия или недостаточно прав"}), 401
    try:
        with open("server.log", 'r', encoding='utf-8') as f:
            logs = f.readlines()
        logger.info("Возвращены логи для админа")
        return jsonify({"logs": logs}), 200
    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        return jsonify({"error": "Ошибка чтения логов"}), 500


if __name__ == "__main__":
    os.makedirs("static/captures", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    app.run(host="0.0.0.0", port=SERVER_PORT, debug=True)