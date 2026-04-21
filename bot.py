import asyncio
import sqlite3
import base64
import requests
import json
import uuid
import ssl
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import os

# Отключаем проверку SSL (для самоподписанных сертификатов)
ssl._create_default_https_context = ssl._create_unverified_context

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8598128447:AAHupd0ltwgCOt592dPu09sKswEjGtMK3Lo"
ADMIN_IDS = [1446300344, 2051767977]
BOT_USERNAME = "UniGates_bot"

CARD_NUMBER = "2200 1523 0320 4112"
CARD_HOLDER = "SAVELII MINKOV"

# ========== НАСТРОЙКИ GITHUB ==========
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = "kolarakuzov07-max/UniGateBot"
GITHUB_PATH = "sub.txt"
SUBSCRIPTION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_PATH}"

# ========== НАСТРОЙКИ ПАНЕЛЕЙ ==========
PANELS = [
    {
        "name": "Финляндия",
        "host": "https://89.125.199.10:18184",
        "username": "jS0JFHvlsd",
        "password": "a6qSCo055u",
        "inbound_id": 1,
        "public_key": "RDInRTWWcapc63FVwqErWswse5fX1EJsRNyupixfyLQA",
        "short_id": "05",
        "ip": "89.125.199.10"
    },
    {
        "name": "Нидерланды",
        "host": "https://78.17.38.254:32475",
        "username": "IuzIr13Sz3",
        "password": "wGvRLBat9G",
        "inbound_id": 1,
        "public_key": "gJf-IXJop7xayakfaJ7u57-j7bJTqznPGjlHkJT9_0s",
        "short_id": "c4",
        "ip": "78.17.38.254"
    },
    {
        "name": "Польша",
        "host": "https://89.125.27.104:27520",
        "username": "YqsmDjGTAW",
        "password": "tDuL2CYYYq",
        "inbound_id": 1,
        "public_key": "NQv9v4X_INAg_oVZa_LPvcCMJ-h3jptktl4nexOM6BY",
        "short_id": "461ffc9b",
        "ip": "89.125.27.104"
    }
]

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

# ========== УДАЛЕНИЕ СООБЩЕНИЙ ==========
main_message_id = {}
temp_messages = {}
user_messages = {}

async def save_main_message(user_id, message_id):
    main_message_id[user_id] = message_id

async def save_temp_message(user_id, message_id):
    if user_id not in temp_messages:
        temp_messages[user_id] = []
    temp_messages[user_id].append(message_id)
    if len(temp_messages[user_id]) > 10:
        temp_messages[user_id] = temp_messages[user_id][-10:]

async def save_user_message(user_id, message_id):
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(message_id)
    if len(user_messages[user_id]) > 10:
        user_messages[user_id] = user_messages[user_id][-10:]

async def delete_user_messages(user_id, chat_id):
    if user_id in user_messages:
        for msg_id in user_messages[user_id]:
            try:
                await bot.delete_message(chat_id, msg_id)
            except:
                pass
        user_messages[user_id] = []

async def delete_temp_messages(user_id, chat_id):
    if user_id in temp_messages:
        for msg_id in temp_messages[user_id]:
            try:
                await bot.delete_message(chat_id, msg_id)
            except:
                pass
        temp_messages[user_id] = []

# ========== ФУНКЦИИ РАБОТЫ С ПАНЕЛЯМИ ==========
def api_login(panel):
    """Логин в панели 3X-UI, возвращает сессию"""
    session = requests.Session()
    login_url = f"{panel['host']}/login"
    login_data = {
        "username": panel["username"],
        "password": panel["password"]
    }
    session.post(login_url, data=login_data, verify=False)
    return session

async def create_client_on_panel(panel, user_id, days):
    """Создаёт клиента на указанной панели и возвращает vless:// ссылку"""
    email = f"user_{user_id}"
    expiry_time = int((datetime.now() + timedelta(days=days)).timestamp() * 1000)
    client_uuid = str(uuid.uuid4())
    
    session = api_login(panel)
    
    # Создаём клиента
    api_url = f"{panel['host']}/panel/api/inbounds/addClient"
    data = {
        "id": panel["inbound_id"],
        "settings": json.dumps({
            "clients": [{
                "id": client_uuid,
                "email": email,
                "enable": True,
                "expiryTime": expiry_time,
                "totalGB": 0,
                "flow": "xtls-rprx-vision"
            }]
        })
    }
    
    response = session.post(api_url, json=data, verify=False)
    
    if response.status_code == 200:
        vless_link = f"vless://{client_uuid}@{panel['ip']}:443?type=tcp&security=reality&pbk={panel['public_key']}&fp=random&sid={panel['short_id']}&flow=xtls-rprx-vision#{panel['name']}"
        return vless_link
    
    return None

