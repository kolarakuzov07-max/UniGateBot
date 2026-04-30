import asyncio
import sqlite3
import json
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import os

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8598128447:AAELO9xBRUKx8cWVbIn_3kiQB1CglsALTZk"
ADMIN_IDS = [1446300344]
BOT_USERNAME = "UniGates_bot"

CARD_NUMBER = "2200 1523 0320 4112"
CARD_HOLDER = "SAVELII MINKOV"

# ========== НАСТРОЙКИ ПАНЕЛИ 3X-UI ==========
XUI_URL = "https://89.125.199.10:18184"
XUI_USERNAME = "jS0JFHvlsd"
XUI_PASSWORD = "a6qSCo055u"
INBOUND_ID = 14

SERVER_IP = "89.125.199.10"
PORT = 8443
PUBLIC_KEY = "mT5TlvgHgv3kinWWTdHByPWmDvLSDdscR2sHMBButlE"
SHORT_ID = "1049b659"
SNI = "rydervless.ru"
FLOW = "xtls-rprx-vision"

# ========== ЦЕНЫ ==========
PRICES = {1: 100, 2: 180, 3: 270}

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("unigate.db", check_same_thread=False)
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
    builder.button(text="🏠 Главное меню")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def tariffs_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ 1 месяц — 100₽ ⭐", callback_data="tariff_1")
    builder.button(text="🔥 2 месяца — 180₽ 🔥", callback_data="tariff_2")
    builder.button(text="💎 3 месяца — 270₽ 💎", callback_data="tariff_3")
    builder.adjust(1)
    return builder.as_markup()

def payment_keyboard(amount, months, user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать реквизиты", callback_data="copy_payment")
    builder.button(text="✅ Я оплатил", callback_data=f"paid_{months}")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

def copy_keyboard(connection_string):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать ключ", callback_data="copy_key")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

# ========== API 3X-UI ==========
async def create_xui_client(user_id: int, months: int):
    days = months * 30
    expiry_time = int((datetime.now() + timedelta(days=days)).timestamp() * 1000)
    email = f"user_{user_id}"

    client_config = {
        "email": email,
        "limitIp": 1,
        "totalGB": 0,
        "expiryTime": expiry_time,
        "enable": True,
        "flow": FLOW,
    }

    async with aiohttp.ClientSession() as session:
        login_data = {"username": XUI_USERNAME, "password": XUI_PASSWORD}
        try:
            async with session.post(f"{XUI_URL}/login", data=login_data, ssl=False) as login_resp:
                if login_resp.status != 200:
                    return None
        except:
            return None

        add_url = f"{XUI_URL}/panel/api/inbounds/addClient"
        payload = {
            "id": INBOUND_ID,
            "settings": json.dumps({"clients": [client_config]})
        }
        try:
            async with session.post(add_url, json=payload, ssl=False) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("success"):
                        vless_link = f"vless://{email}@{SERVER_IP}:{PORT}?type=tcp&security=reality&pbk={PUBLIC_KEY}&fp=chrome&sni={SNI}&sid={SHORT_ID}&flow={FLOW}#UniGate_{user_id}"
                        return vless_link
        except:
            return None
    return None

# ========== ОБРАБОТЧИКИ ==========
@dp.callback_query(lambda c: c.data == "copy_payment")
async def copy_payment(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT pending_payment FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    months = result[0] if result else 1
    amount = PRICES.get(months, 100)
    text = f"Переведи {amount}₽ на карту {CARD_NUMBER}\nПолучатель: {CARD_HOLDER}\nКомментарий: {user_id}"
    await callback.answer(f"💳 Реквизиты скопированы!\n\n{text}", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("tariff_"))
async def select_tariff(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tariff = callback.data.split("_")[1]
    months = int(tariff)
    amount = PRICES.get(months, 100)
    
    cursor.execute("INSERT INTO users (user_id, pending_payment) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET pending_payment = ?", (user_id, months, months))
    conn.commit()
    
    text = (f"💳 **Оплата {months} месяц(ев) — {amount}₽**\n\n"
            f"**Реквизиты для перевода:**\n"
            f"📌 Карта: `{CARD_NUMBER}`\n"
            f"📌 Получатель: `{CARD_HOLDER}`\n"
            f"📌 Сумма: {amount}₽\n"
            f"📌 Комментарий: `{user_id}`\n\n"
            f"✅ **После перевода** нажми кнопку «✅ Я оплатил».")
    
    # ОТПРАВЛЯЕМ НОВОЕ СООБЩЕНИЕ, а не редактируем
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=payment_keyboard(amount, months, user_id))
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("paid_"))
async def payment_received(callback: types.CallbackQuery):
    months = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    amount = PRICES.get(months, 100)
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"💰 **НОВАЯ ОПЛАТА**\n\n👤 Пользователь: [{user_id}](tg://user?id={user_id})\n📆 Тариф: {months} месяц(ев)\n💵 Сумма: {amount}₽\n\n✅ После проверки введи:\n`/activate {user_id} {months}`", parse_mode="Markdown")
    
    await callback.message.answer("✅ **Заявка на оплату отправлена!**\n\nАдминистратор проверит перевод и активирует подписку.")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "copy_key")
