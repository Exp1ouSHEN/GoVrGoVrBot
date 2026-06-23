import asyncio
import os
import sqlite3
import aiohttp

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# ---------------- MEMORY ----------------
user_data = {}
admin_reply = {}
admin_mode = {}

# ---------------- MENU ----------------
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Забронювати")],
        [KeyboardButton(text="💰 Прайс")],
        [KeyboardButton(text="📞 Адміністратор")]
    ],
    resize_keyboard=True
)

# ---------------- TARIFS ----------------
TARIFFS = {
    "lite": {"name": "LITE", "prices": {1: 500, 2: 900, 3: 1300, 4: 1600}},
    "vip": {"name": "VIP", "prices": {1: 700, 2: 1300, 3: 1800, 4: 2300}},
    "birthday": {"name": "BIRTHDAY", "prices": {1.5: 2500, 2: 3000, 3: 4000, 4: 5000}},
    "party": {"name": "PARTY", "prices": {4: 8000}}
}

WORK_START = 10
WORK_END = 19

# ---------------- PAYMENT ----------------
async def create_invoice(amount, desc):
    url = "https://api.monobank.ua/api/merchant/invoice/create"
    headers = {"X-Token": MONO_TOKEN}

    payload = {
        "amount": int(amount * 100),
        "ccy": 980,
        "merchantPaymInfo": {
            "reference": "booking",
            "destination": desc
        },
        "redirectUrl": "https://t.me/"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as r:
            return await r.json()

# ---------------- KEYBOARDS ----------------
def get_dates():
    today = datetime.now()
    kb = []

    for i in range(7):
        d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        kb.append([InlineKeyboardButton(text=d, callback_data=f"date:{d}")])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_times():
    kb = []
    for h in range(10, 19):
        kb.append([InlineKeyboardButton(text=f"{h}:00", callback_data=f"time:{h}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_tariffs():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="LITE", callback_data="tariff:lite")],
        [InlineKeyboardButton(text="VIP", callback_data="tariff:vip")],
        [InlineKeyboardButton(text="BIRTHDAY", callback_data="tariff:birthday")],
        [InlineKeyboardButton(text="PARTY", callback_data="tariff:party")]
    ])


def get_hours():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1h", callback_data="hours:1"),
         InlineKeyboardButton(text="2h", callback_data="hours:2")],
        [InlineKeyboardButton(text="3h", callback_data="hours:3"),
         InlineKeyboardButton(text="4h", callback_data="hours:4")]
    ])

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("👋 GoVr бронювання", reply_markup=menu)

# ---------------- ADMIN BUTTON ----------------
@dp.message(lambda m: m.text == "📞 Адміністратор")
async def admin_btn(m: types.Message):
    admin_mode[m.from_user.id] = True
    await m.answer("Напиши сообщение админу")

@dp.message(lambda m: m.from_user.id in admin_mode)
async def send_to_admin(m: types.Message):
    uid = m.from_user.id
    admin_mode.pop(uid, None)

    admin_reply[ADMIN_ID] = uid

    await bot.send_message(
        ADMIN_ID,
        f"Сообщение от {uid}:\n{m.text}"
    )

    await m.answer("Отправлено")

@dp.message(lambda m: m.from_user.id == ADMIN_ID)
async def admin_reply_handler(m: types.Message):
    uid = admin_reply.get(ADMIN_ID)
    if not uid:
        return

    await bot.send_message(uid, f"Ответ админа:\n{m.text}")
    await m.answer("Отправлено")

# ---------------- BOOK ----------------

@dp.message(lambda m: m.text == "🎮 Забронювати")
async def book(m: types.Message):
    user_data[m.from_user.id] = {}
    await m.answer("📅 Обери дату:", reply_markup=get_dates())

# ---------------- DATE ----------------

@dp.callback_query(lambda c: c.data.startswith("date:"))
async def date(c: types.CallbackQuery):
    uid = c.from_user.id
    user_data[uid]["date"] = c.data.split(":")[1]
    await c.message.answer("🎮 Обери тариф:", reply_markup=get_tariffs())
    await c.answer()

# ---------------- TARIFF ----------------

@dp.callback_query(lambda c: c.data.startswith("tariff:"))
async def tariff(c: types.CallbackQuery):
    uid = c.from_user.id
    user_data[uid]["tariff"] = c.data.split(":")[1]
    await c.message.answer("⏱ Обери години:", reply_markup=get_hours())
    await c.answer()

# ---------------- HOURS ----------------

@dp.callback_query(lambda c: c.data.startswith("hours:"))
async def hours(c: types.CallbackQuery):
    uid = c.from_user.id
    user_data[uid]["hours"] = float(c.data.split(":")[1])
    await c.message.answer("👤 Введи ім'я:")
    await c.answer()

# ---------------- FORM ----------------

@dp.message(lambda m: m.from_user.id in user_data)
async def form(m: types.Message):
    uid = m.from_user.id
    d = user_data[uid]

    if "name" not in d:
        d["name"] = m.text
        await m.answer("📞 Телефон:")
        return

    if "phone" not in d:
        d["phone"] = m.text
        await m.answer("👥 Гостей:")
        return

    if "guests" not in d:
        d["guests"] = m.text
        await m.answer("💬 Коментар:")
        return

    d["comment"] = m.text

    price = TARIFFS[d["tariff"]].get(d["hours"], 0)
    deposit = round(price * 0.1)

    cursor.execute("""
        INSERT INTO bookings (date, time, hours, name, phone, guests, comment, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (d["date"], 10, d["hours"], d["name"], d["phone"], d["guests"], d["comment"]))
    conn.commit()

    pay = await create_invoice(deposit, "GoVr booking")
    url = pay.get("pageUrl", "")

    await m.answer(
        f"✅ Бронь створено\n💰 {price} грн\n💳 Аванс: {deposit} грн\n{url}"
    )

    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"""📥 НОВА БРОНЬ

👤 {d['name']}
📞 {d['phone']}
📅 {d['date']}
⌛ {d['hours']}h
👥 {d['guests']}
💬 {d['comment']}
"""
        )

# ---------------- RUN ----------------

async def main():
    print("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())