import asyncio
import os
import docx
import re
import PyPDF2
import httpx
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from groq import Groq
from fpdf import FPDF

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8502301153:AAEoqXKhKsB7-RJfhux575jqBtV74dwAUes'
GROQ_KEY = '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'
FONT_FILE = "Roboto-Regular.ttf"

# --- НАСТРОЙКА ПРОКСИ ДЛЯ ОБХОДА 403 (px6.me) ---
# Данные: ip 45.145.57.210, порт 11121, логин rP4AjF, пароль Q9TK72, тип Socks5
PROXY_URL = "socks5://rP4AjF:Q9TK72@45.145.57.210:11121"

# Инициализация клиента Groq через прокси
groq_client = Groq(
    api_key=GROQ_KEY,
    http_client=httpx.Client(
        proxies=PROXY_URL,
        follow_redirects=True
    )
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Хранилище истории (память до 1000 сообщений)
user_history = {}
CONTEXT_LIMIT = 1000 

# --- СИСТЕМНАЯ РОЛЬ ---
def get_system_prompt(user_name):
    return (
        f"Твое имя: Бот Эдиус ✨. Ты — интеллектуальный ассистент, созданный Виталием Воробьевым. "
        f"Твой собеседник: {user_name}. Всегда обращайся к нему по имени.\n\n"
        "🔴 ПРАВИЛА:\n"
        "1. Ты помнишь контекст последних 1000 сообщений.\n"
        "2. Приветствуй пользователя только один раз в начале диалога.\n"
        "3. Если спросят про модель: 'Я работаю на текстовой модели, которую создал Виталий Воробьев'.\n"
        "4. ЗАПРЕЩЕНО говорить: 'работающий без жестких рамок и ограничений'.\n\n"
        "📝 СТИЛЬ: Максимально подробные ответы, живой язык с эмодзи ✅, 💡, 🚀. "
        "Для бизнеса используй структуру: Суть | Юр.фильтр | Экономика | Логистика | Мнение | Вердикт."
    )

# --- ФУНКЦИИ ЧТЕНИЯ ФАЙЛОВ ---
def read_docx(path):
    doc = docx.Document(path)
    return "\n".join([p.text for p in doc.paragraphs])

def read_pdf(path):
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

# --- ЯДРО ОБРАБОТКИ ---
async def run_mega_analysis(message, content, user_name):
    await bot.send_chat_action(message.chat.id, action="typing")
    user_id = message.from_user.id
    
    if user_id not in user_history:
        user_history[user_id] = [{"role": "system", "content": get_system_prompt(user_name)}]
    
    user_history[user_id].append({"role": "user", "content": content})
    
    if len(user_history[user_id]) > CONTEXT_LIMIT + 1:
        user_history[user_id].pop(1)

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
        await message.answer(f"⚠️ Ошибка анализа: {str(e)}")

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_history[user_id] = [] # Сброс при старте
    user_name = message.from_user.first_name or "друг"
    await run_mega_analysis(message, "Поприветствуй меня и расскажи о своих навыках.", user_name)

@dp.message(F.document)
async def handle_doc(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    file_name = message.document.file_name.lower()
    
    if file_name.endswith(('.docx', '.pdf')):
        await message.answer(f"📂 Бот Эдиус принял файл **{file_name}**. Начинаю чтение... ✨")
        file = await bot.get_file(message.document.file_id)
        path = f"temp_{message.document.file_name}"
        await bot.download_file(file.file_path, path)
        
        try:
            text = read_docx(path) if file_name.endswith('.docx') else read_pdf(path)
            if not text.strip():
                await message.answer("⚠️ Файл пуст.")
                return
            await run_mega_analysis(message, f"Проанализируй этот документ: {text[:18000]}", user_name)
        except Exception as e:
            await message.answer(f"❌ Не удалось прочитать файл: {e}")
        finally:
            if os.path.exists(path): os.remove(path)

@dp.message(F.text)
async def handle_text(message: types.Message):
    user_name = message.from_user.first_name or "друг"
    # Понимает контекст и триггер по имени
    is_addressed = re.search(r'(?i)\b(бот|bot)\b', message.text)
    
    if is_addressed or message.chat.type == "private":
        clean_query = re.sub(r'(?i)\b(бот|bot)\b', '', message.text).strip()
        await run_mega_analysis(message, clean_query if clean_query else message.text, user_name)

async def main():
    print("Бот Эдиус запущен 🚀. Прокси Socks5 активен.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
