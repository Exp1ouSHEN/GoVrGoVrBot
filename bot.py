import asyncio
import sqlite3
import aiohttp
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# ---------------- CONFIG ----------------

from config import BOT_TOKEN, ADMIN_ID, MONO_TOKEN

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------- DB ----------------

conn = sqlite3.connect("bookings.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    time INTEGER,
    hours REAL,
    tariff TEXT,
    name TEXT,
    phone TEXT,
    guests TEXT,
    comment TEXT,
    status TEXT DEFAULT 'pending'
)
""")
conn.commit()

# ---------------- STATE ----------------

user_data = {}
admin_reply = {}
admin_mode = {}
wait_photo = {}

# Состояние этапа бронирования
booking_step = {}

# ---------------- FULL TARIFS (НЕ УРЕЗАНО) ----------------

TARIFFS = {
    "lite": {
        "name": "🎮 LITE",
        "prices": {1: 500, 2: 900, 3: 1300, 4: 1600}
    },
    "vip": {
        "name": "🔥 VIP + PS5",
        "prices": {1: 700, 2: 1300, 3: 1800, 4: 2300}
    },
    "2lite": {
        "name": "🎮 2 ЗОНИ LITE",
        "prices": {1: 1000, 2: 1800, 3: 2600, 4: 3200}
    },
    "2vip": {
        "name": "🔥 2 ЗОНИ VIP + PS5",
        "prices": {1: 1400, 2: 2600, 3: 3600, 4: 4600}
    },
    "birthday": {
        "name": "🎂 ДЕНЬ НАРОДЖЕННЯ",
        "prices": {1.5: 2500, 2: 3000, 3: 4000, 4: 5000}
    },
    "party": {
        "name": "⭐ VIP PARTY",
        "prices": {4: 8000}
    }
}

WORK_START = 10
WORK_END = 19


# ---------------- UI ----------------

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Забронювати")],
        [KeyboardButton(text="💰 Прайс")],
        [KeyboardButton(text="📞 Адміністратор")]
    ],
    resize_keyboard=True
)

# ---------------- CALENDAR ----------------

def get_dates():
    kb = []
    today = datetime.now()

    for i in range(7):
        d = (today + timedelta(days=i)).strftime("%Y-%m-%d")
        kb.append([InlineKeyboardButton(text=d, callback_data=f"date:{d}")])

    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_times(date):
    cursor.execute("SELECT time, hours FROM bookings WHERE date=?", (date,))
    rows = cursor.fetchall()

    busy = set()
    for t, h in rows:
        for i in range(int(h)):
            busy.add(t + i)

    kb = []

    for h in range(WORK_START, WORK_END):

        if h == 13:
            continue

        if h in busy:
            kb.append([InlineKeyboardButton(text=f"{h}:00 ❌", callback_data="none")])
        else:
            kb.append([InlineKeyboardButton(text=f"{h}:00", callback_data=f"time:{h}")])

    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_tariffs():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 LITE", callback_data="tariff:lite")],
        [InlineKeyboardButton(text="🔥 VIP + PS5", callback_data="tariff:vip")],
        [InlineKeyboardButton(text="🎮 2 ЗОНИ LITE", callback_data="tariff:2lite")],
        [InlineKeyboardButton(text="🔥 2 ЗОНИ VIP + PS5", callback_data="tariff:2vip")],
        [InlineKeyboardButton(text="🎂 ДЕНЬ НАРОДЖЕННЯ", callback_data="tariff:birthday")],
        [InlineKeyboardButton(text="⭐ VIP PARTY", callback_data="tariff:party")]
    ])

def get_hours(tariff):
    kb = []
    for h, price in TARIFFS[tariff]["prices"].items():
        kb.append([InlineKeyboardButton(
            text=f"{h}h - {price} грн",
            callback_data=f"hours:{h}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("👋 GoVr бот бронювання", reply_markup=menu)

# ---------------- PRICE ----------------

@dp.message(lambda m: m.text == "💰 Прайс")
async def price(m: types.Message):
    await m.answer(
        "💰 ПРАЙС:\n\n"
        "🎮 LITE: 1h 500 / 2h 900 / 3h 1300 / 4h 1600\n"
        "🔥 VIP: 1h 700 / 2h 1300 / 3h 1800 / 4h 2300\n"
        "🎮 2 ЗОНИ LITE: 1h 1000 / 2h 1800 / 3h 2600 / 4h 3200\n"
        "🔥 2 ЗОНИ VIP: 1h 1400 / 2h 2600 / 3h 3600 / 4h 4600\n"
        "🎂 BIRTHDAY: 1.5h 2500 / 2h3000 /  3h4000 / 4h5000\n"
        "⭐ PARTY: 8000 (4h)"
    )

# ---------------- BOOK ----------------

@dp.message(lambda m: m.text == "🎮 Забронювати")
async def book(m: types.Message):
    user_data[m.from_user.id] = {}
    await m.answer("📅 Оберіть дату:", reply_markup=get_dates())


# ---------------- FLOW ----------------

@dp.callback_query(lambda c: c.data.startswith("date:"))
async def date(c: types.CallbackQuery):
    uid = c.from_user.id

    user_data[uid] = {
        "date": c.data.split(":", 1)[1]
    }

    booking_step[uid] = "time"

    await c.message.edit_text(
        "⏰ Оберіть час:",
        reply_markup=get_times(user_data[uid]["date"])
    )
    await c.answer()


@dp.callback_query(lambda c: c.data.startswith("time:"))
async def time(c: types.CallbackQuery):
    uid = c.from_user.id

    if uid not in user_data:
        await c.answer("❌ Почніть бронювання заново.", show_alert=True)
        return

    user_data[uid]["time"] = int(c.data.split(":", 1)[1])
    booking_step[uid] = "tariff"

    await c.message.edit_text(
        "🎮 Оберіть тариф:",
        reply_markup=get_tariffs()
    )
    await c.answer()


@dp.callback_query(lambda c: c.data.startswith("tariff:"))
async def tariff(c: types.CallbackQuery):
    uid = c.from_user.id

    if uid not in user_data:
        await c.answer("❌ Почніть бронювання заново.", show_alert=True)
        return

    t = c.data.split(":", 1)[1]

    if t not in TARIFFS:
        await c.answer("❌ Тариф не знайдено.", show_alert=True)
        return

    user_data[uid]["tariff"] = t
    booking_step[uid] = "hours"

    await c.message.edit_text(
        f"{TARIFFS[t]['name']}\n\n⏱ Оберіть кількість годин:",
        reply_markup=get_hours(t)
    )
    await c.answer()


@dp.callback_query(lambda c: c.data.startswith("hours:"))
async def hours(c: types.CallbackQuery):
    uid = c.from_user.id

    if uid not in user_data:
        await c.answer("❌ Почніть бронювання заново.", show_alert=True)
        return

    tariff = user_data[uid].get("tariff")

    if not tariff or tariff not in TARIFFS:
        await c.answer("❌ Спочатку оберіть тариф.", show_alert=True)
        return

    h = float(c.data.split(":", 1)[1])

    if h not in TARIFFS[tariff]["prices"]:
        await c.answer(
            "❌ Така кількість годин недоступна.",
            show_alert=True
        )
        return

    user_data[uid]["hours"] = h
    booking_step[uid] = "name"

    await c.message.edit_text("👤 Введіть імʼя:")
    await c.answer()

# ---------------- BOOKING FORM ----------------

@dp.message(
    lambda m: (
        m.from_user.id in user_data
        and booking_step.get(m.from_user.id) in {
            "name",
            "phone",
            "guests",
            "comment"
        }
    )
)
async def booking_form(m: types.Message):

    uid = m.from_user.id
    step = booking_step.get(uid)
    d = user_data.get(uid)

    # Если состояния нет — ничего не делаем
    if not d or not step:
        return

    # Не принимаем команды/кнопки меню как данные формы
    if m.text in [
        "🎮 Забронювати",
        "💰 Прайс",
        "📞 Адміністратор"
    ]:
        return

    # ------------------------------------------------
    # ИМЯ
    # ------------------------------------------------

    if step == "name":

        if not m.text:
            await m.answer("👤 Будь ласка, введіть імʼя текстом.")
            return

        d["name"] = m.text.strip()

        booking_step[uid] = "phone"

        await m.answer("📞 Введіть номер телефону:")
        return

    # ------------------------------------------------
    # ТЕЛЕФОН
    # ------------------------------------------------

    if step == "phone":

        if not m.text:
            await m.answer("📞 Будь ласка, введіть номер телефону.")
            return

        d["phone"] = m.text.strip()

        booking_step[uid] = "guests"

        await m.answer("👥 Скільки буде гостей?")
        return

    # ------------------------------------------------
    # ГОСТИ
    # ------------------------------------------------

    if step == "guests":

        if not m.text:
            await m.answer("👥 Вкажіть кількість гостей.")
            return

        d["guests"] = m.text.strip()

        booking_step[uid] = "comment"

        await m.answer(
            "💬 Напишіть коментар до бронювання "
            "або напишіть «-», якщо коментаря немає."
        )
        return

    # ------------------------------------------------
    # КОММЕНТАРИЙ
    # ------------------------------------------------

    if step == "comment":

        if not m.text:
            await m.answer("💬 Введіть коментар або «-».")
            return

        d["comment"] = m.text.strip()

        # СРАЗУ меняем состояние, чтобы повторное сообщение
        # не создало вторую бронь
        booking_step.pop(uid, None)

        # ------------------------------------------------
        # СОЗДАНИЕ БРОНИ
        # ------------------------------------------------

        tariff = d["tariff"]
        hours_value = d["hours"]

        price = TARIFFS[tariff]["prices"][hours_value]
        deposit = round(price * 0.1)

        cursor.execute(
            """
            INSERT INTO bookings
            (date, time, hours, tariff, name, phone, guests, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d["date"],
                d["time"],
                d["hours"],
                d["tariff"],
                d["name"],
                d["phone"],
                d["guests"],
                d["comment"]
            )
        )

        conn.commit()

        # ------------------------------------------------
        # КНОПКИ ОПЛАТЫ
        # ------------------------------------------------

        pay_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Я оплатив",
                        callback_data="paid"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Скасувати бронювання",
                        callback_data="cancel"
                    )
                ]
            ]
        )

        # ------------------------------------------------
        # СООБЩЕНИЕ КЛИЕНТУ
        # ------------------------------------------------

        await m.answer(
            f"""✅ Бронювання створено!

📅 Дата: {d['date']}
⏰ Час: {d['time']}:00
🎮 Тариф: {TARIFFS[tariff]['name']}
⌛ Тривалість: {d['hours']} год.

💰 Повна сума: {price} грн
💳 Передоплата (10%): {deposit} грн

Оплатіть передоплату на картку:

Денис Ф. В.
💳 IBAN: UA493220010000026001380009480
ІПН/ЄДРПОУ: 3579512999

Після оплати натисніть кнопку нижче.
""",
            reply_markup=pay_kb
        )

        # ------------------------------------------------
        # СООБЩЕНИЕ АДМИНУ
        # ------------------------------------------------

        text = f"""
📥 НОВА БРОНЬ

👤 {d['name']}
📞 {d['phone']}
📅 {d['date']} {d['time']}:00
🎮 {TARIFFS[tariff]['name']}
⌛ {d['hours']}h
👥 {d['guests']}

💬 {d['comment']}

💰 Сума: {price} грн
💳 Передоплата: {deposit} грн
"""

        await bot.send_message(ADMIN_ID, text)

        # После успешной записи удаляем данные формы
        user_data.pop(uid, None)

        return

