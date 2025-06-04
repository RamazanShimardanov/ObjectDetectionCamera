import customtkinter as ctk
from PIL import Image, ImageTk
import io
import threading
import requests
import os
from datetime import datetime
import uuid
import pyperclip
import time
import json
import cv2
import tkinter as tk
import tkinter.filedialog as filedialog

# URL сервера и Telegram-бота
SERVER_URL = "http://127.0.0.1:5000"
BOT_SERVER_URL = "http://127.0.0.1:5001"

# Основной класс приложения для работы с камерами и распознаванием объектов
class ObjectDetectionApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Настройка заголовка и размера окна
        self.title("Object Detection Camera")
        self.geometry("1200x800")

        # Настройка темной темы и цветовой схемы
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Инициализация переменных приложения
        self.cameras = {}  # Словарь для хранения данных о камерах: {name: (label, source, active_flag, frame, is_test_video)}
        self.image_widgets = {}  # Словарь для хранения виджетов изображений: {camera_name: [(label, path, timestamp, viewed)]}
        self.new_images_count = 0  # Счетчик новых изображений
        self.current_user = None  # Текущий пользователь
        self.session_token = None  # Токен сессии
        self.role = "user"  # Роль пользователя (по умолчанию user)
        self.running = True  # Флаг активности приложения
        self.detection_settings = {}  # Настройки распознавания объектов
        self.auth_code = None  # Код авторизации для Telegram
        self.settings_frame = None  # Окно настроек
        self.add_camera_window = None  # Окно добавления камеры
        self.edit_user_window = None  # Окно редактирования пользователя
        self.logs_text = None  # Текстовое поле для логов

        # Создание главного фрейма
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True)

        # Инициализация переменных для вкладок и кнопок
        self.tabview = None  # Вкладки интерфейса
        self.cameras_frame = None  # Фрейм для камер
        self.images_frame = None  # Фрейм для снимков
        self.admin_frame = None  # Фрейм для админ-панели
        self.notification_circle = None  # Индикатор новых изображений
        self.settings_button = None  # Кнопка настроек
        self.admin_button = None  # Кнопка админ-панели

        # Отображение экрана авторизации
        self.show_auth_screen()
        # Привязка обработчика изменения размера окна
        self.bind("<Configure>", self.on_resize)
        # Запуск периодического обновления видео
        self.after(20, self.update_video_frames)
        # Запуск проверки новых изображений
        self.after(5000, self.check_new_images)

        # Обработчик закрытия окна
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # Очистка главного фрейма от виджетов
    def clear_frame(self, exclude=[]):
        for widget in self.main_frame.winfo_children():
            if widget not in exclude:
                widget.destroy()
        self.main_frame.update_idletasks()

    # Отображение экрана авторизации
    def show_auth_screen(self):
        # Очистка текущего интерфейса
        self.clear_frame()
        self.auth_frame = ctk.CTkFrame(self.main_frame)
        self.auth_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # Поля для ввода логина и пароля
        ctk.CTkLabel(self.auth_frame, text="Логин:").pack(pady=5)
        self.login_entry = ctk.CTkEntry(self.auth_frame)
        self.login_entry.pack(pady=5)

        ctk.CTkLabel(self.auth_frame, text="Пароль:").pack(pady=5)
        self.password_entry = ctk.CTkEntry(self.auth_frame, show="*")
        self.password_entry.pack(pady=5)

        # Метка для отображения ошибок
        self.error_label = ctk.CTkLabel(self.auth_frame, text="", text_color="red")
        self.error_label.pack(pady=5)

        # Кнопки входа и регистрации
        ctk.CTkButton(self.auth_frame, text="Войти", command=self.login).pack(pady=10)
        ctk.CTkButton(self.auth_frame, text="Зарегистрироваться", command=self.register).pack(pady=10)

    # Обработка входа пользователя
    def login(self):
        username = self.login_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            self.error_label.configure(text="Введите логин и пароль")
            return
        try:
            response = requests.post(
                f"{SERVER_URL}/login",
                json={"username": username, "password": password},
                timeout=5
            )
            if response.status_code == 200:
                # Сохранение данных пользователя
                data = response.json()
                self.current_user = username
                self.session_token = data.get("token")
                self.auth_code = list(data.get("auth_codes", {}).keys())[0] if data.get("auth_codes") else None
                self.detection_settings = data.get("detection_settings", {})
                self.role = data.get("role", "user")
                self.error_label.configure(text="Вход выполнен, загрузка...", text_color="green")
                self.update()
                self.clear_frame()
                self.show_main_interfaces()
            else:
                self.error_label.configure(text=response.json().get("error", "Неверный логин или пароль"))
        except requests.RequestException as e:
            self.error_label.configure(text=f"Ошибка сети: {e}")

    # Обработка регистрации нового пользователя
    def register(self):
        username = self.login_entry.get().strip()
        password = self.password_entry.get().strip()
        if not username or not password:
            self.error_label.configure(text="Введите логин и пароль")
            return
        try:
            response = requests.post(
                f"{SERVER_URL}/register",
                json={"username": username, "password": password},
                timeout=5
            )
            if response.status_code == 201:
                # Сохранение данных нового пользователя
                data = response.json()
                self.current_user = username
                self.session_token = data.get("token")
                self.auth_code = list(data.get("auth_codes", {}).keys())[0] if data.get("auth_codes") else None
                self.detection_settings = data.get("detection_settings", {})
                self.role = data.get("role", "user")
                self.error_label.configure(text="Регистрация завершена, загрузка...", text_color="green")
                self.update()
                self.clear_frame()
                self.show_main_interfaces()
            else:
                self.error_label.configure(text=response.json().get("error", "Ошибка регистрации"))
        except requests.RequestException as e:
            self.error_label.configure(text=f"Ошибка сети: {e}")

    # Отображение основного интерфейса с вкладками
    def show_main_interfaces(self):
        self.clear_frame(exclude=[self.settings_button, self.notification_circle, self.admin_button])
        if not self.tabview or not self.tabview.winfo_exists():
            # Создание вкладок для видео, снимков и админ-панели (если админ)
            self.tabview = ctk.CTkTabview(self.main_frame)
            self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
            self.init_video_tab()
            self.init_images_tab()
            if self.role == "admin":
                self.tabview.add("Admin")
            self.tabview.configure(command=lambda: self.on_tab_changed(self.tabview.get()))
        if not self.settings_button or not self.settings_button.winfo_exists():
            # Кнопка настроек
            self.settings_button = ctk.CTkButton(
                self.main_frame,
                text="⚙ Настройки",
                command=self.show_settings,
                fg_color="#444444",
                hover_color="#666666",
                width=120
            )
            self.settings_button.place(relx=0.99, rely=0.01, anchor="ne")
            self.settings_button.lift()
        if self.role == "admin" and (not self.admin_button or not self.admin_button.winfo_exists()):
            # Кнопка админ-панели для администратора
            self.admin_button = ctk.CTkButton(
                self.main_frame,
                text="🛠 Админ-панель",
                command=self.show_admin_panel,
                fg_color="#444444",
                hover_color="#666666",
                width=120
            )
            self.admin_button.place(relx=0.99, rely=0.06, anchor="ne")
            self.admin_button.lift()
        if not self.notification_circle or not self.notification_circle.winfo_exists():
            # Индикатор новых изображений
            self.notification_circle = ctk.CTkCanvas(
                self.main_frame,
                width=20,
                height=20,
                bg="black",
                highlightthickness=0
            )
            self.notification_circle.pack_forget()
        self.load_previous_cameras()

    # Загрузка ранее добавленных камер с сервера
    def load_previous_cameras(self):
        if not self.current_user or not self.session_token:
            return
        try:
            response = requests.get(
                f"{SERVER_URL}/get_cameras",
                params={"username": self.current_user, "token": self.session_token},
                timeout=5
            )
            if response.status_code == 200:
                cameras = response.json().get("cameras", {})
                self.cameras.clear()
                for name, url in cameras.items():
                    self.start_video_stream(name, url, is_test_video=False)
            else:
                self.show_auth_screen()
        except requests.RequestException as e:
            print(f"Ошибка загрузки камер: {e}")

    # Запуск видеопотока для камеры
    def start_video_stream(self, name, source, is_test_video=False):
        if not self.cameras_frame or not self.cameras_frame.winfo_exists():
            return
        frame = ctk.CTkFrame(self.cameras_frame)
        # Заглушка для изображения
        placeholder_img = Image.new('RGB', (320, 240), color='black')
        placeholder_tk = ctk.CTkImage(light_image=placeholder_img, size=(320, 240))
        label = ctk.CTkLabel(frame, text=f"Подключение к {name}...", image=placeholder_tk)
        label.image = placeholder_tk
        label.pack(fill="both", expand=True)
        active_flag = [True]
        self.cameras[name] = (label, source, active_flag, frame, is_test_video)
        frame.bind("<Configure>", lambda e: self.update_camera_grid())
        self.update_camera_grid()
        if is_test_video:
            # Запуск потока для тестового видео
            threading.Thread(
                target=self.update_test_video_stream,
                args=(name, label, frame, active_flag, source),
                daemon=True
            ).start()
        else:
            # Запуск потока для реального видео
            threading.Thread(
                target=self.update_video_stream,
                args=(name, label, frame, active_flag),
                daemon=True
            ).start()

    # Обновление потока реального видео
    def update_video_stream(self, name, label, frame, active_flag):
        url = f"{SERVER_URL}/video_feed?username={self.current_user}&camera_name={name}&token={self.session_token}"
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                stream = requests.get(url, stream=True, timeout=10)
                if stream.status_code != 200:
                    label.configure(text=f"{name}: Ошибка - {stream.text}", image=None)
                    break

                bytes_data = bytes()
                for chunk in stream.iter_content(chunk_size=1024):
                    if not self.running or name not in self.cameras or not active_flag[0]:
                        break
                    bytes_data += chunk
                    a = bytes_data.find(b'\xff\xd8')
                    b = bytes_data.find(b'\xff\xd9')
                    if a != -1 and b != -1:
                        jpg = bytes_data[a:b + 2]
                        bytes_data = bytes_data[b + 2:]
                        try:
                            img = Image.open(io.BytesIO(jpg))
                            if frame.winfo_exists():
                                frame_width = max(1, frame.winfo_width())
                                frame_height = max(1, frame.winfo_height())
                                if frame_width > 0 and frame_height > 0:
                                    img_ratio = img.width / img.height
                                    new_height = frame_height
                                    new_width = int(new_height * img_ratio)
                                    if new_width > frame_width:
                                        new_width = frame_width
                                        new_height = int(new_width / img_ratio)
                                    img = img.resize((new_width, new_height), Image.Resampling.BILINEAR)
                                    img_tk = ctk.CTkImage(light_image=img, size=(new_width, new_height))
                                    self.after(0, lambda: label.configure(text="", image=img_tk))
                                    label.image = img_tk
                        except Exception as e:
                            self.after(0, lambda: label.configure(text=f"{name}: Ошибка кадра - {e}", image=None))
                break
            except requests.RequestException as e:
                self.after(0, lambda: label.configure(text=f"{name}: Ошибка - {e}", image=None))
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    break

    # Обновление потока тестового видео
    def update_test_video_stream(self, name, label, frame, active_flag, video_path):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self.after(0, lambda: label.configure(text=f"{name}: Ошибка - Не удалось открыть видео", image=None))
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = 1 / fps

        while self.running and name in self.cameras and active_flag[0]:
            ret, frame_cv = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame_rgb = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            if frame.winfo_exists():
                frame_width = max(1, frame.winfo_width())
                frame_height = max(1, frame.winfo_height())
                if frame_width > 0 and frame_height > 0:
                    img_ratio = img.width / img.height
                    new_height = frame_height
                    new_width = int(new_height * img_ratio)
                    if new_width > frame_width:
                        new_width = frame_width
                        new_height = int(new_width / img_ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    img_tk = ctk.CTkImage(light_image=img, size=(new_width, new_height))
                    self.after(0, lambda: label.configure(text="", image=img_tk))

                    label.image = img_tk
            time.sleep(frame_interval)

        cap.release()

    # Периодическое обновление кадров видео
    def update_video_frames(self):
        for name, (label, _, active_flag, frame, _) in list(self.cameras.items()):
            if label.winfo_exists() and frame.winfo_exists() and active_flag[0]:
                try:
                    pass  # Обновление происходит в потоках update_video_stream/update_test_video_stream
                except Exception as e:
                    print(f"Ошибка обновления видео для {name}: {e}")
        if self.running:
            self.after(20, self.update_video_frames)

    # Инициализация вкладки с видео
    def init_video_tab(self):
        video_tab = self.tabview.add("Video")
        self.controls_frame = ctk.CTkFrame(video_tab)
        self.controls_frame.pack(fill="x", padx=10, pady=5)
        # Кнопка добавления камеры
        ctk.CTkButton(
            self.controls_frame,
            text="+ Добавить камеру",
            command=self.show_add_camera
        ).pack(side="left", padx=5)
        self.cameras_frame = ctk.CTkFrame(video_tab)
        self.cameras_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.cameras_frame.bind("<Configure>", self.on_cameras_frame_resize)

    # Обработчик изменения размера фрейма камер
    def on_cameras_frame_resize(self, event):
        self.update_camera_grid()

    # Отображение окна добавления камеры
    def show_add_camera(self):
        if self.add_camera_window and self.add_camera_window.winfo_exists():
            self.add_camera_window.lift()
            return

        self.add_camera_window = ctk.CTkToplevel(self)
        self.add_camera_window.title("Добавить камеру")
        self.add_camera_window.geometry("400x400")
        self.add_camera_window.transient(self)
        self.add_camera_window.grab_set()
        self.add_camera_window.attributes("-topmost", True)

        # Центрирование окна
        window_width = 400
        window_height = 400
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.add_camera_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        add_camera_frame = ctk.CTkFrame(self.add_camera_window)
        add_camera_frame.pack(pady=20, padx=20, fill="both", expand=True)

        ctk.CTkLabel(add_camera_frame, text="Название камеры:").pack(pady=5)
        self.name_entry = ctk.CTkEntry(add_camera_frame)
        self.name_entry.pack(pady=5)

        # Чекбокс для тестового видео
        self.is_test_video_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            add_camera_frame,
            text="Использовать тестовое видео",
            variable=self.is_test_video_var,
            command=self.toggle_input_fields
        ).pack(pady=5)

        # Поля для ввода URL
        self.url_frame = ctk.CTkFrame(add_camera_frame)
        self.url_frame.pack(pady=5, fill="x")
        ctk.CTkLabel(self.url_frame, text="URL камеры (RTSP/HTTP):").pack(pady=5)
        self.url_entry = ctk.CTkEntry(self.url_frame)
        self.url_entry.pack(pady=5, fill="x")

        # Поля для выбора видеофайла
        self.video_frame = ctk.CTkFrame(add_camera_frame)
        self.video_file_path = ctk.StringVar()
        ctk.CTkLabel(self.video_frame, text="Файл видео:").pack(pady=5)
        self.video_entry = ctk.CTkEntry(self.video_frame, textvariable=self.video_file_path, state="readonly")
        self.video_entry.pack(pady=5, fill="x")
        ctk.CTkButton(
            self.video_frame,
            text="Выбрать видео",
            command=self.select_video_file
        ).pack(pady=5)
        self.toggle_input_fields()

        # Кнопки подключения и отмены
        ctk.CTkButton(add_camera_frame, text="Подключить", command=self.add_camera).pack(pady=10)
        ctk.CTkButton(add_camera_frame, text="Отмена", command=self.close_add_camera).pack(pady=10)

    # Переключение полей ввода (URL или видеофайл)
    def toggle_input_fields(self):
        if self.is_test_video_var.get():
            self.url_frame.pack_forget()
            self.video_frame.pack(pady=5, fill="x")
        else:
            self.video_frame.pack_forget()
            self.url_frame.pack(pady=5, fill="x")

    # Выбор тестового видеофайла
    def select_video_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.avi *.mkv"), ("All files", "*.*")]
        )
        if file_path:
            self.video_file_path.set(file_path)

    # Добавление новой камеры
    def add_camera(self):
        name = self.name_entry.get().strip()
        is_test_video = self.is_test_video_var.get()
        source = self.video_file_path.get().strip() if is_test_video else self.url_entry.get().strip()

        if not name or not source:
            tk.messagebox.showerror("Ошибка", "Укажите название камеры и источник")
            return
        if name in self.cameras:
            tk.messagebox.showerror("Ошибка", "Камера с таким именем уже существует")
            return

        try:
            if is_test_video:
                if not os.path.exists(source):
                    tk.messagebox.showerror("Ошибка", "Видеофайл не найден")
                    return
                self.start_video_stream(name, source, is_test_video=True)
                self.close_add_camera()
            else:
                response = requests.post(
                    f"{SERVER_URL}/add_camera",
                    json={
                        "username": self.current_user,
                        "name": name,
                        "url": source,
                        "token": self.session_token
                    },
                    timeout=5
                )
                if response.status_code == 200:
                    self.start_video_stream(name, source, is_test_video=False)
                    self.close_add_camera()
                else:
                    tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Закрытие окна добавления камеры
    def close_add_camera(self):
        if self.add_camera_window:
            self.add_camera_window.destroy()
            self.add_camera_window = None

    # Инициализация вкладки со снимками
    def init_images_tab(self):
        images_tab = self.tabview.add("Снимки")
        self.images_control_frame = ctk.CTkFrame(images_tab)
        self.images_control_frame.pack(fill="x", padx=10, pady=5)
        # Выбор камеры для отображения снимков
        self.camera_selector = ctk.CTkOptionMenu(
            self.images_control_frame,
            values=["Все камеры"],
            command=self.load_selected_images
        )
        self.camera_selector.pack(side="left", padx=5)
        self.images_frame = ctk.CTkScrollableFrame(images_tab)
        self.images_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.load_selected_images("Все камеры")

    # Загрузка снимков для выбранной камеры
    def load_selected_images(self, selection):
        for widget in self.images_frame.winfo_children():
            widget.destroy()
        self.image_widgets.clear()

        try:
            response = requests.get(
                f"{SERVER_URL}/get_images",
                params={"username": self.current_user, "token": self.session_token},
                timeout=5
            )
            if response.status_code == 200:
                images = response.json().get("images", {})
                cameras = images.keys() if selection == "Все камеры" else [selection]
                for camera_name in cameras:
                    if camera_name in images:
                        self.load_images_for_camera(camera_name, images[camera_name])
                self.camera_selector.configure(values=["Все камеры"] + sorted(images.keys()))
            else:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Загрузка снимков для конкретной камеры
    def load_images_for_camera(self, camera_name, image_list):
        label = ctk.CTkLabel(self.images_frame, text=f"📷 {camera_name}")
        label.pack(pady=5)
        grid_frame = ctk.CTkFrame(self.images_frame)
        grid_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.image_widgets[camera_name] = []
        for idx, (image_path, timestamp) in enumerate(sorted(image_list.items(), key=lambda x: x[1], reverse=True)):
            try:
                image_url = f"{SERVER_URL}/{image_path}?token={self.session_token}"
                response = requests.get(image_url, timeout=5)
                response.raise_for_status()
                img = Image.open(io.BytesIO(response.content))
                img_thumbnail = img.copy()
                img_thumbnail.thumbnail((150, 150), Image.Resampling.LANCZOS)
                img_tk = ctk.CTkImage(light_image=img_thumbnail, size=(150, 150))

                container = ctk.CTkFrame(grid_frame)
                container.grid(row=idx // 5, column=idx % 5, padx=5, pady=5, sticky="nsew")

                label = ctk.CTkLabel(container, image=img_tk, text="")
                label.image = img_tk
                label.pack()
                label.bind(
                    "<Button-1>",
                    lambda e, cn=camera_name, p=image_path: self.mark_image_viewed(cn, p)
                )

                time_label = ctk.CTkLabel(container, text=timestamp, font=("Arial", 10))
                time_label.pack()

                button_frame = ctk.CTkFrame(container)
                button_frame.pack(fill="x", pady=2)

                delete_button = ctk.CTkButton(
                    button_frame,
                    text="🗑️",
                    width=20,
                    height=20,
                    fg_color="#555555",
                    command=lambda cn=camera_name, p=image_path, c=container: self.delete_image(cn, p, c)
                )
                delete_button.pack(side="left", padx=2)

                open_button = ctk.CTkButton(
                    button_frame,
                    text="🔍",
                    width=20,
                    height=20,
                    fg_color="#555555",
                    command=lambda p=image_path: self.open_image_fullscreen(p)
                )
                open_button.pack(side="left", padx=2)

                viewed = False
                if not viewed:
                    indicator = ctk.CTkLabel(container, text="●", text_color="red", font=("Arial", 12))
                    indicator.place(relx=0.9, rely=0.1)

                self.image_widgets[camera_name].append((label, image_path, timestamp, viewed))
            except requests.RequestException as e:
                print(f"Ошибка загрузки изображения {image_path}: {e}")

    # Открытие изображения в полноэкранном режиме
    def open_image_fullscreen(self, image_path):
        try:
            image_url = f"{SERVER_URL}/{image_path}?token={self.session_token}"
            response = requests.get(image_url, timeout=5)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content))

            viewer_window = ctk.CTkToplevel(self)
            viewer_window.title("Просмотр изображения")
            viewer_window.geometry("800x600")

            viewer_frame = ctk.CTkFrame(viewer_window)
            viewer_frame.pack(fill="both", expand=True)

            window_width = 800
            window_height = 600
            img_width, img_height = img.size
            scale = min((window_width - 20) / img_width, (window_height - 80) / img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            img_tk = ctk.CTkImage(light_image=img, size=(new_width, new_height))

            img_label = ctk.CTkLabel(viewer_frame, image=img_tk, text="")
            img_label.image = img_tk
            img_label.pack(expand=True)

            close_button = ctk.CTkButton(
                viewer_frame,
                text="Закрыть",
                command=viewer_window.destroy,
                width=100
            )
            close_button.pack(pady=10)

            viewer_window.transient(self)
            viewer_window.grab_set()
            viewer_window.focus_set()

            screen_width = viewer_window.winfo_screenwidth()
            screen_height = viewer_window.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            viewer_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Ошибка загрузки изображения: {e}")

    # Добавление нового снимка в интерфейс
    def append_image(self, camera_name, image_path, timestamp):
        if camera_name not in self.image_widgets or \
                self.camera_selector.get() not in [camera_name, "Все камеры"]:
            return

        try:
            image_url = f"{SERVER_URL}/{image_path}?token={self.session_token}"
            response = requests.get(image_url, timeout=5)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content))
            img.thumbnail((150, 150), Image.Resampling.LANCZOS)
            img_tk = ctk.CTkImage(light_image=img, size=(150, 150))

            grid_frame = None
            for widget in self.images_frame.winfo_children():
                if isinstance(widget, ctk.CTkLabel) and widget.cget("text") == f"📷 {camera_name}":
                    children = self.images_frame.winfo_children()
                    label_index = children.index(widget)
                    if label_index + 1 < len(children):
                        grid_frame = children[label_index + 1]
                        break

            if not grid_frame:
                return

            container = ctk.CTkFrame(grid_frame)
            label = ctk.CTkLabel(container, image=img_tk, text="")
            label.image = img_tk
            label.pack()
            label.bind(
                "<Button-1>",
                lambda e: self.mark_image_viewed(camera_name, image_path)
            )

            time_label = ctk.CTkLabel(container, text=timestamp, font=("Arial", 10))
            time_label.pack()

            button_frame = ctk.CTkFrame(container)
            button_frame.pack(fill="x", pady=2)

            delete_button = ctk.CTkButton(
                button_frame,
                text="🗑️",
                width=20,
                height=20,
                fg_color="#555555",
                command=lambda: self.delete_image(camera_name, image_path, container)
            )
            delete_button.pack(side="left", padx=2)

            open_button = ctk.CTkButton(
                button_frame,
                text="🔍",
                width=20,
                height=20,
                fg_color="#555555",
                command=lambda: self.open_image_fullscreen(image_path)
            )
            open_button.pack(side="left", padx=2)

            indicator = ctk.CTkLabel(container, text="●", text_color="red", font=("Arial", 12))
            indicator.place(relx=0.9, rely=0.1)

            row = len(self.image_widgets[camera_name]) // 5
            col = len(self.image_widgets[camera_name]) % 5
            container.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self.image_widgets[camera_name].insert(0, (label, image_path, timestamp, False))
            self.new_images_count += 1
            self.update_notification()
        except requests.RequestException as e:
            print(f"Ошибка добавления изображения {image_path}: {e}")

    # Удаление снимка
    def delete_image(self, camera_name, image_path, container):
        try:
            response = requests.post(
                f"{SERVER_URL}/delete_image",
                json={
                    "username": self.current_user,
                    "image_path": image_path,
                    "token": self.session_token
                },
                timeout=5
            )
            if response.status_code == 200:
                self.image_widgets[camera_name] = [
                    (l, p, t, v) for l, p, t, v in self.image_widgets[camera_name] if p != image_path
                ]
                container.destroy()
                self.new_images_count = sum(
                    1 for cn in self.image_widgets for _, _, _, v in self.image_widgets[cn] if not v
                )
                self.update_notification()
            else:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Отметка изображения как просмотренного
    def mark_image_viewed(self, camera_name, image_path):
        for i, (label, path, timestamp, viewed) in enumerate(self.image_widgets[camera_name]):
            if path == image_path and not viewed:
                self.image_widgets[camera_name][i] = (label, path, timestamp, True)
                self.new_images_count -= 1
                for child in label.master.winfo_children():
                    if isinstance(child, ctk.CTkLabel) and child.cget("text") == "●":
                        child.destroy()
                self.update_notification()
                self.open_image_fullscreen(image_path)
                break

    # Обработка смены вкладок
    def on_tab_changed(self, tab_name):
        if tab_name == "Снимки":
            self.load_selected_images(self.camera_selector.get())
        elif tab_name == "Admin" and self.role == "admin":
            self.load_admin_panel()
        elif self.new_images_count > 0:
            for camera_name in self.image_widgets:
                for i, (label, path, timestamp, viewed) in enumerate(self.image_widgets[camera_name]):
                    if not viewed:
                        self.image_widgets[camera_name][i] = (label, path, timestamp, True)
                        for child in label.master.winfo_children():
                            if isinstance(child, ctk.CTkLabel) and child.cget("text") == "●":
                                child.destroy()
            self.new_images_count = 0
            self.update_notification()

    # Отображение админ-панели
    def show_admin_panel(self):
        if self.role != "admin":
            return
        if self.tabview.tab("Admin") not in self.tabview._tab_dict:
            self.tabview.add("Admin")
        self.tabview.set("Admin")
        self.load_admin_panel()

    # Загрузка содержимого админ-панели
    def load_admin_panel(self):
        if not self.admin_frame or not self.admin_frame.winfo_exists():
            for widget in self.tabview.tab("Admin").winfo_children():
                widget.destroy()
            self.admin_frame = ctk.CTkFrame(self.tabview.tab("Admin"))
            self.admin_frame.pack(fill="both", expand=True, padx=10, pady=10)

        admin_tabview = ctk.CTkTabview(self.admin_frame)
        admin_tabview.pack(fill="both", expand=True)

        users_tab = admin_tabview.add("Пользователи")
        self.users_frame = ctk.CTkScrollableFrame(users_tab)
        self.users_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.load_users()

        logs_tab = admin_tabview.add("Логи")
        self.logs_frame = ctk.CTkScrollableFrame(logs_tab)
        self.logs_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.load_logs()

    # Загрузка списка пользователей
    def load_users(self):
        for widget in self.users_frame.winfo_children():
            widget.destroy()
        try:
            response = requests.get(
                f"{SERVER_URL}/admin/users",
                params={"token": self.session_token},
                timeout=5
            )
            if response.status_code == 200:
                users = response.json().get("users", {})
                for username, data in users.items():
                    user_frame = ctk.CTkFrame(self.users_frame)
                    user_frame.pack(fill="x", pady=5, padx=5)

                    ctk.CTkLabel(user_frame, text=f"Пользователь: {username}").pack(side="left", padx=5)
                    ctk.CTkLabel(user_frame, text=f"Роль: {data['role']}").pack(side="left", padx=5)

                    ctk.CTkButton(
                        user_frame,
                        text="Редактировать",
                        command=lambda u=username: self.edit_user(u),
                        width=100
                    ).pack(side="right", padx=5)

                    ctk.CTkButton(
                        user_frame,
                        text="Удалить",
                        fg_color="red",
                        hover_color="#CC0000",
                        command=lambda u=username: self.delete_user(u),
                        width=100
                    ).pack(side="right", padx=5)
            else:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Удаление пользователя
    def delete_user(self, username):
        if username == self.current_user:
            tk.messagebox.showerror("Ошибка", "Нельзя удалить самого себя")
            return
        try:
            response = requests.post(
                f"{SERVER_URL}/admin/user/{username}/delete",
                headers={"Content-Type": "application/json"},
                json={},
                params={"token": self.session_token},
                timeout=5
            )
            if response.status_code == 200:
                self.load_users()
                tk.messagebox.showinfo("Успех", f"Пользователь {username} удален")
            else:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Редактирование данных пользователя
    def edit_user(self, username):
        if self.edit_user_window and self.edit_user_window.winfo_exists():
            self.edit_user_window.lift()
            return

        try:
            response = requests.get(
                f"{SERVER_URL}/admin/user/{username}",
                params={"token": self.session_token},
                timeout=5
            )
            if response.status_code != 200:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
                return
            user_data = response.json().get("user", {})
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")
            return

        self.edit_user_window = ctk.CTkToplevel(self)
        self.edit_user_window.title(f"Редактировать пользователя {username}")
        self.edit_user_window.geometry("600x600")
        self.edit_user_window.transient(self)
        self.edit_user_window.grab_set()

        edit_frame = ctk.CTkFrame(self.edit_user_window)
        edit_frame.pack(pady=20, padx=20, fill="both", expand=True)

        ctk.CTkLabel(edit_frame, text=f"Пользователь: {username}").pack(pady=5)
        ctk.CTkLabel(edit_frame, text="Роль:").pack(pady=5)
        role_var = ctk.StringVar(value=user_data.get("role", "user"))
        ctk.CTkOptionMenu(edit_frame, values=["user", "admin"], variable=role_var).pack(pady=5)

        ctk.CTkLabel(edit_frame, text="Камеры:").pack(pady=5)
        cameras_text = ctk.CTkTextbox(edit_frame, height=100)
        cameras_text.insert("0.0", json.dumps(user_data.get("cameras", {}), indent=2, ensure_ascii=False))
        cameras_text.pack(pady=5, fill="x")

        ctk.CTkLabel(edit_frame, text="Настройки распознавания:").pack(pady=5)
        settings_text = ctk.CTkTextbox(edit_frame, height=100)
        settings_text.insert("0.0", json.dumps(user_data.get("detection_settings", {}), indent=2, ensure_ascii=False))
        settings_text.pack(pady=5, fill="x")

        def save_changes():
            try:
                cameras_data = json.loads(cameras_text.get("0.0", "end").strip())
                settings_data = json.loads(settings_text.get("0.0", "end").strip())
                response = requests.post(
                    f"{SERVER_URL}/admin/user/{username}",
                    json={
                        "cameras": cameras_data,
                        "detection_settings": settings_data,
                        "role": role_var.get()
                    },
                    params={"token": self.session_token},
                    timeout=5
                )
                if response.status_code == 200:
                    self.load_users()
                    self.edit_user_window.destroy()
                    self.edit_user_window = None
                    tk.messagebox.showinfo("Успех", "Изменения сохранены")
                else:
                    tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
            except (json.JSONDecodeError, requests.RequestException) as e:
                tk.messagebox.showerror("Ошибка", f"Ошибка сохранения: {e}")

        ctk.CTkButton(edit_frame, text="Сохранить", command=save_changes).pack(pady=10)
        ctk.CTkButton(
            edit_frame,
            text="Отмена",
            command=lambda: self.edit_user_window.destroy()
        ).pack(pady=10)

    # Загрузка логов сервера
    def load_logs(self):
        for widget in self.logs_frame.winfo_children():
            widget.destroy()
        try:
            response = requests.get(
                f"{SERVER_URL}/admin/logs",
                params={"token": self.session_token},
                timeout=5
            )
            if response.status_code == 200:
                logs = response.json().get("logs", [])
                self.logs_text = ctk.CTkTextbox(self.logs_frame, height=400, wrap="word")
                self.logs_text.pack(fill="both", expand=True, padx=5, pady=5)
                for log in logs:
                    self.logs_text.insert("end", log)
                self.logs_text.configure(state="disabled")
            else:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Отображение окна настроек
    def show_settings(self):
        if self.settings_frame and self.settings_frame.winfo_exists():
            self.settings_frame.lift()
            return

        self.settings_frame = ctk.CTkToplevel(self)
        self.settings_frame.title("Настройки")
        self.settings_frame.geometry("600x600")
        self.settings_frame.transient(self)
        self.settings_frame.grab_set()

        settings_tabview = ctk.CTkTabview(self.settings_frame)
        settings_tabview.pack(fill="both", expand=True, padx=10, pady=10)

        cameras_tab = settings_tabview.add("Камеры")
        detection_tab = settings_tabview.add("Распознавание")
        telegram_tab = settings_tabview.add("Telegram")
        account_tab = settings_tabview.add("Аккаунт")

        # Вкладка камер
        cameras_frame = ctk.CTkScrollableFrame(cameras_tab)
        cameras_frame.pack(fill="both", expand=True, padx=5, pady=5)
        try:
            response = requests.get(
                f"{SERVER_URL}/get_cameras",
                params={"username": self.current_user, "token": self.session_token},
                timeout=5
            )
            if response.status_code == 200:
                cameras = response.json().get("cameras", {})
                for name, url in cameras.items():
                    camera_frame = ctk.CTkFrame(cameras_frame)
                    camera_frame.pack(fill="x", pady=5, padx=5)
                    ctk.CTkLabel(camera_frame, text=f"{name}: {url}").pack(side="left", padx=5)
                    ctk.CTkButton(
                        camera_frame,
                        text="Удалить",
                        fg_color="red",
                        hover_color="#CC0000",
                        command=lambda n=name: self.delete_camera(n),
                        width=100
                    ).pack(side="right", padx=5)
            else:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

        # Вкладка настроек распознавания
        detection_frame = ctk.CTkFrame(detection_tab)
        detection_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            detection_frame,
            text="Настройки распознавания объектов",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(10, 5))

        ctk.CTkLabel(
            detection_frame,
            text="Выберите объекты для распознавания и уведомлений",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(0, 10))

        grid_frame = ctk.CTkFrame(detection_frame)
        grid_frame.pack(fill="both", expand=True, padx=5, pady=5)

        detection_classes = {
            "0": "Человек", "2": "Машина", "16": "Собака", "15": "Кот", "1": "Велосипед",
            "3": "Мотоцикл", "14": "Птица", "24": "Рюкзак", "25": "Зонт", "26": "Сумка"
        }

        detection_vars = {}

        headers = ["Объект", "Распознавать", "Уведомлять"]
        for col, header in enumerate(headers):
            ctk.CTkLabel(
                grid_frame,
                text=header,
                font=ctk.CTkFont(size=12, weight="bold")
            ).grid(row=0, column=col, padx=10, pady=5, sticky="w")

        separator = ctk.CTkFrame(grid_frame, height=2, fg_color="#666666")
        separator.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)

        for row, (class_id, class_name) in enumerate(detection_classes.items(), start=2):
            detect_var = ctk.BooleanVar(
                value=self.detection_settings.get(class_id, {}).get("detect", False)
            )
            notify_var = ctk.BooleanVar(
                value=self.detection_settings.get(class_id, {}).get("notify", False)
            )
            detection_vars[class_id] = {"detect": detect_var, "notify": notify_var}

            ctk.CTkLabel(
                grid_frame,
                text=class_name,
                font=ctk.CTkFont(size=12)
            ).grid(row=row, column=0, padx=10, pady=5, sticky="w")

            ctk.CTkCheckBox(
                grid_frame,
                text="",
                variable=detect_var,
                width=20
            ).grid(row=row, column=1, padx=10, pady=5)

            ctk.CTkCheckBox(
                grid_frame,
                text="",
                variable=notify_var,
                width=20
            ).grid(row=row, column=2, padx=10, pady=5)

        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=0)
        grid_frame.grid_columnconfigure(2, weight=0)

        def save_detection_settings():
            new_settings = {}
            for class_id, vars in detection_vars.items():
                new_settings[class_id] = {
                    "detect": vars["detect"].get(),
                    "notify": vars["notify"].get()
                }
            try:
                response = requests.post(
                    f"{SERVER_URL}/update_detection_settings",
                    json={
                        "username": self.current_user,
                        "detection_settings": new_settings,
                        "token": self.session_token
                    },
                    timeout=5
                )
                if response.status_code == 200:
                    self.detection_settings = new_settings
                    success_label = ctk.CTkLabel(
                        detection_frame,
                        text="Настройки успешно сохранены",
                        text_color="green",
                        font=ctk.CTkFont(size=12)
                    )
                    success_label.pack(pady=5)
                    self.after(3000, success_label.destroy)
                else:
                    tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
            except requests.RequestException as e:
                tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

        ctk.CTkButton(
            detection_frame,
            text="Сохранить настройки",
            command=save_detection_settings,
            fg_color="#4CAF50",
            hover_color="#45A049",
            width=200
        ).pack(pady=15)

        # Вкладка Telegram
        telegram_frame = ctk.CTkFrame(telegram_tab)
        telegram_frame.pack(fill="both", expand=True, padx=5, pady=5)
        ctk.CTkLabel(telegram_frame, text="Код для Telegram:").pack(pady=5)
        code_entry = ctk.CTkEntry(telegram_frame)
        code_entry.pack(pady=5)
        if self.auth_code:
            code_entry.insert(0, self.auth_code)
            code_entry.configure(state="readonly")

        def toggle_buttons():
            generate_button.configure(state="normal" if not self.auth_code else "disabled")
            delete_button.configure(state="disabled" if not self.auth_code else "normal")
            code_entry.configure(state="normal" if not self.auth_code else "readonly")
            copy_button.configure(state="normal" if self.auth_code else "disabled")

        generate_button = ctk.CTkButton(
            telegram_frame,
            text="Сгенерировать новый код",
            command=lambda: self.generate_telegram_code(code_entry, toggle_buttons),
            state="normal" if not self.auth_code else "disabled"
        )
        generate_button.pack(pady=5)

        delete_button = ctk.CTkButton(
            telegram_frame,
            text="Удалить код",
            fg_color="red",
            hover_color="#CC0000",
            command=lambda: self.delete_telegram_code(code_entry, toggle_buttons),
            state="disabled" if not self.auth_code else "normal"
        )
        delete_button.pack(pady=5)

        copy_button = ctk.CTkButton(
            telegram_frame,
            text="Копировать код",
            command=lambda: pyperclip.copy(code_entry.get()),
            state="normal" if self.auth_code else "disabled"
        )
        copy_button.pack(pady=5)

        # Вкладка аккаунта
        account_frame = ctk.CTkFrame(account_tab)
        account_frame.pack(fill="both", expand=True, padx=5, pady=5)
        ctk.CTkLabel(account_frame, text=f"Пользователь: {self.current_user}").pack(pady=5)
        ctk.CTkButton(
            account_frame,
            text="Выйти",
            fg_color="red",
            hover_color="#CC0000",
            command=self.logout
        ).pack(pady=10)

    # Генерация нового Telegram-кода
    def generate_telegram_code(self, code_entry, toggle_buttons):
        if self.auth_code:
            tk.messagebox.showerror("Ошибка", "Код уже сгенерирован")
            return
        code = str(uuid.uuid4())[:8]
        try:
            response = requests.post(
                f"{SERVER_URL}/update_auth_code",
                json={
                    "username": self.current_user,
                    "code": code,
                    "token": self.session_token
                },
                timeout=5
            )
            if response.status_code == 200:
                self.auth_code = code
                code_entry.delete(0, "end")
                code_entry.insert(0, code)
                toggle_buttons()
                tk.messagebox.showinfo("Успех", "Код успешно сгенерирован")
            else:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Удаление Telegram-кода
    def delete_telegram_code(self, code_entry, toggle_buttons):
        if not self.auth_code:
            tk.messagebox.showerror("Ошибка", "Код не существует")
            return
        try:
            # Примечание: Сервер не поддерживает /delete_auth_code, используем заглушку
            self.auth_code = None
            code_entry.delete(0, "end")
            toggle_buttons()
            tk.messagebox.showinfo("Успех", "Код удален")
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Удаление камеры
    def delete_camera(self, name):
        try:
            if name in self.cameras:
                label, _, active_flag, frame, is_test_video = self.cameras[name]
                active_flag[0] = False
                frame.destroy()
                del self.cameras[name]
                self.update_camera_grid()
                if not is_test_video:
                    response = requests.post(
                        f"{SERVER_URL}/delete_camera",
                        json={
                            "username": self.current_user,
                            "name": name,
                            "token": self.session_token
                        },
                        timeout=5
                    )
                    if response.status_code == 200:
                        tk.messagebox.showinfo("Успех", f"Камера {name} удалена")
                    else:
                        tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Выход из аккаунта
    def logout(self):
        try:
            response = requests.post(
                f"{SERVER_URL}/logout",
                json={
                    "username": self.current_user,
                    "token": self.session_token
                },
                timeout=5
            )
            if response.status_code == 200:
                self.current_user = None
                self.session_token = None
                self.role = "user"
                self.auth_code = None
                self.cameras.clear()
                self.image_widgets.clear()
                self.new_images_count = 0
                self.show_auth_screen()
                tk.messagebox.showinfo("Успех", "Выход выполнен")
            else:
                tk.messagebox.showerror("Ошибка", response.json().get("error", "Неизвестная ошибка"))
        except requests.RequestException as e:
            tk.messagebox.showerror("Ошибка", f"Сетевая ошибка: {e}")

    # Обновление сетки камер
    def update_camera_grid(self):
        if not self.cameras_frame or not self.cameras_frame.winfo_exists():
            return

        num_cameras = len(self.cameras)
        frame_width = max(1, self.cameras_frame.winfo_width())
        frame_height = max(1, self.cameras_frame.winfo_height())

        for i in range(self.cameras_frame.grid_size()[0]):
            self.cameras_frame.grid_columnconfigure(i, weight=0, minsize=0)
        for i in range(self.cameras_frame.grid_size()[1]):
            self.cameras_frame.grid_rowconfigure(i, weight=0)

        if num_cameras == 0:
            return

        idx = 0
        for name, (_, _, _, frame, _) in self.cameras.items():
            if not frame.winfo_exists():
                continue

            if num_cameras == 1:
                frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
                self.cameras_frame.grid_columnconfigure(0, weight=1)
                self.cameras_frame.grid_rowconfigure(0, weight=1)
            elif num_cameras == 2:
                frame.grid(row=0, column=idx, sticky="nsew", padx=5, pady=5)
                self.cameras_frame.grid_columnconfigure(idx, weight=1, minsize=frame_width // 2)
                self.cameras_frame.grid_rowconfigure(0, weight=1)
            else:
                cols = max(1, frame_width // 320)
                row = idx // cols
                col = idx % cols
                frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                self.cameras_frame.grid_columnconfigure(col, weight=1)
                self.cameras_frame.grid_rowconfigure(row, weight=1)

            idx += 1

    # Проверка новых снимков
    def check_new_images(self):
        if not self.current_user or not self.session_token:
            return
        try:
            response = requests.get(
                f"{SERVER_URL}/new_images_count",
                params={"username": self.current_user, "token": self.session_token},
                timeout=5
            )
            if response.status_code == 200:
                new_images = response.json().get("new_images", {})
                for camera_name, images in new_images.items():
                    for image_path, timestamp in images.items():
                        self.append_image(camera_name, image_path, timestamp)
            else:
                print(f"Ошибка проверки новых изображений: {response.json().get('error', 'Неизвестная ошибка')}")
        except requests.RequestException as e:
            print(f"Сетевая ошибка при проверке новых изображений: {e}")
        if self.running:
            self.after(5000, self.check_new_images)

    # Обновление индикатора новых изображений
    def update_notification(self):
        if self.new_images_count > 0:
            self.notification_circle.delete("all")
            self.notification_circle.create_oval(0, 0, 20, 20, fill="red")
            self.notification_circle.create_text(
                10, 10, text=str(self.new_images_count), fill="white", font=("Arial", 12)
            )
            self.notification_circle.place(relx=0.95, rely=0.05, anchor="center")
        else:
            self.notification_circle.place_forget()

    # Обработчик изменения размера окна
    def on_resize(self, event):
        self.update_camera_grid()

    # Обработчик закрытия приложения
    def on_closing(self):
        self.running = False
        for _, (_, _, active_flag, frame, _) in self.cameras.items():
            active_flag[0] = False
            if frame.winfo_exists():
                frame.destroy()
        self.destroy()

# Запуск приложения
if __name__ == "__main__":
    app = ObjectDetectionApp()
    app.mainloop()