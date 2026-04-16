import asyncio
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import os
import uuid

from py3xui import Api, Client

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8598128447:AAHupd0ltwgCOt592dPu09sKswEjGtMK3Lo"
ADMIN_IDS = [1446300344, 2051767977]
BOT_USERNAME = "UniGates_bot"

CARD_NUMBER = "2200 1523 0320 4112"
CARD_HOLDER = "SAVELII MINKOV"

# ========== НАСТРОЙКИ 3X-UI ==========
XUI_HOST = "http://89.125.199.10:18184"  # <--- ПОРТ ИСПРАВЛЕН
XUI_USERNAME = "jS0JFHvlsd"
XUI_PASSWORD = "a6qSCo055u"
INBOUND_ID = 1
SERVER_IP = "89.125.199.10"

# Подключаемся к API панели
api = Api(XUI_HOST, XUI_USERNAME, XUI_PASSWORD)
api.login()

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

# ========== РАБОТА С 3X-UI API ==========
async def create_vpn_key(user_id, days=30):
    """Создаёт клиента в 3X-UI и возвращает vless:// ссылку"""
    email = f"user_{user_id}"
    
    # Проверяем, есть ли уже такой клиент
    existing = api.client.get_by_email(email)
    if existing:
        # Обновляем дату окончания
        existing.expiry_time = int((datetime.now() + timedelta(days=days)).timestamp() * 1000)
        api.client.update(existing.id, existing)
        return get_client_link(existing)
    
    # Создаём нового клиента
    new_client = Client(
        id=str(uuid.uuid4()),
        email=email,
        enable=True,
        expiry_time=int((datetime.now() + timedelta(days=days)).timestamp() * 1000)
    )
    
    api.client.add(INBOUND_ID, new_client)
    
    # Получаем созданного клиента
    client = api.client.get_by_email(email)
    return get_client_link(client)

def get_client_link(client):
    """Формирует vless:// ссылку из данных клиента"""
    inbound = api.inbound.get(INBOUND_ID)
    
    # Получаем параметры из inbound
    port = inbound.port
    stream_settings = inbound.stream_settings
    reality_settings = stream_settings.get("realitySettings", {})
    public_key = reality_settings.get("publicKey", "")
    sni = reality_settings.get("serverNames", ["www.microsoft.com"])[0]
    short_id = reality_settings.get("shortIds", ["e83ba78a69"])[0]
    
    # Формируем ссылку
    link = f"vless://{client.id}@{SERVER_IP}:{port}?type=tcp&security=reality&pbk={public_key}&fp=chrome&sni={sni}&sid={short_id}&flow=xtls-rprx-vision#UniGates"
    
    return link

# ========== ОБРАБОТЧИКИ ==========
@dp.callback_query(lambda c: c.data == "copy_key")
async def copy_key(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    # Получаем ключ пользователя из БД или создаём новый
    cursor.execute("SELECT subscription_end FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result and result[0]:
        key = await create_vpn_key(user_id, 30)
        await callback.answer(f"🔑 Ключ скопирован!\n\n{key}", show_alert=True)
    else:
        await callback.answer("❌ У вас нет активной подписки", show_alert=True)

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
    
    tariff = callback.data.split("_")[1]
    prices = {"1": 100, "2": 180, "3": 250}
    amount = prices.get(tariff, 100)
    months = int(tariff)
    
    cursor.execute("INSERT INTO users (user_id, pending_payment) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET pending_payment = ?", (user_id, months, months))
    conn.commit()
    
    text = (
        f"💳 **Оплата {months} месяц(ев) — {amount}₽**\n\n"
        f"**Реквизиты для перевода:**\n"
        f"📌 Карта: `{CARD_NUMBER}`\n"
        f"📌 Получатель: `{CARD_HOLDER}`\n"
        f"📌 Сумма: {amount}₽\n"
        f"📌 Комментарий: `{user_id}`\n\n"
        f"✅ После перевода нажми кнопку «✅ Я оплатил»."
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=payment_keyboard(amount, months, user_id))
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("paid_"))
async def payment_received(callback: types.CallbackQuery):
    months = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    prices = {1: 100, 2: 180, 3: 250}
    amount = prices.get(months, 100)
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"💰 **НОВАЯ ОПЛАТА**\n\n👤 Пользователь: [{user_id}](tg://user?id={user_id})\n📆 Тариф: {months} месяц(ев)\n💵 Сумма: {amount}₽\n\n✅ После проверки введи:\n`/activate {user_id} {months}`", parse_mode="Markdown")
    
    await callback.message.edit_text(
        "✅ **Заявка на оплату отправлена!**\n\n"
        "Администратор проверит перевод и активирует подписку."
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "extend")
async def extend_subscription(callback: types.CallbackQuery):
    await callback.message.edit_text("💰 **Выбери тариф для продления:**", reply_markup=tariffs_keyboard())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await start_command(callback.message)
    await callback.answer()

