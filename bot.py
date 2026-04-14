import asyncio
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import os

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "8598128447:AAHupd0ltwgCOt592dPu09sKswEjGtMK3Lo")
ADMIN_ID = 123456789  # ЗАМЕНИ НА СВОЙ ID (узнай у @userinfobot)

# Тестовые реквизиты
CARD_NUMBER = "1234 5678 9012 3456"
CARD_HOLDER = "IVAN IVANOV"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("unigate.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    subscription_end TEXT,
    pending_payment INTEGER DEFAULT 0,
    username TEXT,
    first_name TEXT
)
""")
conn.commit()

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🛡️ Получить ключ")
    builder.button(text="💳 Тарифы")
    builder.button(text="👤 Профиль")
    builder.button(text="📞 Поддержка")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def tariffs_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="1 месяц — 200₽", callback_data="tariff_1")
    builder.button(text="3 месяца — 500₽", callback_data="tariff_3")
    builder.button(text="6 месяцев — 900₽", callback_data="tariff_6")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

def copy_keyboard(connection_string):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать ключ", copy_text=connection_string)
    builder.button(text="◀️ В меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

def payment_keyboard(amount, months, user_id):
    text = f"Переведи {amount}₽ на карту {CARD_NUMBER}\nПолучатель: {CARD_HOLDER}\nКомментарий: {user_id}"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать реквизиты", copy_text=text)
    builder.button(text="✅ Я оплатил", callback_data=f"paid_{months}")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_test_key(user_id):
    return f"vless://test-uuid@{user_id}.example.com:443?type=tcp&security=reality&pbk=test&fp=chrome&sni=google.com&sid=test#UniGate_{user_id}"

# ========== ПРОФИЛЬ ==========
@dp.message(lambda m: m.text == "👤 Профиль")
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "нет"
    first_name = message.from_user.first_name or ""
    
    cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        end_date = datetime.fromisoformat(result[0])
        if end_date > datetime.now():
            days_left = (end_date - datetime.now()).days
            status = f"✅ Активна (осталось {days_left} дн.)"
            builder = InlineKeyboardBuilder()
            builder.button(text="🔄 Продлить подписку", callback_data="extend")
            builder.button(text="◀️ В меню", callback_data="back_to_menu")
            builder.adjust(1)
            reply_markup = builder.as_markup()
        else:
            status = "❌ Истекла"
            reply_markup = None
    else:
        status = "❌ Нет активной подписки"
        reply_markup = None
    
    profile_text = (
        f"👤 **Ваш профиль UniGate**\n\n"
        f"🆔 Telegram ID: `{user_id}`\n"
        f"📝 Имя: {first_name}\n"
        f"🔹 Username: @{username}\n\n"
        f"📅 Статус подписки: {status}"
    )
    
    await message.answer(profile_text, parse_mode="Markdown", reply_markup=reply_markup)

@dp.callback_query(lambda c: c.data == "extend")
async def extend_subscription(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💰 **Выбери тариф для продления:**",
        reply_markup=tariffs_keyboard()
    )
    await callback.answer()

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    cursor.execute("""
        INSERT INTO users (user_id, username, first_name) 
        VALUES (?, ?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET username = ?, first_name = ?
    """, (user_id, username, first_name, username, first_name))
    conn.commit()
    
    text = (
        "🚪 Добро пожаловать в UniGate!\n\n"
        "Это тестовая версия бота.\n"
        "Все функции работают.\n\n"
        "👇 Выбери действие:"
    )
    await message.answer(text, reply_markup=main_keyboard())

# ========== ПОЛУЧИТЬ КЛЮЧ ==========
@dp.message(lambda m: m.text == "🛡️ Получить ключ")
async def get_key(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        end_date = datetime.fromisoformat(result[0])
        if end_date > datetime.now():
            connection_string = get_test_key(user_id)
            
            await message.answer(
                f"🔑 **Твой тестовый VPN-ключ:**\n\n"
                f"`{connection_string}`\n\n"
                f"⚠️ **Это тестовый ключ**\n\n"
                f"📱 **Инструкция:**\n"
                f"1. Нажми «📋 Скопировать ключ»\n"
                f"2. Открой Happ → «+» → «Из буфера обмена»",
                parse_mode="Markdown",
                reply_markup=copy_keyboard(connection_string)
            )
            return
    
    await message.answer(
        "❌ У тебя нет активной подписки.\n\n"
        "Нажми «💳 Тарифы», чтобы оплатить доступ."
    )

# ========== ТАРИФЫ ==========
@dp.message(lambda m: m.text == "💳 Тарифы")
async def show_tariffs(message: types.Message):
    await message.answer(
        "💰 **Наши тарифы:**\n\n"
        "• 1 месяц — 200₽\n"
        "• 3 месяца — 500₽\n"
        "• 6 месяцев — 900₽",
        parse_mode="Markdown",
        reply_markup=tariffs_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("tariff_"))
async def select_tariff(callback: types.CallbackQuery):
    tariff = callback.data.split("_")[1]
    prices = {"1": 200, "3": 500, "6": 900}
    amount = prices.get(tariff, 200)
    months = int(tariff)
    user_id = callback.from_user.id
    
    cursor.execute("""
        INSERT INTO users (user_id, pending_payment) 
        VALUES (?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET pending_payment = ?
    """, (user_id, months, months))
    conn.commit()
    
    text = (
        f"💳 **Оплата {months} месяц(ев) — {amount}₽**\n\n"
        f"**Реквизиты для перевода:**\n"
        f"Карта: `{CARD_NUMBER}`\n"
        f"Получатель: {CARD_HOLDER}\n"
        f"Сумма: {amount}₽\n"
        f"**Комментарий:** `{user_id}`"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=payment_keyboard(amount, months, user_id)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def payment_received(callback: types.CallbackQuery):
    months = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    prices = {1: 200, 3: 500, 6: 900}
    amount = prices.get(months, 200)
    
    await bot.send_message(
        ADMIN_ID,
        f"💰 **НОВАЯ ОПЛАТА**\n\n"
        f"👤 Пользователь: [{user_id}](tg://user?id={user_id})\n"
        f"📆 Тариф: {months} месяц(ев)\n"
        f"💵 Сумма: {amount}₽\n\n"
        f"✅ После проверки введи:\n"
        f"`/activate {user_id} {months}`",
        parse_mode="Markdown"
    )
    
    await callback.message.edit_text(
        "✅ **Заявка на оплату отправлена!**\n\n"
        "Администратор проверит перевод и активирует подписку."
    )
    await callback.answer()

# ========== ПОДДЕРЖКА ==========
@dp.message(lambda m: m.
            text == "📞 Поддержка")
async def support_command(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Написать", url="https://t.me/unisupport")
    await message.answer("📞 По вопросам пиши сюда:", reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await start_command(callback.message)
    await callback.answer()

# ========== АДМИН-КОМАНДА ==========
@dp.message(Command("activate"))
async def activate_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет прав")
        return
    
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❌ Формат: /activate user_id месяцев")
        return
    
    _, user_id, months = parts
    user_id = int(user_id)
    months = int(months)
    
    end_date = datetime.now() + timedelta(days=30 * months)
    cursor.execute("""
        INSERT INTO users (user_id, subscription_end, pending_payment) 
        VALUES (?, ?, 0) 
        ON CONFLICT(user_id) DO UPDATE SET subscription_end = ?, pending_payment = 0
    """, (user_id, end_date.isoformat(), end_date.isoformat()))
    conn.commit()
    
    connection_string = get_test_key(user_id)
    
    await bot.send_message(
        user_id,
        f"✅ **Подписка активирована на {months} месяц(ев)!**\n\n"
        f"🔑 **Твой тестовый VPN-ключ:**\n"
        f"`{connection_string}`\n\n"
        f"📱 **Инструкция:**\n"
        f"1. Нажми «📋 Скопировать ключ»\n"
        f"2. Открой приложение **Happ**\n"
        f"3. Нажми «+» → «Из буфера обмена»",
        parse_mode="Markdown",
        reply_markup=copy_keyboard(connection_string)
    )
    
    await message.answer(f"✅ Подписка активирована для {user_id} на {months} месяц(ев)")

# ========== ЗАПУСК ==========
async def main():
    print("✅ Тестовый бот UniGate запущен!")
    await dp.start_polling(bot)

if name == "__main__":
    asyncio.run(main())
