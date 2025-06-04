# Используем официальный образ Python
FROM python:3.13-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости для OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код проекта
COPY . .

# Создаем необходимые директории
RUN mkdir -p server/static/captures server/templates

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app

# Открываем порты
EXPOSE 5000 5001

# По умолчанию запускаем сервер
CMD ["python", "run_server.py"] 