# ========== ПРОФИЛЬ ==========
@dp.message(lambda m: m.text == "👤 Профиль")
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "нет"
    first_name = message.from_user.first_name or ""
    
    cursor.execute("SELECT subscription_end, referral_count FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        fromisoformat(result[0])
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
        f"🆔 Telegram ID: `{user_id}`\n"
        f"📝 Имя: {first_name}\n"
        f"🔹 Username: @{username}\n\n"
        f"📅 Статус подписки: {status}\n\n"
        f"👥 **Реферальная система:**\n"
        f"└ Приглашено друзей: **{referral_count}**\n"
        f"└ Ваша ссылка: `{referral_link}`"
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

# ========== СТАРТ ==========
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
    
    text = (
        "🚪 **Добро пожаловать в UniGate!**\n\n"
        "✨ **Почему выбирают нас:**\n"
        "• 🚀 **Молниеносная скорость**\n"
        "• 🔒 **Абсолютная приватность**\n"
        "• 🌍 **Доступ к любым сайтам**\n"
        "• 📱 Один клик для подключения\n\n"
        "🎁 **Первый месяц — всего 100₽!**\n\n"
        "👇 **Выбери действие:**"
    )
    
    try:
        with open("welcome.jpg", "rb") as photo:
            await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="welcome.jpg"),
                caption=text,
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
    except:
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
            # Автоматически создаём ключ через API
            try:
                vless_link = await create_vpn_key(user_id)
                await message.answer(
                    f"🔑 **Твой VPN-ключ:**\n\n"
                    f"`{vless_link}`\n\n"
                    f"📱 **Инструкция:**\n"
                    f"1. Нажми «📋 Скопировать ключ»\n"
                    f"2. Открой Happ → «+» → «Из буфера обмена»",
                    parse_mode="Markdown",
                    reply_markup=copy_keyboard(vless_link)
                )
            except Exception as e:
                await message.answer(f"❌ Ошибка при создании ключа: {e}")
            return
    
    await message.answer(
        "❌ **У тебя нет активной подписки.**\n\n"
        "Нажми «💳 Тарифы» и выбери подходящий план.",
        parse_mode="Markdown"
    )

# ========== ТАРИФЫ ==========
@dp.message(lambda m: m.text == "💳 Тарифы")
async def show_tariffs(message: types.Message):
    text = (
        "💰 **Наши тарифы:**\n\n"
        "⭐ 1 месяц — 100₽\n"
        "🔥 2 месяца — 180₽\n"
        "💎 3 месяца — 250₽\n\n"
        "👇 **Выбери подходящий тариф:**"
    )
    
    try:
        with open("tariffs.jpg", "rb") as photo:
            await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="tariffs.jpg"),
                caption=text,
                parse_mode="Markdown",
                reply_markup=tariffs_keyboard()
            )
    except:
        await message.answer(text, parse_mode="Markdown", reply_markup=tariffs_keyboard())

# ========== ПОДДЕРЖКА ==========
@dp.message(lambda m: m.text == "📞 Поддержка")
async def support_command(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📩 Написать в поддержку", url="https://t.me/UniGatesSupport")
    builder.button(text="🏠 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    text = "📞 **Служба поддержки UniGate**\n\nВозникли проблемы? Напиши нам!"
    
    try:
        with open("support.jpg", "rb") as photo:
            await message.answer_photo(
                photo=types.BufferedInputFile(photo.read(), filename="support.jpg"),
                caption=text,
                parse_mode="Markdown",
                reply_markup=builder.as_markup()
            )
    except:
        await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

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
    
    # Активируем подписку в БД
    end_date = datetime.now() + timedelta(days=30 * months)
    cursor.execute("""
        INSERT INTO users (user_id, subscription_end, pending_payment) 
        VALUES (?, ?, 0) 
        ON CONFLICT(user_id) DO UPDATE SET subscription_end = ?, pending_payment = 0
    """, (user_id, end_date.isoformat(), end_date.isoformat()))
    conn.commit()
    
    # Автоматически создаём ключ через API
    try:
        vless_link = await create_vpn_key(user_id, days=30 * months)
        
        await bot.send_message(
            user_id,
            f"✅ **Подписка активирована на {months} месяц(ев)!**\n\n"
            f"🔑 **Твой VPN-ключ:**\n"
            f"`{vless_link}`\n\n"
            f"📱 **Инструкция:**\n"
            f"1. Нажми «📋 Скопировать ключ»\n"
            f"2. Открой Happ → «+» → «Из буфера обмена»",
            parse_mode="Markdown",
            reply_markup=copy_keyboard(vless_link)
        )
        await message.answer(f"✅ Ключ создан и отправлен пользователю {user_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при создании ключа: {e}")

# ========== ЗАПУСК ==========
async def main():
    print("✅ Бот UniGate запущен!")
    await dp.start_polling(bot)

asyncio.run(main())