async def update_subscription_file(vless_links):
    """Обновляет файл sub.txt на GitHub"""
    content = "#%FRAGMENT length=1-10, interval=5-20, packets=tlshello\n"
    content += "\n".join(vless_links)
    
    encoded = base64.b64encode(content.encode()).decode()
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    response = requests.get(url, headers=headers)
    sha = response.json().get("sha") if response.status_code == 200 else None
    
    data = {
        "message": "Update subscription",
        "content": encoded,
        "sha": sha
    }
    
    requests.put(url, headers=headers, json=data)

async def create_subscription(user_id, days):
    """Создаёт клиентов на всех серверах и возвращает ссылку на подписку"""
    vless_links = []
    
    for panel in PANELS:
        try:
            link = await create_client_on_panel(panel, user_id, days)
            if link:
                vless_links.append(link)
        except Exception as e:
            print(f"Ошибка на панели {panel['name']}: {e}")
    
    if vless_links:
        await update_subscription_file(vless_links)
    
    return SUBSCRIPTION_URL

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
    builder.button(text="💎 3 месяца — 250₽ 💎", callback_data="tariff_3")
    builder.adjust(1)
    return builder.as_markup()

def copy_keyboard(connection_string):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать ключ", callback_data="copy_key")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

def payment_keyboard(amount, months, user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Скопировать реквизиты", callback_data="copy_payment")
    builder.button(text="✅ Я оплатил", callback_data=f"paid_{months}")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()

# ========== ОБРАБОТЧИКИ ==========
@dp.callback_query(lambda c: c.data == "copy_key")
async def copy_key(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer(f"🔑 Подписка активна! Используй ссылку: {SUBSCRIPTION_URL}", show_alert=True)

@dp.callback_query(lambda c: c.data == "copy_payment")
async def copy_payment(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT pending_payment FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    months = 1
    if result and result[0] and result[0] > 0:
        months = result[0]
    
    prices = {1: 100, 2: 180, 3: 250}
    amount = prices.get(months, 100)
    
    text = f"Переведи {amount}₽ на карту {CARD_NUMBER}\nПолучатель: {CARD_HOLDER}\nКомментарий: {user_id}"
    await callback.answer(f"💳 Реквизиты скопированы!\n\n{text}", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("tariff_"))
async def select_tariff(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    await save_user_message(user_id, callback.message.message_id)
    
    tariff = callback.data.split("_")[1]
    prices = {"1": 100, "2": 180, "3": 250}
    amount = prices.get(tariff, 100)
    months = int(tariff)
    
    cursor.execute("INSERT INTO users (user_id, pending_payment) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET pending_payment = ?", (user_id, months, months))
    conn.commit()
    
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
    text = (
        f"💳 **Оплата {months} месяц(ев) — {amount}₽**\n\n"
        f"**Реквизиты для перевода:**\n"
        f"📌 Карта: `{CARD_NUMBER}`\n"
        f"📌 Получатель: `{CARD_HOLDER}`\n"
        f"📌 Сумма: {amount}₽\n"
        f"📌 Комментарий: `{user_id}`\n\n"
        f"✅ **После перевода** нажми кнопку «✅ Я оплатил»."
    )
    
    msg = await callback.message.answer(text, parse_mode="Markdown", reply_markup=payment_keyboard(amount, months, user_id))
    await save_temp_message(user_id, msg.message_id)
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("paid_"))
async def payment_received(callback: types.CallbackQuery):
    months = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    prices = {1: 100, 2: 180, 3: 250}
    amount = prices.get(months, 100)
    
    await save_user_message(user_id, callback.message.message_id)
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"💰 **НОВАЯ ОПЛАТА**\n\n👤 Пользователь: [{user_id}](tg://user?id={user_id})\n📆 Тариф: {months} месяц(ев)\n💵 Сумма: {amount}₽\n\n✅ После проверки введи:\n`/activate {user_id} {months}`", parse_mode="Markdown")
    
    msg = await callback.message.answer(
        "✅ **Заявка на оплату отправлена!**\n\n"
        "Администратор проверит перевод и активирует подписку."
    )
    await save_temp_message(user_id, msg.message_id)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "extend")
async def extend_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    await save_user_message(user_id, callback.message.message_id)
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
    msg = await callback.message.answer("💰 **Выбери тариф для продления:**", reply_markup=tariffs_keyboard())
    await save_temp_message(user_id, msg.message_id)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    await save_user_message(user_id, callback.message.message_id)
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
    if user_id in main_message_id:
        try:
            await bot.delete_message(chat_id, main_message_id[user_id])
        except:
            pass
    
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
            msg = await callback.message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="welcome.jpg"),
                caption=text,
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
            await save_main_message(user_id, msg.message_id)
    except:
        msg = await callback.message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard())
        await save_main_message(user_id, msg.message_id)
    
    await callback.answer()

