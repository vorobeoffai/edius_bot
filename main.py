import asyncio
import os
import docx
import re
import PyPDF2
import logging
import httpx
from aiogram import Bot, Dispatcher, types, F
from groq import Groq

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8502301153:AAEoqXKhKsB7-RJfhux575jqBtV74dwAUes'
GROQ_KEY = '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'

# --- 🇺🇸 ТВОЙ ПРОКСИ ---
PROXY_URL = "socks5://rP4AjF:Q9TK72@45.145.57.210:11121"

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    logger.info("🔌 Подключаюсь к USA Proxy...")
    
    # ВОТ ЗДЕСЬ БЫЛА ОШИБКА. ТЕПЕРЬ ТУТ 'proxy' (без S)
    proxy_client = httpx.Client(proxy=PROXY_URL)
    
    groq_client = Groq(api_key=GROQ_KEY, http_client=proxy_client)
    logger.info(f"✅ Groq успешно настроен через IP 45.145.57.210")

    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    
except Exception as e:
    logger.critical(f"🔥 Ошибка настройки: {e}")
    exit(1)

user_history = {}
CONTEXT_LIMIT = 1000 

# --- СИСТЕМНАЯ РОЛЬ ---
def get_system_prompt(user_name):
    return (
        f"Твое имя: Бот Эдиус. Ты — интеллектуальный ассистент и эксперт ✨. "
        f"Твой собеседник: {user_name}. Обращайся к нему по имени.\n"
        "📝 СТИЛЬ: Максимально развернутые ответы 📚."
    )

# --- ЧТЕНИЕ ФАЙЛОВ ---
def read_docx(path):
    try:
        doc = docx.Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception: return ""

def read_pdf(path):
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t: text += t + "\n"
        return text
    except Exception: return ""

# --- АНАЛИЗ ---
async def run_mega_analysis(message, content, user_name):
    await bot.send_chat_action(message.chat.id, action="typing")
    user_id = message.from_user.id
    
    if user_id not in user_history:
        user_history[user_id] = [{"role": "system", "content": get_system_prompt(user_name)}]
    
    user_history[user_id].append({"role": "user", "content": content})
    if len(user_history[user_id]) > CONTEXT_LIMIT: user_history[user_id].pop(1)

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=user_history[user_id],
            temperature=0.7
        )
        report = completion.choices[0].message.content
        user_history[user_id].append({"role": "assistant", "content": report})
        
        if len(report) > 4000:
            for x in range(0, len(report), 4000):
                await message.answer(report[x:x+4000])
        else:
            await message.answer(report)
    except Exception as e:
        logger.error(f"Groq Error: {e}")
        await message.answer(f"⚠️ Ошибка: {e}")

# --- ОБРАБОТЧИКИ ---
@dp.message(F.document)
async def handle_doc(message: types.Message):
    path = f"temp_{message.document.file_name}"
    await bot.download(message.document, destination=path)
    try:
        text = read_docx(path) if path.endswith('.docx') else read_pdf(path)
        if text.strip():
            await run_mega_analysis(message, f"Проанализируй: {text[:18000]}", message.from_user.first_name)
        else:
            await message.answer("⚠️ Файл пуст.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        if os.path.exists(path): os.remove(path)

@dp.message(F.text)
async def handle_text(message: types.Message):
    await run_mega_analysis(message, message.text, message.from_user.first_name)

async def main():
    logger.info("🚀 Бот Эдиус запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
