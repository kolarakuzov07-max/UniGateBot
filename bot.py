import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import os

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8598128447:AAEASGWXHgHVmkKnK0eEX83p6CYe9yLp2JA"
ADMIN_USERNAME = "p2pshil"
BOT_USERNAME = "UniGates_bot"

CARD_NUMBER = "2200 1523 0320 4112"
CARD_HOLDER = "SAVELII MINKOV"

# ========== ЦЕНЫ ТАРИФОВ ==========
PRICES = {1: 100, 2: 180, 3: 270}

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("unigate.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT
)
""")
conn.commit()

# ========== ХРАНИЛИЩА ==========
main_message_id = {}      # ID главного сообщения с меню
temp_messages = {}        # ID временных сообщений бота
user_messages = {}        # ID сообщений пользователя

async def delete_user_messages(user_id, chat_id):
    """Удаляет сообщения пользователя"""
    if user_id in user_messages:
        for msg_id in user_messages[user_id]:
            try:
                await bot.delete_message(chat_id, msg_id)
            except:
                pass
        user_messages[user_id] = []

async def save_user_message(user_id, message_id):
    """Сохраняет ID сообщения пользователя"""
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(message_id)
    if len(user_messages[user_id]) > 10:
        user_messages[user_id] = user_messages[user_id][-10:]

async def delete_temp_messages(user_id, chat_id):
    """Удаляет временные сообщения бота"""
    if user_id in temp_messages:
        for msg_id in temp_messages[user_id]:
            try:
                await bot.delete_message(chat_id, msg_id)
            except:
                pass
        temp_messages[user_id] = []

async def save_temp_message(user_id, message_id):
    """Сохраняет ID временного сообщения бота"""
    if user_id not in temp_messages:
        temp_messages[user_id] = []
    temp_messages[user_id].append(message_id)
    if len(temp_messages[user_id]) > 10:
        temp_messages[user_id] = temp_messages[user_id][-10:]

async def save_main_message(user_id, message_id):
    """Сохраняет ID главного сообщения с меню"""
    main_message_id[user_id] = message_id

async def delete_all_messages(user_id, chat_id):
    """Удаляет всё: и сообщения пользователя, и временные сообщения бота"""
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="💳 Тарифы")
    builder.button(text="👤 Профиль")
    builder.button(text="📞 Поддержка")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def tariffs_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 1 месяц — 100₽ ⭐", callback_data="tariff_1")
    builder.button(text="🔥 2 месяца — 180₽ 🔥", callback_data="tariff_2")
    builder.button(text="💎 3 месяца — 270₽ 💎", callback_data="tariff_3")
    builder.adjust(1)
    return builder.as_markup()

# ========== ОБРАБОТЧИКИ ==========
@dp.callback_query(lambda c: c.data and c.data.startswith("tariff_"))
async def select_tariff(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    # Сохраняем сообщение пользователя (нажатие на кнопку)
    await save_user_message(user_id, callback.message.message_id)
    
    # Удаляем всё
    await delete_all_messages(user_id, chat_id)
    
    tariff = callback.data.split("_")[1]
    months = int(tariff)
    amount = PRICES.get(months, 100)
    
    text = (
        f"💳 **Оплата {months} месяц(ев) — {amount}₽**\n\n"
        f"**Реквизиты для перевода:**\n"
        f"📌 Карта: `{CARD_NUMBER}`\n"
        f"📌 Получатель: `{CARD_HOLDER}`\n"
        f"📌 Сумма: {amount}₽\n"
        f"📌 Комментарий: `{user_id}`\n\n"
        f"✅ **После перевода** напиши @{ADMIN_USERNAME} и пришли чек."
    )
    
    msg = await callback.message.answer(text, parse_mode="Markdown")
    await save_temp_message(user_id, msg.message_id)
    await callback.answer()

@dp.message(lambda m: m.text == "👤 Профиль")
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or "нет"
    first_name = message.from_user.first_name or ""
    
    # Сохраняем сообщение пользователя
    await save_user_message(user_id, message.message_id)
    
    # Удаляем всё
    await delete_all_messages(user_id, chat_id)
    
    profile_text = (
        f"👤 **Ваш профиль UniGate**\n\n"
        f"🆔 **Telegram ID:** `{user_id}`\n"
        f"📝 **Имя:** {first_name}\n"
        f"🔹 **Username:** @{username}\n\n"
        f"💡 **Как получить доступ:**\n"
        f"1. Нажми «💳 Тарифы»\n"
        f"2. Выбери тариф\n"
        f"3. Оплати и напиши @{ADMIN_USERNAME}"
    )
    
    try:
        with open("profile.jpg", "rb") as photo:
            msg = await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="profile.jpg"),
                caption=profile_text,
                parse_mode="Markdown"
            )
            await save_temp_message(user_id, msg.message_id)
    except:
        msg = await message.answer(profile_text, parse_mode="Markdown")
        await save_temp_message(user_id, msg.message_id)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Сохраняем сообщение пользователя
    await save_user_message(user_id, message.message_id)
    
    # Удаляем всё
    await delete_all_messages(user_id, chat_id)
    
    # Если есть сохранённое главное сообщение, удаляем его
    if user_id in main_message_id:
        try:
            await bot.delete_message(chat_id, main_message_id[user_id])
        except:
            pass
    
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", (user_id, username, first_name))
    conn.commit()
    
    text = (
        "🚪 **Добро пожаловать в UniGate!**\n\n"
        "✨ **Почему выбирают нас:**\n"
        "• 🚀 **Молниеносная скорость**\n"
        "• 🔒 **Абсолютная приватность**\n"
        "• 🌍 **Доступ к любым сайтам**\n"
        "• 📱 **Один клик** для подключения\n\n"
        "🎁 **Первый месяц — всего 100₽!**\n\n"
        "👇 **Выбери действие:**"
    )
    
    try:
        with open("welcome.jpg", "rb") as photo:
            msg = await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="welcome.jpg"),
                caption=text,
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
            await save_main_message(user_id, msg.message_id)
    except:
        msg = await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard())
        await save_main_message(user_id, msg.message_id)

@dp.message(lambda m: m.text == "💳 Тарифы")
async def show_tariffs(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Сохраняем сообщение пользователя
    await save_user_message(user_id, message.message_id)
    
    # Удаляем всё
    await delete_all_messages(user_id, chat_id)
    
    text = "💰 **Наши тарифы:**\n\n⭐ 1 месяц — 100₽\n🔥 2 месяца — 180₽\n💎 3 месяца — 270₽"
    
    try:
        with open("tariffs.jpg", "rb") as photo:
            msg = await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="tariffs.jpg"),
                caption=text,
                parse_mode="Markdown",
                reply_markup=tariffs_keyboard()
            )
            await save_temp_message(user_id, msg.message_id)
    except:
        msg = await message.answer(text, parse_mode="Markdown", reply_markup=tariffs_keyboard())
        await save_temp_message(user_id, msg.message_id)

@dp.message(lambda m: m.text == "📞 Поддержка")
async def support_command(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Сохраняем сообщение пользователя
    await save_user_message(user_id, message.message_id)
    
    # Удаляем всё
    await delete_all_messages(user_id, chat_id)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Написать", url=f"https://t.me/{ADMIN_USERNAME}")
    builder.adjust(1)
    
    text = f"📞 **Служба поддержки UniGate**\n\nВозникли проблемы? Напиши @{ADMIN_USERNAME}!"
    
    try:
        with open("support.jpg", "rb") as photo:
            msg = await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="support.jpg"),
                caption=text,
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
            await save_temp_message(user_id, msg.message_id)
    except:
        msg = await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
        await save_temp_message(user_id, msg.message_id)

# ========== ЗАПУСК ==========
async def main():
    print("✅ Бот UniGate запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
