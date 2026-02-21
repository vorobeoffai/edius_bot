import asyncio
import os
import docx
import re
import PyPDF2
import logging
import httpx  # Библиотека для работы с интернетом и прокси
from aiogram import Bot, Dispatcher, types, F
from groq import Groq

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8502301153:AAEoqXKhKsB7-RJfhux575jqBtV74dwAUes'
GROQ_KEY = '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'

# --- 🇺🇸 ТВОЙ SOCKS5 ПРОКСИ ---
# Я вставил твои данные: логин rP4AjF, пароль Q9TK72
PROXY_URL = "socks5://rP4AjF:Q9TK72@45.145.57.210:11121"

# Настройка логирования (чтобы видеть в консоли, что происходит)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    logger.info("🔌 Настраиваю соединение через USA Proxy...")
    
    # 1. Создаем специального "почтальона" (http_client), который ходит через твой прокси
    # Мы используем его ТОЛЬКО для Groq, так как Telegram обычно работает и так.
    proxy_client = httpx.Client(proxies=PROXY_URL)
    
    # 2. Подключаем мозг (Groq) через этого "почтальона"
    groq_client = Groq(api_key=GROQ_KEY, http_client=proxy_client)
    logger.info(f"✅ Groq успешно настроен через IP 45.145.57.210")

    # 3. Инициализируем бота
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    
except Exception as e:
    logger.critical(f"🔥 Ошибка настройки прокси: {e}")
    # Если прокси не работает, программа остановится
    exit(1)

user_history = {}
CONTEXT_LIMIT = 1000 

# --- СИСТЕМНАЯ РОЛЬ ---
def get_system_prompt(user_name):
    return (
        f"Твое имя: Бот Эдиус. Ты — интеллектуальный ассистент и эксперт ✨. "
        f"Твой собеседник: {user_name}. Обращайся к нему по имени.\n\n"
        "🔴 САМОИДЕНТИФИКАЦИЯ:\n"
        "1. Создатель: Виталий Воробьев. Никогда не упоминай другие компании.\n"
        "2. ПРИВЕТСТВИЕ: Только один раз в начале диалога.\n\n"
        "📝 СТИЛЬ: Максимально развернутые ответы 📚, использование эмодзи ✅💡🚀."
    )

# --- ФУНКЦИИ ЧТЕНИЯ ФАЙЛОВ ---
def read_docx(path):
    try:
        doc = docx.Document(path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        logger.error(f"Ошибка чтения DOCX: {e}")
        return ""

def read_pdf(path):
    text = ""
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text
    except Exception as e:
        logger.error(f"Ошибка чтения PDF: {e}")
        return ""

# --- ЯДРО ОБРАБОТКИ (С ПРОКСИ) ---
async def run_mega_analysis(message, content, user_name):
    await bot.send_chat_action(message.chat.id, action="typing")
    user_id = message.from_user.id
    
    if user_id not in user_history:
        user_history[user_id] = [{"role": "system", "content": get_system_prompt(user_name)}]
    
    user_history[user_id].append({"role": "user", "content": content})
    if len(user_history[user_id]) > CONTEXT_LIMIT + 1:
        user_history[user_id].pop(1)

    try:
        # Этот запрос пойдет через твой прокси в США
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
        logger.error(f"Ошибка Groq API: {e}")
        await message.answer(f"⚠️ Ошибка связи с нейросетью: {str(e)}")

# --- ОБРАБОТЧИКИ ---
@dp.message(F.document)
async def handle_doc(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    file_name = message.document.file_name.lower()
    
    if file_name.endswith(('.docx', '.pdf')):
        await message.answer(f"📂 Получил файл **{message.document.file_name}**. Читаю... ⏳")
        file = await bot.get_file(message.document.file_id)
        path = f"temp_{message.document.file_id}_{message.document.file_name}"
        
        await bot.download_file(file.file_path, path)
        
        try:
            text = ""
            if file_name.endswith('.docx'):
                text = read_docx(path)
            else:
                text = read_pdf(path)
            
            if not text.strip():
                await message.answer("⚠️ Файл пуст.")
                return

            await run_mega_analysis(message, f"Проанализируй документ: {text[:18000]}", user_name)
        except Exception as e:
            logger.error(f"Ошибка файла: {e}")
            await message.answer("❌ Не удалось прочитать файл.")
        finally:
            if os.path.exists(path):
                os.remove(path)
    else:
        await message.answer("Я понимаю только **.docx** и **.pdf**.")

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    if re.search(r'(?i)\b(бот|bot)\b', message.text) or message.chat.type == "private":
        clean_query = re.sub(r'(?i)\b(бот|bot)\b', '', message.text).strip()
        final_text = clean_query if clean_query else message.text
        await run_mega_analysis(message, final_text, user_name)

# --- ЗАПУСК ---
async def main():
    logger.info("🚀 Бот Эдиус запускается через USA Proxy...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
