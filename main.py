import asyncio
import logging
import re
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from transformers import pipeline

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
TOKEN = "8196658164:AAFbMgNqLPsou5pBm07OLH8lhAKbsQiRUig"
CHANNEL_ID = "@Ruins_of_Utopia"

bot = Bot(token=TOKEN)
dp = Dispatcher()
toxic_checker = None  # Загрузим позже в main

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name or "бро"
    await message.answer(f"Привет {user_name}!\nМожешь написать сообщение ⬇️")

# 1. Обработка НЕ-текстовых сообщений
@dp.message(~F.text)
async def not_text_handler(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        return
    
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] Юзер {message.from_user.full_name} (ID: {message.from_user.id}) прислал НЕ ТЕКСТ")
    await message.answer("Можно отправлять только текстовые сообщения!\nМожешь НАПИСАТЬ его сюда ⬇️")

# 2. Основная логика для текста
@dp.message(F.text)
async def process_message(message: types.Message):
    global toxic_checker
    now = datetime.now().strftime("%H:%M:%S")
    
    # Если ИИ еще не загрузился (на Render это может занять минуту)
    if toxic_checker is None:
        if message.chat.type not in ["group", "supergroup"]:
            await message.answer("Бот еще загружается, подожди пару секунд...")
        return

    # --- НЕЙРО-АНАЛИЗ ---
    result = toxic_checker(message.text)[0]
    label = result['label']
    score = result['score']
    is_toxic_log = "ДА" if label != 'non-toxic' else "НЕТ"

    is_group = message.chat.type in ["group", "supergroup"]

    print(f"[{now}] 1. {message.from_user.full_name}")
    print(f"[{now}] 2. {message.text}")
    print(f"[{now}] 3. {is_toxic_log} ({score:.4f})")
    
    if label != 'non-toxic' and score > 0.75:
        print("-" * 30)
        if is_group:
            try:
                await message.delete()
            except: pass
            return
        else:
            return await message.answer("Мы не отправляем сообщения с матами!\nМожешь написать другое ⬇️")

    if is_group:
        print("-" * 30)
        return

    print("-" * 30)
    try:
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
        await message.answer("❌ Ошибка отправки в канал.")

# 3. Обработка кнопки удаления
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
        await callback.answer("❌ Ошибка: пост уже удален.", show_alert=True)

# --- ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА ---
async def main():
    # 1. СНАЧАЛА ЗАПУСКАЕМ ВЕБ-СЕРВЕР (Render увидит порт сразу)
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    
    await site.start()
    print("--- Порт открыт ---")

    # 2. ТЕПЕРЬ ГРУЗИМ ТЯЖЕЛУЮ НЕЙРОНКУ
    print("--- Начинаю загрузку transformers ---")
    global toxic_checker
    try:
        # Это может занять время на слабом CPU Render
        toxic_checker = pipeline("text-classification", model="cointegrated/rubert-tiny-toxicity")
        print("--- ИИ успешно загружен и готов к работе! ---")
    except Exception as e:
        print(f"--- КРИТИЧЕСКАЯ ОШИБКА ЗАГРУЗКИ ИИ: {e} ---")

    # 3. ЗАПУСКАЕМ БОТА (Polling)
    print("--- Бот запущен в режиме Polling ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
