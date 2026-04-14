import asyncio
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import os

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8598128447:AAHupd0ltwgCOt592dPu09sKswEjGtMK3Lo"
ADMIN_IDS = [1446300344, 2051767977]  # СПИСОК АДМИНОВ
BOT_USERNAME = "UniGates_bot"

# РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ
CARD_NUMBER = "2200 1523 0320 4112"
CARD_HOLDER = "SAVELII MINKOV"

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
    first_name TEXT,
    referrer_id INTEGER DEFAULT 0,
    referral_count INTEGER DEFAULT 0
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
    builder.button(text="1 месяц — 100₽", callback_data="tariff_1")
    builder.button(text="2 месяца — 180₽", callback_data="tariff_2")
    builder.button(text="3 месяца — 250₽", callback_data="tariff_3")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

def copy_keyboard(connection_string):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать ключ", callback_data="copy_key")
    builder.button(text="◀️ В меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

def payment_keyboard(amount, months, user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать реквизиты", callback_data="copy_payment")
    builder.button(text="✅ Я оплатил", callback_data=f"paid_{months}")
    builder.button(text="◀️ Назад", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_test_key(user_id):
    return f"vless://test-uuid@{user_id}.example.com:443?type=tcp&security=reality&pbk=test&fp=chrome&sni=google.com&sid=test#UniGate_{user_id}"

# ========== КОПИРОВАНИЕ ==========
@dp.callback_query(lambda c: c.data == "copy_key")
async def copy_key(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    key = get_test_key(user_id)
    await callback.answer(f"🔑 Ключ скопирован!\n\n{key}", show_alert=True)

@dp.callback_query(lambda c: c.data == "copy_payment")
async def copy_payment(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT pending_payment FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    months = result[0] if result else 1
    prices = {1: 100, 2: 180, 3: 250}
    amount = prices.get(months, 100)
    
    text = f"Переведи {amount}₽ на карту {CARD_NUMBER}\nПолучатель: {CARD_HOLDER}\nКомментарий: {user_id}"
    await callback.answer(f"💳 Реквизиты скопированы!\n\n{text}", show_alert=True)

# ========== ПРОФИЛЬ С РЕФЕРАЛКАМИ ==========
@dp.message(lambda m: m.text == "👤 Профиль")
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "нет"
    first_name = message.from_user.first_name or ""
    
    cursor.execute("SELECT subscription_end, referral_count FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        end_date = datetime.fromisoformat(result[0])
        if end_date > datetime.now():
            days_left = (end_date - datetime.now()).days
            status = f"✅ Активна (осталось {days_left} дн.)"
            builder = InlineKeyboardBuilder()
           
            builder.button(text="◀️ В меню", callback_data="back_to_menu")
            builder.adjust(1)
            reply_markup = builder.as_markup()
        else:
            status = "❌ Истекла"
            reply_markup = None
    else:
        status = "❌ Нет активной подписки"
        reply_markup = None
    
    referral_count = result[1] if result else 0
    referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    profile_text = (
        f"👤 **Ваш профиль UniGate**\n\n"
        f"🆔 Telegram ID: `{user_id}`\n"
        f"📝 Имя: {first_name}\n"
        f"🔹 Username: @{username}\n\n"
        f"📅 Статус подписки: {status}\n\n"
        f"👥 **Реферальная система:**\n"
        f"└ Приглашено друзей: **{referral_count}**\n"
        f"└ Ваша ссылка: `{referral_link}`\n\n"
        f"💡 **Как это работает:**\n"
        f"Пригласи друга по ссылке → он получит скидку, а ты бонус!"
    )
    
    try:
        with open("profile.jpg", "rb") as photo:
            await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="profile.jpg"),
                caption=profile_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
    except:
        await message.answer(profile_text, parse_mode="Markdown", reply_markup=reply_markup)

# ========== ОБРАБОТКА РЕФЕРАЛЬНОЙ ССЫЛКИ ==========
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
        except:
            pass
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    existing = cursor.fetchone()
    
    if not existing:
        cursor.execute("INSERT INTO users (user_id, username, first_name, referrer_id) VALUES (?, ?, ?, ?)", (user_id, username, first_name, referrer_id))
        if referrer_id and referrer_id != user_id:
            cursor.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?", (referrer_id,))
            await bot.send_message(referrer_id, f"🎉 По вашей ссылке зарегистрировался новый пользователь @{username}!")
        conn.commit()
    else:
        cursor.execute("UPDATE users SET username = ?, first_name = ? WHERE user_id = ?", (username, first_name, user_id))
        conn.commit()
    
    text = "🚪 Добро пожаловать в UniGate!\n\n👇 Выбери действие:"
    await message.answer(text, reply_markup=main_keyboard())

@dp.callback_query(lambda c: c.data == "extend")
async def extend_subscription(callback: types.CallbackQuery):
    await callback.message.edit_text("💰 **Выбери тариф для продления:**", reply_markup=tariffs_keyboard())
    await callback.answer()

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
            await message.answer(f"🔑 **Твой тестовый VPN-ключ:**\n\n`{connection_string}`\n\n📱 **Инструкция:**\n1. Нажми «📋 Скопировать ключ»\n2. Открой Happ → «+» → «Из буфера обмена»", parse_mode="Markdown", reply_markup=copy_keyboard(connection_string))
            return
    
    await message.answer("❌ У тебя нет активной подписки.\n\nНажми «💳 Тарифы», чтобы оплатить доступ.")

# ========== ТАРИФЫ ==========
@dp.message(lambda m: m.text == "💳 Тарифы")
async def show_tariffs(message: types.Message):
    text = "💰 **Наши тарифы:**\n\n• 1 месяц — 100₽\n• 2 месяца — 180₽\n• 3 месяца — 250₽"
    await message.
    answer(text, parse_mode="Markdown", reply_markup=tariffs_keyboard())

@dp.callback_query(lambda c: c.data.startswith("tariff_"))
async def select_tariff(callback: types.CallbackQuery):
    tariff = callback.data.split("_")[1]
    prices = {"1": 100, "2": 180, "3": 250}
    amount = prices.get(tariff, 100)
    months = int(tariff)
    user_id = callback.from_user.id
    
    cursor.execute("INSERT INTO users (user_id, pending_payment) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET pending_payment = ?", (user_id, months, months))
    conn.commit()
    
    text = f"💳 Оплата {months} месяц(ев) — {amount}₽**\n\n**Реквизиты:**\nКарта: `{CARD_NUMBER}`\nПолучатель: {CARD_HOLDER}\nСумма: {amount}₽\n**Комментарий: `{user_id}`"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=payment_keyboard(amount, months, user_id))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("paid_"))
async def payment_received(callback: types.CallbackQuery):
    months = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    prices = {1: 100, 2: 180, 3: 250}
    amount = prices.get(months, 100)
    
    # Отправляем уведомление ВСЕМ админам
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"💰 **НОВАЯ ОПЛАТА**\n\n👤 Пользователь: [{user_id}](tg://user?id={user_id})\n📆 Тариф: {months} месяц(ев)\n💵 Сумма: {amount}₽\n\n✅ После проверки введи:\n`/activate {user_id} {months}`", parse_mode="Markdown")
    
    await callback.message.edit_text("✅ **Заявка на оплату отправлена!**\n\nАдминистратор проверит перевод и активирует подписку.")
    await callback.answer()

# ========== ПОДДЕРЖКА ==========
@dp.message(lambda m: m.text == "📞 Поддержка")
async def support_command(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Написать", url="https://t.me/UniGatesSupport")
    await message.answer("📞 По вопросам пиши сюда:", reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await start_command(callback.message)
    await callback.answer()

# ========== АДМИН-КОМАНДА ==========
@dp.message(Command("activate"))
async def activate_user(message: types.Message):
    # Проверяем, что команду пишет админ из списка
    if message.from_user.id not in ADMIN_IDS:
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
    cursor.execute("INSERT INTO users (user_id, subscription_end, pending_payment) VALUES (?, ?, 0) ON CONFLICT(user_id) DO UPDATE SET subscription_end = ?, pending_payment = 0", (user_id, end_date.isoformat(), end_date.isoformat()))
    conn.commit()
    
    connection_string = get_test_key(user_id)
    
    await bot.send_message(user_id, f"✅ **Подписка активирована на {months} месяц(ев)!**\n\n🔑 **Твой VPN-ключ:**\n`{connection_string}`\n\n📱 **Инструкция:**\n1. Нажми «📋 Скопировать ключ»\n2. Открой Happ → «+» → «Из буфера обмена»", parse_mode="Markdown", reply_markup=copy_keyboard(connection_string))
    
    await message.answer(f"✅ Подписка активирована для {user_id} на {months} месяц(ев)")

# ========== ЗАПУСК ==========
async def main():
    print("✅ Тестовый бот UniGate запущен!")
    await dp.start_polling(bot)

asyncio.run(main())