# ========== ПРОФИЛЬ ==========
@dp.message(lambda m: m.text == "👤 Профиль")
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    await save_user_message(user_id, message.message_id)
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
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
            builder.button(text="🔄 Продлить подписку", callback_data="extend")
            builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
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
        f"🆔 **Telegram ID:** `{user_id}`\n"
        f"📝 **Имя:** {first_name}\n"
        f"🔹 **Username:** @{username}\n\n"
        f"📅 **Статус подписки:** {status}\n\n"
        f"👥 **Реферальная система:**\n"
        f"└ Приглашено друзей: **{referral_count}**\n"
        f"└ Ваша ссылка: `{referral_link}`"
    )
    
    try:
        with open("profile.jpg", "rb") as photo:
            msg = await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="profile.jpg"),
                caption=profile_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
            await save_temp_message(user_id, msg.message_id)
    except:
        msg = await message.answer(profile_text, parse_mode="Markdown", reply_markup=reply_markup)
        await save_temp_message(user_id, msg.message_id)

# ========== СТАРТ ==========
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    await save_user_message(user_id, message.message_id)
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
    if user_id in main_message_id:
        try:
            await bot.delete_message(chat_id, main_message_id[user_id])
        except:
            pass
    
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

# ========== ГЛАВНОЕ МЕНЮ ==========
@dp.message(lambda m: m.text == "🏠 Главное меню")
async def main_menu(message: types.Message):
    await start_command(message)

# ========== ПОЛУЧИТЬ КЛЮЧ ==========
@dp.message(lambda m: m.text == "🛡️ Получить ключ")
async def get_key(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    await save_user_message(user_id, message.message_id)
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
    cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        end_date = datetime.fromisoformat(result[0])
        if end_date > datetime.now():
            await message.answer(
                f"🔑 **Твоя подписка активна!**\n\n"
                f"📱 **Ссылка для подключения:**\n"
                f"`{SUBSCRIPTION_URL}`\n\n"
                f"📌 **Инструкция:**\n"
                f"1. Скопируй ссылку\n"
                f"2. Открой Happ → «+» → «Импорт по URL»\n"
                f"3. Вставь ссылку и нажми «Готово»\n"
                f"4. Выбери сервер и подключись",
                parse_mode="Markdown"
            )
            return
    
    msg = await message.answer(
        "❌ **У тебя нет активной подписки.**\n\n"
        "Нажми «💳 Тарифы» и выбери подходящий план.",
        parse_mode="Markdown"
    )
    await save_temp_message(user_id, msg.message_id)

# ========== ТАРИФЫ ==========
@dp.message(lambda m: m.text == "💳 Тарифы")
async def show_tariffs(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    await save_user_message(user_id, message.message_id)
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
    text = (
        "💰 **Наши тарифы:**\n\n"
        "⭐ **1 месяц** — 100₽\n"
        "🔥 **2 месяца** — 180₽\n"
        "💎 **3 месяца** — 250₽\n\n"
        "👇 **Выбери подходящий тариф:**"
    )
    
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

# ========== ПОДДЕРЖКА ==========
@dp.message(lambda m: m.text == "📞 Поддержка")
async def support_command(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    await save_user_message(user_id, message.message_id)
    await delete_user_messages(user_id, chat_id)
    await delete_temp_messages(user_id, chat_id)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Написать в поддержку", url="https://t.me/UniGatesSupport")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    text = "📞 **Служба поддержки UniGate**\n\nВозникли проблемы? Напиши нам!"
    
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
    days = months * 30
    
    end_date = datetime.now() + timedelta(days=days)
    cursor.execute("""
        INSERT INTO users (user_id, subscription_end, pending_payment) 
        VALUES (?, ?, 0) 
        ON CONFLICT(user_id) DO UPDATE SET subscription_end = ?, pending_payment = 0
    """, (user_id, end_date.isoformat(), end_date.isoformat()))
    conn.commit()
    
    subscription_url = await create_subscription(user_id, days)
    
    await bot.send_message(
        user_id,
        f"✅ **Подписка активирована на {months} месяц(ев)!**\n\n"
        f"🔗 **Твоя подписка:**\n`{subscription_url}`\n\n"
        f"📱 **Инструкция:**\n"
        f"1. Скопируй ссылку\n"
        f"2. Открой Happ → «+» → «Импорт по URL»\n"
        f"3. Вставь ссылку и нажми «Готово»\n\n"
        f"🗓️ Действительна до: {end_date.strftime('%d.%m.%Y')}\n"
        f"🌍 В подписке: Финляндия, Нидерланды, Польша",
        parse_mode="Markdown"
    )
    await message.answer(f"✅ Подписка активирована для {user_id}")

# ========== ЗАПУСК ==========
async def main():
    print("✅ Бот UniGate запущен!")
    await dp.start_polling(bot)

asyncio.run(main())
