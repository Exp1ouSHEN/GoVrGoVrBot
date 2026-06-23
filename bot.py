import asyncio
import sqlite3
import aiohttp
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import BOT_TOKEN, ADMIN_ID, MONO_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
admin_reply = {}
admin_mode = {}
user_data = {}
# ---------------- DB ----------------

conn = sqlite3.connect("bookings.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    time INTEGER,
    hours REAL,
    name TEXT,
    phone TEXT,
    guests TEXT,
    comment TEXT,
    status TEXT DEFAULT 'pending'
)
""")
conn.commit()

user_data = {}

WORK_START = 10
WORK_END = 19

TARIFFS = {
    "lite": {
        "name": "🎮 LITE",
        "prices": {
            1: 500,
            2: 900,
            3: 1300,
            4: 1600
        }
    },

    "vip": {
        "name": "🔥 VIP + PS5",
        "prices": {
            1: 700,
            2: 1300,
            3: 1800,
            4: 2300
        }
    },

    "birthday": {
        "name": "🎂 День Народження",
        "prices": {
            1.5: 2500,
            2: 3000,
            3: 4000,
            4: 5000
        }
    },

    "party": {
        "name": "⭐ VIP PARTY",
        "prices": {
            4: 8000
        }
    }
}

# ---------------- MONO PAY ----------------

async def create_invoice(amount, desc):
    url = "https://api.monobank.ua/api/merchant/invoice/create"

    headers = {"X-Token": MONO_TOKEN}

    payload = {
        "amount": int(amount * 100),
        "ccy": 980,
        "merchantPaymInfo": {
            "reference": "gouvr_booking",
            "destination": desc
        },
        "redirectUrl": "https://t.me/"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as r:
            return await r.json()


# ---------------- UI ----------------

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Забронювати")],
        [KeyboardButton(text="💰 Прайс")],
        [KeyboardButton(text="📞 Адміністратор")]
    ],
    resize_keyboard=True
)


# ---------------- DATES ----------------

def get_dates():
    today = datetime.now()
    kb = []

    for i in range(7):
        d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        kb.append([InlineKeyboardButton(text=d, callback_data=f"date:{d}")])

    return InlineKeyboardMarkup(inline_keyboard=kb)


# ---------------- TIMES (❌ занято) ----------------

def get_times(date):

    cursor.execute(
        "SELECT time, hours FROM bookings WHERE date=?",
        (date,)
    )

    rows = cursor.fetchall()

    busy = set()

    for start_time, duration in rows:
        for i in range(int(duration)):
            busy.add(start_time + i)

    kb = []

    for h in range(10, 19):

        # Перерыв
        if h == 13:
            kb.append([
                InlineKeyboardButton(
                    text="13:00-14:00 ☕ Перерва",
                    callback_data="none"
                )
            ])
            continue

        # Занято
        if h in busy:
            kb.append([
                InlineKeyboardButton(
                    text=f"{h}:00 ❌",
                    callback_data="none"
                )
            ])
        else:
            kb.append([
                InlineKeyboardButton(
                    text=f"{h}:00",
                    callback_data=f"time:{h}"
                )
            ])

    return InlineKeyboardMarkup(inline_keyboard=kb)

# ---------------- HOURS ----------------

def get_hours():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 год", callback_data="hours:1"),
            InlineKeyboardButton(text="2 год", callback_data="hours:2"),
        ],
        [
            InlineKeyboardButton(text="3 год", callback_data="hours:3"),
            InlineKeyboardButton(text="4 год", callback_data="hours:4"),
        ],
    ])

def get_tariffs():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 LITE", callback_data="tariff:lite")],
        [InlineKeyboardButton(text="🔥 VIP + PS5", callback_data="tariff:vip")],
        [InlineKeyboardButton(text="🎂 День Народження", callback_data="tariff:birthday")],
        [InlineKeyboardButton(text="⭐ VIP PARTY", callback_data="tariff:party")]
    ])


def get_tariff_hours(tariff):

    buttons = []

    for hour, price in TARIFFS[tariff]["prices"].items():

        buttons.append([
            InlineKeyboardButton(
                text=f"{hour} год - {price} грн",
                callback_data=f"hours:{hour}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("👋 GoVr бронювання", reply_markup=menu)


# ---------------- PRICE ----------------

@dp.message(lambda m: m.text == "💰 Прайс")
async def price(m: types.Message):
    await m.answer(
        "💰 ПРАЙС GoVr\n\n"
        "🎮 LITE:\n"
        "1h — 500 грн\n2h — 900 грн\n3h — 1300 грн\n4h — 1600 грн\n\n"
        "🎮 VIP + PS5:\n"
        "1h — 700 грн\n2h — 1300 грн\n3h — 1800 грн\n4h — 2300 грн\n\n"
        "🎂 BIRTHDAY:\n"
        "1.5h — 2500 грн\n2h — 3000 грн\n3h — 4000 грн\n4h — 5000 грн\n\n"
        "🔥 VIP PARTY — 8000 грн (4h)"
    )


# ---------------- ADMIN ЧАТ ----------------
admin_mode = {}
@dp.message(lambda m: m.text == "📞 Адміністратор")
async def admin(m: types.Message):
    admin_mode[m.from_user.id] = True
    await m.answer("💬 Напишіть повідомлення адміністратору:")

@dp.message(lambda m: m.from_user.id in admin_mode)
async def admin_message(m: types.Message):

    uid = m.from_user.id

    admin_mode.pop(uid, None)

    username = m.from_user.username or "no_username"

    admin_reply[ADMIN_ID] = uid

    await bot.send_message(
        ADMIN_ID,
        f"📩 Нове повідомлення від @{username}\n\n{m.text}\n\n"
        f"Для відповіді просто напишіть повідомлення."
    )

    await m.answer("✅ Повідомлення відправлено адміністратору")

@dp.message(lambda m: m.from_user.id == ADMIN_ID)
async def admin_answer(m: types.Message):

    user_id = admin_reply.get(ADMIN_ID)

    if not user_id:
        return

    await bot.send_message(
        user_id,
        f"💬 Відповідь адміністратора:\n\n{m.text}"
    )

    await m.answer("✅ Відправлено користувачу")

# ---------------- BOOK ----------------

@dp.message(lambda m: m.text == "🎮 Забронювати")
async def book(m: types.Message):
    user_data[m.from_user.id] = {}
    await m.answer("📅 Оберіть дату:", reply_markup=get_dates())


# ---------- ВЫБОР ДАТЫ ----------

@dp.callback_query(lambda c: c.data.startswith("date:"))
async def date(c: types.CallbackQuery):
    uid = c.from_user.id

    selected_date = c.data.split(":")[1]

    user_data[uid]["date"] = selected_date

    await c.message.answer(
        "⏰ Оберіть час:",
        reply_markup=get_times(selected_date)
    )

    await c.answer()


# ---------- ВЫБОР ВРЕМЕНИ ----------

@dp.callback_query(lambda c: c.data.startswith("time:"))
async def time(c: types.CallbackQuery):

    uid = c.from_user.id

    selected_time = int(c.data.split(":")[1])

    user_data[uid]["time"] = selected_time

    await c.message.answer(
        "🎮 Оберіть тариф:",
        reply_markup=get_tariffs()
    )

    await c.answer()

@dp.callback_query(lambda c: c.data.startswith("tariff:"))
async def tariff(c: types.CallbackQuery):

    uid = c.from_user.id

    selected_tariff = c.data.split(":")[1]

    user_data[uid]["tariff"] = selected_tariff

    await c.message.answer(
        "⏱ Оберіть тривалість:",
        reply_markup=get_tariff_hours(selected_tariff)
    )

    await c.answer()


# ---------- ВЫБОР КОЛИЧЕСТВА ЧАСОВ ----------

@dp.callback_query(lambda c: c.data.startswith("hours:"))
async def hours(c: types.CallbackQuery):
    uid = c.from_user.id

    selected_hours = float(c.data.split(":")[1])

    booking_date = user_data[uid]["date"]
    booking_time = user_data[uid]["time"]

    # Проверяем пересечения брони
    cursor.execute(
        "SELECT time, hours FROM bookings WHERE date=?",
        (booking_date,)
    )

    rows = cursor.fetchall()

    new_slots = set(
        booking_time + i
        for i in range(int(selected_hours))
    )

    # Нельзя через перерыв
    if 13 in new_slots:
        await c.message.answer(
            "❌ Не можна бронювати через перерву 13:00-14:00"
        )
        return

    # Нельзя после 19:00
    if booking_time + selected_hours > 19:
        await c.message.answer(
            "❌ Заклад працює до 19:00"
        )
        return

    # Проверка занятости
    for start_time, duration in rows:

        busy_slots = set(
            start_time + i
            for i in range(int(duration))
        )

        if new_slots & busy_slots:
            await c.message.answer(
                "❌ Цей час вже зайнятий"
            )
            return

    user_data[uid]["hours"] = selected_hours

    await c.message.answer("👤 Введіть ім'я:")
    await c.answer()

# ---------------- FORM + PAYMENT ----------------

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
        await m.answer("👥 Кількість гостей:")
        return

    if "guests" not in d:
        d["guests"] = m.text
        await m.answer("💬 Коментар:")
        return

    d["comment"] = m.text

    tariff = d["tariff"]
    hours = d["hours"]

    price = TARIFFS[tariff]["prices"].get(hours)
    deposit = round(price * 0.1)

    cursor.execute("""
        INSERT INTO bookings (date, time, hours, name, phone, guests, comment, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (
        d["date"], d["time"], d["hours"],
        d["name"], d["phone"], d["guests"], d["comment"]
    ))
    conn.commit()

    pay = await create_invoice(deposit, "GoVr бронювання")
    pay_url = pay.get("pageUrl", "")

    await m.answer(
        f"✅ Бронь створено!\n\n"
        f"💰 Сума: {price} грн\n"
        f"💳 Передплата 10%: {deposit} грн\n\n"
        f"💳 Оплатити тут:\n{pay_url}"
    )
    if ADMIN_ID:
        await bot.send_message(
        ADMIN_ID,
        f"""
📥 НОВА БРОНЬ

👤 Ім'я: {d['name']}
📞 Телефон: {d['phone']}
📅 Дата: {d['date']}
⏰ Час: {d['time']}:00
⌛ Годин: {d['hours']}
🎮 Тариф: {TARIFFS[d['tariff']]['name']}
👥 Гостей: {d['guests']}

💬 Коментар:
{d['comment']}
"""
   )
     
    user_data.pop(uid, None)

       
# ---------------- RUN ----------------
@dp.message(Command("calendar"))
async def calendar(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    cursor.execute("""
        SELECT date, time, hours, name
        FROM bookings
        ORDER BY date, time
    """)

    rows = cursor.fetchall()

    if not rows:
        await m.answer("Броней немає")
        return

    text = "📅 КАЛЕНДАР БРОНЕЙ\n\n"

    for date, time, hours, name in rows:
        text += (
            f"📅 {date}\n"
            f"⏰ {time}:00\n"
            f"⌛ {hours} год\n"
            f"👤 {name}\n\n"
        )

    await m.answer(text)
async def main():
    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())