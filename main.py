import asyncio
import os
import docx
import re
import PyPDF2
import logging
import httpx
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from groq import Groq

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8502301153:AAEoqXKhKsB7-RJfhux575jqBtV74dwAUes'
GROQ_KEY = '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'
PROXY_URL = "socks5://rP4AjF:Q9TK72@45.145.57.210:11121"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    # Увеличенный тайм-аут для стабильности прокси
    proxy_client = httpx.Client(proxy=PROXY_URL, timeout=40.0)
    groq_client = Groq(api_key=GROQ_KEY, http_client=proxy_client)
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
except Exception as e:
    logger.critical(f"Ошибка настройки: {e}")
    exit(1)

user_history = {}

# --- СИСТЕМНАЯ ИНСТРУКЦИЯ (С ФОРМАТИРОВАНИЕМ) ---
def get_system_prompt(user_name):
    return (
        f"Твое имя: Бот Эдиус. Собеседник: {user_name}. Создатель: Виталий Воробьев.\n"
        "ВАЖНО ПО ФОРМАТИРОВАНИЮ:\n"
        "1. Всегда используй Markdown.\n"
        "2. Заголовки выделяй жирным (например: **Заголовок**).\n"
        "3. Важные мысли выделяй курсивом или жирным.\n"
        "4. Используй списки (• или 1.) для перечислений.\n"
        "5. Делай отступы между абзацами.\n"
        "Твоя цель: давать структурированные, красивые и умные ответы. ✨"
    )

# --- КЛАВИАТУРА (КНОПКИ) ---
def get_analysis_keyboard():
    buttons = [
        [
            InlineKeyboardButton(text="📝 Кратко", callback_data="btn_summary"),
            InlineKeyboardButton(text="⚖️ Риски", callback_data="btn_risks")
        ],
        [
            InlineKeyboardButton(text="🇬🇧 English", callback_data="btn_translate"),
            InlineKeyboardButton(text="🧠 Совет", callback_data="btn_advice")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ЧТЕНИЕ ФАЙЛОВ ---
def read_docx(path):
    try:
        doc = docx.Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    except: return ""

def read_pdf(path):
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t: text += t + "\n"
        return text
    except: return ""

# --- УМНАЯ ОТПРАВКА СООБЩЕНИЙ ---
async def send_smart_message(message, text, reply_markup=None):
    """
    Пытается отправить красиво (Markdown). 
    Если Telegram ругается на ошибки форматирования — отправляет обычным текстом.
    """
    try:
        # Пробуем отправить красиво
        if len(text) > 4000:
            for x in range(0, len(text), 4000):
                await message.answer(text[x:x+4000], parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        else:
            await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.warning(f"Ошибка Markdown, отправляю чистый текст: {e}")
        # Если ошибка — отправляем без форматирования
        if len(text) > 4000:
            for x in range(0, len(text), 4000):
                await message.answer(text[x:x+4000], reply_markup=reply_markup)
        else:
            await message.answer(text, reply_markup=reply_markup)

# --- АНАЛИЗ (C RETRY И КНОПКАМИ) ---
async def run_mega_analysis(message, content, user_name, is_button_click=False):
    if not is_button_click:
        await bot.send_chat_action(message.chat.id, action="typing")
    
    user_id = message.chat.id # Используем chat_id для истории
    
    if user_id not in user_history:
        user_history[user_id] = [{"role": "system", "content": get_system_prompt(user_name)}]
    
    user_history[user_id].append({"role": "user", "content": content})
    
    # Ограничение памяти (последние 10 сообщений)
    if len(user_history[user_id]) > 12:
        # Оставляем системный промпт [0] и последние 10 сообщений
        user_history[user_id] = [user_history[user_id][0]] + user_history[user_id][-10:]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            completion = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=user_history[user_id],
                temperature=0.7
            )
            report = completion.choices[0].message.content
            user_history[user_id].append({"role": "assistant", "content": report})
            
            # Отправляем ответ с кнопками
            await send_smart_message(message, report, reply_markup=get_analysis_keyboard())
            return 
            
        except Exception as e:
            error_msg = str(e)
            if "403" in error_msg or "connect" in error_msg.lower():
                logger.warning(f"⚠️ Попытка {attempt+1} (403). Жду...")
                await asyncio.sleep(1)
                continue
            else:
                await message.answer(f"⚠️ Ошибка: {e}")
                return

    await message.answer("⚠️ Прокси не отвечает. Попробуй позже.")

# --- ОБРАБОТЧИК КНОПОК ---
@dp.callback_query(F.data.startswith("btn_"))
async def callbacks_handler(callback: CallbackQuery):
    action = callback.data
    user_name = callback.from_user.first_name
    
    # Готовим команду для ИИ
    prompt = ""
    if action == "btn_summary":
        prompt = "Сделай максимально краткое резюме (summary) вышесказанного. Выдели главное жирным."
    elif action == "btn_risks":
        prompt = "Проанализируй текст выше и выдели списком потенциальные риски, ошибки или угрозы."
    elif action == "btn_translate":
        prompt = "Переведи последний ответ или текст на английский язык. Сохрани форматирование."
    elif action == "btn_advice":
        prompt = "Дай практический совет или рекомендацию по этому поводу."
    
    await callback.answer("Обрабатываю... 🧠") # Убираем часики на кнопке
    
    # Отправляем как новый запрос в ту же историю
    # callback.message - это сообщение, к которому прикреплена кнопка
    await run_mega_analysis(callback.message, prompt, user_name, is_button_click=True)

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ ---
@dp.message(F.document)
async def handle_doc(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    file_name = message.document.file_name.lower()
    
    if file_name.endswith(('.docx', '.pdf')):
        await message.answer(f"📂 **Вижу файл:** `{message.document.file_name}`\n⏳ Читаю и анализирую...", parse_mode="Markdown")
        file = await bot.get_file(message.document.file_id)
        path = f"temp_{message.document.file_id}_{message.document.file_name}"
        await bot.download_file(file.file_path, path)
        
        text = read_docx(path) if file_name.endswith('.docx') else read_pdf(path)
        
        if text.strip():
            await run_mega_analysis(message, f"Проанализируй документ и выдели ключевые моменты: {text[:20000]}", user_name)
        else:
            await message.answer("⚠️ Файл пуст.")
        
        if os.path.exists(path): os.remove(path)

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    text_lower = message.text.lower()

    if message.chat.type == "private" or "бот" in text_lower:
        clean_text = re.sub(r'(?i)\bбот\b', '', message.text).strip()
        
        if not clean_text and "бот" in text_lower:
            await message.answer("Я тут! 👋\nНажми кнопку ниже или задай вопрос.", reply_markup=get_analysis_keyboard())
            return

        final_text = clean_text if clean_text else message.text
        await run_mega_analysis(message, final_text, user_name)

# --- ЗАПУСК ---
async def main():
    logger.info("🚀 Бот Эдиус запущен: Markdown + Кнопки + Прокси")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