# ---------------- ADMIN CHAT ----------------

@dp.message(lambda m: m.text == "📞 Адміністратор")
async def admin(m: types.Message):
    admin_mode[m.from_user.id] = True
    await m.answer("Напиши повідомлення адміну:")

@dp.message(lambda m: m.from_user.id in admin_mode)
async def admin_msg(m: types.Message):
    uid = m.from_user.id
    admin_mode.pop(uid, None)

    admin_reply[ADMIN_ID] = uid

    await bot.send_message(
        ADMIN_ID,
        f"📩 Від @{m.from_user.username}\n\n{m.text}"
    )

    await m.answer("✅ Відправлено")

@dp.message(lambda m: m.from_user.id == ADMIN_ID)
async def admin_answer(m: types.Message):
    uid = admin_reply.get(ADMIN_ID)
    if not uid:
        return

    await bot.send_message(uid, f"💬 Адмін: {m.text}")
    await m.answer("✔️ Відправлено")


# ---------------- PAYMENT ----------------

@dp.callback_query(lambda c: c.data == "paid")
async def paid(c: types.CallbackQuery):

    wait_photo[c.from_user.id] = True

    await c.message.answer("📷 Надішліть скріншот оплати.")
    await c.answer()


@dp.callback_query(lambda c: c.data == "cancel")
async def cancel(c: types.CallbackQuery):

    user_data.pop(c.from_user.id, None)
    wait_photo.pop(c.from_user.id, None)

    await c.message.answer("❌ Бронювання скасовано.")
    await c.answer()


@dp.message(lambda m: m.photo and m.from_user.id in wait_photo)
async def payment_photo(m: types.Message):

    wait_photo.pop(m.from_user.id)
    user_data.pop(m.from_user.id, None)

    await bot.send_photo(
        ADMIN_ID,
        m.photo[-1].file_id,
        caption=f"""
💳 Нова оплата

👤 {m.from_user.full_name}
📱 @{m.from_user.username}
🆔 {m.from_user.id}

Перевірте оплату.
"""
    )

    await m.answer(
        "✅ Скріншот отримано.\nАдміністратор перевірить оплату."
    )


# ---------------- RUN ----------------

from aiohttp import web
import os
import asyncio

async def health(request):
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 10000))

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=port
    )

    await site.start()

    print(f"Web server started on {port}")

    print("DELETE WEBHOOK")
    await bot.delete_webhook(drop_pending_updates=True)

    print("START POLLING")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())