async def copy_key(callback: types.CallbackQuery):
    await callback.answer("🔑 Ключ скопирован!", show_alert=True)

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await start_command(callback.message)
    await callback.answer()

# ========== ПРОФИЛЬ ==========
@dp.message(lambda m: m.text == "👤 Профиль")
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        end_date = datetime.fromisoformat(result[0])
        if end_date > datetime.now():
            days_left = (end_date - datetime.now()).days
            status = f"✅ Активна (осталось {days_left} дн.)"
        else:
            status = "❌ Истекла"
    else:
        status = "❌ Нет активной подписки"
    
    text = f"👤 **Ваш профиль UniGate**\n\n📅 Статус подписки: {status}"
    await message.answer(text, parse_mode="Markdown")

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    
    text = "🚪 **Добро пожаловать в UniGate!**\n\n👇 **Выбери действие:**"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ========== ГЛАВНОЕ МЕНЮ ==========
@dp.message(lambda m: m.text == "🏠 Главное меню")
async def main_menu(message: types.Message):
    await start_command(message)

# ========== ПОЛУЧИТЬ КЛЮЧ ==========
@dp.message(lambda m: m.text == "🛡️ Получить ключ")
async def get_key(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        end_date = datetime.fromisoformat(result[0])
        if end_date > datetime.now():
            vless_link = await create_xui_client(user_id, 1)
            if vless_link:
                await message.answer(
                    f"🔑 **Твой VPN-ключ:**\n\n`{vless_link}`\n\n📱 **Инструкция:**\n1. Нажми «📋 Скопировать ключ»\n2. Открой Happ → «+» → «Из буфера обмена»",
                    parse_mode="Markdown",
                    reply_markup=copy_keyboard(vless_link)
                )
                return
    await message.answer("❌ **У тебя нет активной подписки.**\n\nНажми «💳 Тарифы», чтобы оплатить доступ.", parse_mode="Markdown")

# ========== ТАРИФЫ ==========
@dp.message(lambda m: m.text == "💳 Тарифы")
async def show_tariffs(message: types.Message):
    text = "💰 **Наши тарифы:**\n\n⭐ 1 месяц — 100₽\n🔥 2 месяца — 180₽\n💎 3 месяца — 270₽"
    await message.answer(text, parse_mode="Markdown", reply_markup=tariffs_keyboard())

# ========== ПОДДЕРЖКА ==========
@dp.message(lambda m: m.text == "📞 Поддержка")
async def support_command(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Написать", url="https://t.me/UniGatesSupport")
    await message.answer("📞 **Служба поддержки UniGate**\n\nВозникли проблемы? Напиши нам!", parse_mode="Markdown", reply_markup=builder.as_markup())

# ========== АДМИН-КОМАНДА ==========
@dp.message(Command("activate"))
async def activate_user(message: types.Message):
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
    cursor.execute("INSERT INTO users (user_id, subscription_end) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET subscription_end = ?", (user_id, end_date.isoformat(), end_date.isoformat()))
    conn.commit()
    vless_link = await create_xui_client(user_id, months)
    if vless_link:
        await bot.send_message(user_id, f"✅ **Подписка активирована на {months} месяц(ев)!**\n\n🔑 **Твой ключ:**\n`{vless_link}`", parse_mode="Markdown")
        await message.answer(f"✅ Ключ отправлен {user_id}")
    else:
        await message.answer("❌ Ошибка при создании ключа")

# ========== ЗАПУСК ==========
async def main():
    print("✅ Бот UniGate запущен!")
    await dp.start_polling(bot)

asyncio.run(main())
