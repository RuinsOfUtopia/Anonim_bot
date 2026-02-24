import asyncio
import logging
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from transformers import pipeline
import os



# --- ЛОКАЛЬНЫЙ ИИ (Ryzen 7 5700G) ---
toxic_checker = pipeline("text-classification", model="cointegrated/rubert-tiny-toxicity")

# --- НАСТРОЙКИ ---
TOKEN = "8196658164:AAFbMgNqLPsou5pBm07OLH8lhAKbsQiRUig"
CHANNEL_ID = "@Ruins_of_Utopia"

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def handle_ping(request):
    return web.Response(text="Bot is alive!")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name or "бро"
    await message.answer(f"Привет {user_name}!\nМожешь написать сообщение ⬇️")

# 1. Обработка НЕ-текстовых сообщений
@dp.message(~F.text)
async def not_text_handler(message: types.Message):
    # В ГРУППЕ: Игнорируем медиа, ничего не пишем
    if message.chat.type in ["group", "supergroup"]:
        return
    
    # В ЛИЧКЕ: Твоя оригинальная фраза и логи
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] Юзер {message.from_user.full_name} (ID: {message.from_user.id}) прислал НЕ ТЕКСТ")
    await message.answer("Можно отправлять только текстовые сообщения!\nМожешь НАПИСАТЬ его сюда ⬇️")

# 2. Основная логика для текста
@dp.message(F.text)
async def process_message(message: types.Message):
    now = datetime.now().strftime("%H:%M:%S")
    
    # --- НЕЙРО-АНАЛИЗ ---
    result = toxic_checker(message.text)[0]
    label = result['label']
    score = result['score']
    is_toxic_log = "ДА" if label != 'non-toxic' else "НЕТ"

    is_group = message.chat.type in ["group", "supergroup"]

    # ЛОГИРОВАНИЕ (как ты просил: 1. Кто, 2. Что, 3. Вероятность)
    print(f"[{now}] 1. {message.from_user.full_name}")
    print(f"[{now}] 2. {message.text}")
    print(f"[{now}] 3. {is_toxic_log} ({score:.4f})")
    
    # Если найден МАТ (порог 0.75)
    if label != 'non-toxic' and score > 0.75:
        print("-" * 30)
        if is_group:
            try:
                await message.delete() # В ГРУППЕ УДАЛЯЕМ
            except: pass
            return
        else:
            # В ЛИЧКЕ НЕ УДАЛЯЕМ (твоя фраза)
            return await message.answer("Мы не отправляем сообщения с матами!\nМожешь написать другое ⬇️")

    # Если ЧИСТО и это ГРУППА — просто выходим
    if is_group:
        print("-" * 30)
        return

    # Если ЧИСТО и это ЛИЧКА — отправляем в канал (твои логи и фразы)
    print("-" * 30)
    try:
        # Отправка в канал
        sent_post = await bot.send_message(
            chat_id=CHANNEL_ID, 
            text=f"❔Кто-то пишет❔\n\n{message.text}",
            parse_mode="Markdown"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="или удалить это", callback_data=f"del_{sent_post.message_id}")
        
        await message.answer(
            "Сообщение отправлено!\nМожешь написать новое ⬇️",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка отправки в канал. Проверь права админа.")

# 3. Обработка кнопки удаления (твои фразы)
@dp.callback_query(F.data.startswith("del_"))
async def delete_callback(callback: types.CallbackQuery):
    try:
        post_id = int(callback.data.split("_")[1])
        await bot.delete_message(chat_id=CHANNEL_ID, message_id=post_id)
        
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Пост {post_id} удален пользователем {callback.from_user.full_name}")

        await callback.message.edit_text("Сообщение удалено из канала.\nМожешь написать другое ⬇️")
        await callback.answer("Удалено!") 
    except Exception as e:
        logging.error(f"Ошибка удаления: {e}")
        await callback.answer("❌ Ошибка: пост уже удален или прошло >48ч.", show_alert=True)

async def main():
    # Настройка веб-сервера для Render
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Берем порт, который дает Render, или 8080 локально
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    print(f"Веб-сервер запущен на порту {port}")
    
    # Запускаем и веб-сервер, и бота одновременно
    await site.start()
    await dp.start_polling(bot)
