import os
import sys

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from flask import Flask, request
import requests
import threading
import asyncio
from config.config import SERVER_URL, BOT_TOKEN, FLASK_PORT

# Настройка логирования для отладки и мониторинга
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Инициализация Flask-приложения
app = Flask(__name__)
bot_application = None  # Глобальная переменная для хранения приложения Telegram-бота

# Эндпоинт Flask для отправки изображений в Telegram
@app.route('/send_image', methods=['POST'])
def send_image():
    # Получение данных из запроса
    chat_id = request.form.get('chat_id')  # ID чата Telegram
    code = request.form.get('code')  # Код авторизации
    caption = request.form.get('caption')  # Подпись к изображению
    photo = request.files.get('photo')  # Файл изображения

    # Проверка наличия всех необходимых данных
    if not all([chat_id, code, caption, photo]):
        logger.error(f"Отсутствуют данные: chat_id={chat_id}, code={code}, caption={caption}, photo={'есть' if photo else 'нет'}")
        return {"error": "Отсутствуют необходимые данные"}, 400

    # Проверка инициализации бота
    if not bot_application:
        logger.error("Приложение бота не инициализировано")
        return {"error": "Бот не инициализирован"}, 500

    # Проверка авторизации chat_id
    user_codes = bot_application.bot_data.get('user_codes', {})
    if chat_id not in user_codes or user_codes[chat_id] != code:
        logger.error(f"Неавторизованный chat_id {chat_id} или неверный код {code}")
        return {"error": "Неавторизованный chat_id или код"}, 401

    # Асинхронная отправка изображения
    try:
        photo.seek(0)  # Сброс указателя файла
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            bot_application.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption
            )
        )
        loop.close()
        logger.info(f"Изображение отправлено в чат {chat_id}")
        return {"status": "success"}, 200
    except Exception as e:
        logger.error(f"Ошибка отправки изображения в чат {chat_id}: {e}")
        return {"error": str(e)}, 500

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Запрос кода авторизации у пользователя
    await update.message.reply_text(
        "Введите код авторизации из приложения."
    )
    context.user_data['awaiting_code'] = True  # Установка флага ожидания кода
    logger.debug(f"Пользователь {update.effective_user.id} начал авторизацию")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверка, ожидается ли код
    if not context.user_data.get('awaiting_code', False):
        await update.message.reply_text("Используйте команду /start для начала.")
        return

    code = update.message.text.strip()  # Получение введенного кода
    chat_id = str(update.effective_chat.id)  # ID чата

    try:
        # Отправка запроса на сервер для проверки кода
        response = requests.post(
            f"{SERVER_URL}/update_chat_id",
            json={"code": code, "chat_id": chat_id},
            timeout=5
        )

        if response.status_code == 200:
            # Сохранение кода в данных бота
            context.bot_data.setdefault('user_codes', {})
            context.bot_data['user_codes'][chat_id] = code
            context.user_data['awaiting_code'] = False
            await update.message.reply_text(
                "Код подтвержден. Уведомления об объектах будут отправляться."
            )
            logger.info(f"Код {code} подтвержден для chat_id {chat_id}")
        else:
            # Обработка ошибки от сервера
            error_msg = response.json().get("error", "Неизвестная ошибка")
            await update.message.reply_text(f"Ошибка: {error_msg}. Повторите попытку.")
            logger.error(f"Ошибка проверки кода {code}: {response.text}")
    except requests.RequestException as e:
        await update.message.reply_text(f"Сетевая ошибка: {e}. Повторите позже.")
        logger.error(f"Сетевая ошибка при проверке кода {code}: {e}")

# Запуск Flask-сервера в отдельном потоке
def run_flask():
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)

# Основная функция для запуска бота
def main():
    global bot_application
    # Инициализация приложения Telegram-бота
    bot_application = Application.builder().token(BOT_TOKEN).build()

    # Регистрация обработчиков команд и сообщений
    bot_application.add_handler(CommandHandler("start", start))
    bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск Flask-сервера в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Запуск бота
    logger.info("Бот запущен")
    bot_application.run_polling()

# Точка входа
if __name__ == "__main__":
    main()