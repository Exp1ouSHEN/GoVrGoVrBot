import asyncio
import sqlite3
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from aiohttp import web

from config import BOT_TOKEN, ADMIN_ID, MONO_TOKEN


# ============================================================
# CONFIG
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# DATABASE
# ============================================================

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

# Добавляем недостающие колонки в старую БД
cursor.execute("PRAGMA table_info(bookings)")
columns = [row[1] for row in cursor.fetchall()]

if "hours" not in columns:
    cursor.execute("ALTER TABLE bookings ADD COLUMN hours REAL")

if "tariff" not in columns:
    cursor.execute("ALTER TABLE bookings ADD COLUMN tariff TEXT")

if "name" not in columns:
    cursor.execute("ALTER TABLE bookings ADD COLUMN name TEXT")

if "phone" not in columns:
    cursor.execute("ALTER TABLE bookings ADD COLUMN phone TEXT")

if "guests" not in columns:
    cursor.execute("ALTER TABLE bookings ADD COLUMN guests TEXT")

if "comment" not in columns:
    cursor.execute("ALTER TABLE bookings ADD COLUMN comment TEXT")

if "status" not in columns:
    cursor.execute(
        "ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT 'pending'"
    )

conn.commit()


# ============================================================
# STATE
# ============================================================

user_data = {}
booking_step = {}

admin_reply = {}
admin_mode = {}

# user_id -> booking_id
wait_photo = {}


# ============================================================
# TARIFFS
# ============================================================

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

    "2lite": {
        "name": "🎮 2 ЗОНИ LITE",
        "prices": {
            1: 1000,
            2: 1800,
            3: 2600,
            4: 3200
        }
    },

    "2vip": {
        "name": "🔥 2 ЗОНИ VIP + PS5",
        "prices": {
            1: 1400,
            2: 2600,
            3: 3600,
            4: 4600
        }
    },

    "birthday": {
        "name": "🎂 ДЕНЬ НАРОДЖЕННЯ",
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


WORK_START = 10
WORK_END = 19


# ============================================================
# MAIN MENU
# ============================================================

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎮 Забронювати")],
        [KeyboardButton(text="💰 Прайс")],
        [KeyboardButton(text="📞 Адміністратор")]
    ],
    resize_keyboard=True
)


# ============================================================
# CALENDAR
# ============================================================

def get_dates():

    kb = []

    today = datetime.now()

    for i in range(7):

        d = (
            today + timedelta(days=i)
        ).strftime("%Y-%m-%d")

        kb.append([
            InlineKeyboardButton(
                text=d,
                callback_data=f"date:{d}"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=kb
    )


# ============================================================
# TIMES
# ============================================================

def get_times(date):

    cursor.execute(
        """
        SELECT time, hours
        FROM bookings
        WHERE date=?
        AND status NOT IN ('cancelled')
        """,
        (date,)
    )

    rows = cursor.fetchall()

    busy = set()

    for t, h in rows:

        if h is None:
            continue

        for i in range(int(h)):
            busy.add(t + i)

    kb = []

    for h in range(WORK_START, WORK_END):

        # Перерыв
        if h == 13:
            continue

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

    return InlineKeyboardMarkup(
        inline_keyboard=kb
    )


# ============================================================
# TARIFF BUTTONS
# ============================================================

def get_tariffs():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎮 LITE",
                    callback_data="tariff:lite"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔥 VIP + PS5",
                    callback_data="tariff:vip"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🎮 2 ЗОНИ LITE",
                    callback_data="tariff:2lite"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔥 2 ЗОНИ VIP + PS5",
                    callback_data="tariff:2vip"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🎂 ДЕНЬ НАРОДЖЕННЯ",
                    callback_data="tariff:birthday"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⭐ VIP PARTY",
                    callback_data="tariff:party"
                )
            ]
        ]
    )


# ============================================================
# HOURS
# ============================================================

def get_hours(tariff):

    kb = []

    for h, price in TARIFFS[tariff]["prices"].items():

        kb.append([
            InlineKeyboardButton(
                text=f"{h}h - {price} грн",
                callback_data=f"hours:{h}"
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=kb
    )


# ============================================================
# START
# ============================================================

@dp.message(Command("start"))
async def start(m: types.Message):

    # Сбрасываем старое состояние
    user_data.pop(m.from_user.id, None)
    booking_step.pop(m.from_user.id, None)
    wait_photo.pop(m.from_user.id, None)

    await m.answer(
        "👋 GoVr бот бронювання",
        reply_markup=menu
    )


# ============================================================
# PRICE
# ============================================================

@dp.message(lambda m: m.text == "💰 Прайс")
async def price(m: types.Message):

    await m.answer(
        "💰 ПРАЙС:\n\n"

        "🎮 LITE:\n"
        "1h — 500 грн\n"
        "2h — 900 грн\n"
        "3h — 1300 грн\n"
        "4h — 1600 грн\n\n"

        "🔥 VIP + PS5:\n"
        "1h — 700 грн\n"
        "2h — 1300 грн\n"
        "3h — 1800 грн\n"
        "4h — 2300 грн\n\n"

        "🎮 2 ЗОНИ LITE:\n"
        "1h — 1000 грн\n"
        "2h — 1800 грн\n"
        "3h — 2600 грн\n"
        "4h — 3200 грн\n\n"

        "🔥 2 ЗОНИ VIP + PS5:\n"
        "1h — 1400 грн\n"
        "2h — 2600 грн\n"
        "3h — 3600 грн\n"
        "4h — 4600 грн\n\n"

        "🎂 ДЕНЬ НАРОДЖЕННЯ:\n"
        "1.5h — 2500 грн\n"
        "2h — 3000 грн\n"
        "3h — 4000 грн\n"
        "4h — 5000 грн\n\n"

        "⭐ VIP PARTY:\n"
        "4h — 8000 грн"
    )


# ============================================================
# START BOOKING
# ============================================================

@dp.message(lambda m: m.text == "🎮 Забронювати")
async def book(m: types.Message):

    uid = m.from_user.id

    # Полностью очищаем старое состояние
    user_data.pop(uid, None)
    booking_step.pop(uid, None)
    wait_photo.pop(uid, None)

    await m.answer(
        "📅 Оберіть дату:",
        reply_markup=get_dates()
    )


# ============================================================
# DATE
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("date:"))
async def date(c: types.CallbackQuery):

    uid = c.from_user.id

    selected_date = c.data.split(":", 1)[1]

    user_data[uid] = {
        "date": selected_date
    }

    booking_step[uid] = "time"

    await c.message.edit_text(
        "⏰ Оберіть час:",
        reply_markup=get_times(selected_date)
    )

    await c.answer()


# ============================================================
# TIME
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("time:"))
async def time(c: types.CallbackQuery):

    uid = c.from_user.id

    if uid not in user_data:

        await c.answer(
            "❌ Почніть бронювання заново.",
            show_alert=True
        )

        return

    selected_time = int(
        c.data.split(":", 1)[1]
    )

    user_data[uid]["time"] = selected_time

    booking_step[uid] = "tariff"

    await c.message.edit_text(
        "🎮 Оберіть тариф:",
        reply_markup=get_tariffs()
    )

    await c.answer()


# ============================================================
# TARIFF
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("tariff:"))
async def tariff(c: types.CallbackQuery):

    uid = c.from_user.id

    if uid not in user_data:

        await c.answer(
            "❌ Почніть бронювання заново.",
            show_alert=True
        )

        return

    t = c.data.split(":", 1)[1]

    if t not in TARIFFS:

        await c.answer(
            "❌ Тариф не знайдено.",
            show_alert=True
        )

        return

    user_data[uid]["tariff"] = t

    booking_step[uid] = "hours"

    await c.message.edit_text(
        f"{TARIFFS[t]['name']}\n\n"
        "⏱ Оберіть кількість годин:",
        reply_markup=get_hours(t)
    )

    await c.answer()


# ============================================================
# HOURS
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("hours:"))
async def hours(c: types.CallbackQuery):

    uid = c.from_user.id

    if uid not in user_data:

        await c.answer(
            "❌ Почніть бронювання заново.",
            show_alert=True
        )

        return

    tariff = user_data[uid].get("tariff")

    if not tariff or tariff not in TARIFFS:

        await c.answer(
            "❌ Спочатку оберіть тариф.",
            show_alert=True
        )

        return

    h = float(
        c.data.split(":", 1)[1]
    )

    if h not in TARIFFS[tariff]["prices"]:

        await c.answer(
            "❌ Така кількість годин недоступна.",
            show_alert=True
        )

        return

    user_data[uid]["hours"] = h

    booking_step[uid] = "name"

    await c.message.edit_text(
        "👤 Введіть імʼя:"
    )

    await c.answer()


# ============================================================
# BOOKING FORM
# ============================================================

@dp.message(
    lambda m: (
        m.from_user.id in user_data
        and booking_step.get(m.from_user.id)
        in {
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

    if not d or not step:
        return

    # Не принимаем кнопки меню как данные
    if m.text in [
        "🎮 Забронювати",
        "💰 Прайс",
        "📞 Адміністратор"
    ]:
        return


    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    if step == "name":

        if not m.text:

            await m.answer(
                "👤 Будь ласка, введіть імʼя текстом."
            )

            return

        d["name"] = m.text.strip()

        booking_step[uid] = "phone"

        await m.answer(
            "📞 Введіть номер телефону:"
        )

        return


    # --------------------------------------------------------
    # PHONE
    # --------------------------------------------------------

    if step == "phone":

        if not m.text:

            await m.answer(
                "📞 Будь ласка, введіть номер телефону."
            )

            return

        d["phone"] = m.text.strip()

        booking_step[uid] = "guests"

        await m.answer(
            "👥 Скільки буде гостей?"
        )

        return


    # --------------------------------------------------------
    # GUESTS
    # --------------------------------------------------------

    if step == "guests":

        if not m.text:

            await m.answer(
                "👥 Вкажіть кількість гостей."
            )

            return

        d["guests"] = m.text.strip()

        booking_step[uid] = "comment"

        await m.answer(
            "💬 Напишіть коментар до бронювання "
            "або напишіть «-», якщо коментаря немає."
        )

        return


    # --------------------------------------------------------
    # COMMENT
    # --------------------------------------------------------

    if step == "comment":

        if not m.text:

            await m.answer(
                "💬 Введіть коментар або «-»."
            )

            return

        d["comment"] = m.text.strip()

        tariff_key = d["tariff"]
        hours_value = d["hours"]

        price = TARIFFS[tariff_key]["prices"][hours_value]

        deposit = round(price * 0.1)


        # ----------------------------------------------------
        # ПРОВЕРЯЕМ, НЕ ЗАНЯТО ЛИ ВРЕМЯ
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT id, time, hours, status
            FROM bookings
            WHERE date=?
            AND status NOT IN ('cancelled')
            """,
            (d["date"],)
        )

        existing = cursor.fetchall()

        requested_start = d["time"]
        requested_end = requested_start + int(hours_value)

        for booking in existing:

            old_time = booking[1]
            old_hours = booking[2]

            if old_hours is None:
                continue

            old_start = old_time
            old_end = old_time + int(old_hours)

            # Проверка пересечения
            if (
                requested_start < old_end
                and requested_end > old_start
            ):

                booking_step.pop(uid, None)
                user_data.pop(uid, None)

                await m.answer(
                    "❌ На жаль, цей час вже зайнятий.\n\n"
                    "Будь ласка, почніть бронювання заново.",
                    reply_markup=menu
                )

                return


        # ----------------------------------------------------
        # ПРОВЕРКА ПЕРЕРЫВА 13:00
        # ----------------------------------------------------

        if (
            d["time"] < 13
            and d["time"] + hours_value > 13
        ):

            await m.answer(
                "❌ Бронювання не може проходити через "
                "перерву 13:00–14:00.\n\n"
                "Оберіть інший час."
            )

            booking_step[uid] = "time"

            await m.answer(
                "⏰ Оберіть час:",
                reply_markup=get_times(d["date"])
            )

            return


        # ----------------------------------------------------
        # ПРОВЕРКА 19:00
        # ----------------------------------------------------

        if d["time"] + hours_value > WORK_END:

            await m.answer(
                "❌ Бронювання не може закінчуватися "
                "після 19:00."
            )

            booking_step[uid] = "time"

            await m.answer(
                "⏰ Оберіть час:",
                reply_markup=get_times(d["date"])
            )

            return


        # ----------------------------------------------------
        # СОЗДАЕМ БРОНЬ
        # ----------------------------------------------------

        cursor.execute(
            """
            INSERT INTO bookings
            (
                date,
                time,
                hours,
                tariff,
                name,
                phone,
                guests,
                comment,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d["date"],
                d["time"],
                d["hours"],
                d["tariff"],
                d["name"],
                d["phone"],
                d["guests"],
                d["comment"],
                "awaiting_payment"
            )
        )

        conn.commit()

        booking_id = cursor.lastrowid


        # ----------------------------------------------------
        # ОЧИЩАЕМ СОСТОЯНИЕ ФОРМЫ
        # ----------------------------------------------------

        booking_step.pop(uid, None)

        user_data.pop(uid, None)


        # ----------------------------------------------------
        # КНОПКИ ОПЛАТЫ
        # ----------------------------------------------------

        pay_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Я оплатив",
                        callback_data=f"paid:{booking_id}"
                    )
                ],

                [
                    InlineKeyboardButton(
                        text="❌ Скасувати бронювання",
                        callback_data=f"cancel:{booking_id}"
                    )
                ]
            ]
        )


        # ----------------------------------------------------
        # КЛИЕНТУ
        # ----------------------------------------------------

        await m.answer(
            f"""
✅ Бронювання створено!

📋 Номер бронювання: #{booking_id}

📅 Дата: {d['date']}
⏰ Час: {d['time']}:00
🎮 Тариф: {TARIFFS[tariff_key]['name']}
⌛ Тривалість: {d['hours']} год.

💰 Повна сума: {price} грн
💳 Передоплата 10%: {deposit} грн

Оплатіть передоплату:

Денис Ф. В.

💳 IBAN:
UA493220010000026001380009480

ІПН/ЄДРПОУ:
3579512999

Після оплати натисніть:

«✅ Я оплатив»

Після цього бот попросить надіслати
скріншот оплати.
""",
            reply_markup=pay_kb
        )


        # ----------------------------------------------------
        # АДМИНУ
        # ----------------------------------------------------

        admin_text = f"""
📥 НОВА БРОНЬ #{booking_id}

👤 Ім'я: {d['name']}
📞 Телефон: {d['phone']}

📅 Дата: {d['date']}
⏰ Час: {d['time']}:00

🎮 Тариф:
{TARIFFS[tariff_key]['name']}

⌛ Тривалість:
{d['hours']} год.

👥 Гості:
{d['guests']}

💬 Коментар:
{d['comment']}

💰 Сума:
{price} грн

💳 Передоплата:
{deposit} грн

⏳ Статус:
ОЧІКУЄТЬСЯ ОПЛАТА
"""

        await bot.send_message(
            ADMIN_ID,
            admin_text
        )

        return


# ============================================================
# ADMIN BUTTON
# ============================================================

@dp.message(lambda m: m.text == "📞 Адміністратор")
async def admin(m: types.Message):

    uid = m.from_user.id

    admin_mode[uid] = True

    await m.answer(
        "Напиши повідомлення адміну:"
    )


# ============================================================
# ADMIN MESSAGE FROM CLIENT
# ============================================================

@dp.message(lambda m: m.from_user.id in admin_mode)
async def admin_msg(m: types.Message):

    uid = m.from_user.id

    admin_mode.pop(uid, None)

    admin_reply[ADMIN_ID] = uid

    await bot.send_message(
        ADMIN_ID,
        f"📩 Від @{m.from_user.username or 'без username'}\n\n"
        f"{m.text}"
    )

    await m.answer(
        "✅ Відправлено"
    )


# ============================================================
# ADMIN ANSWER
# ============================================================

@dp.message(lambda m: m.from_user.id == ADMIN_ID)
async def admin_answer(m: types.Message):

    uid = admin_reply.get(ADMIN_ID)

    if not uid:
        return

    await bot.send_message(
        uid,
        f"💬 Адмін: {m.text}"
    )

    await m.answer(
        "✔️ Відправлено"
    )


# ============================================================
# PAYMENT — BUTTON "I PAID"
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("paid:"))
async def paid(c: types.CallbackQuery):

    uid = c.from_user.id

    try:

        booking_id = int(
            c.data.split(":", 1)[1]
        )

    except (ValueError, IndexError):

        await c.answer(
            "❌ Помилка бронювання.",
            show_alert=True
        )

        return


    # --------------------------------------------------------
    # ИЩЕМ БРОНЬ
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            id,
            date,
            time,
            hours,
            tariff,
            name,
            phone,
            guests,
            comment,
            status
        FROM bookings
        WHERE id=?
        """,
        (booking_id,)
    )

    booking = cursor.fetchone()


    if not booking:

        await c.answer(
            "❌ Бронювання не знайдено.",
            show_alert=True
        )

        return


    # --------------------------------------------------------
    # ПРОВЕРКА СТАТУСА
    # --------------------------------------------------------

    if booking[9] == "cancelled":

        await c.answer(
            "❌ Це бронювання вже скасовано.",
            show_alert=True
        )

        return


    if booking[9] == "paid":

        await c.answer(
            "✅ Оплата вже отримана.",
            show_alert=True
        )

        return


    # --------------------------------------------------------
    # ЖДЕМ ФОТО
    # --------------------------------------------------------

    wait_photo[uid] = booking_id

    await c.message.answer(
        f"""
📷 Надішліть скріншот оплати.

Бронювання #{booking_id}

📅 {booking[1]}
⏰ {booking[2]}:00

Після відправки скріншота
він автоматично прийде адміністратору.
"""
    )

    await c.answer()


# ============================================================
# CANCEL BOOKING
# ============================================================

@dp.callback_query(lambda c: c.data.startswith("cancel:"))
async def cancel(c: types.CallbackQuery):

    uid = c.from_user.id

    try:

        booking_id = int(
            c.data.split(":", 1)[1]
        )

    except (ValueError, IndexError):

        await c.answer(
            "❌ Помилка.",
            show_alert=True
        )

        return


    cursor.execute(
        """
        UPDATE bookings
        SET status='cancelled'
        WHERE id=?
        AND status!='paid'
        """,
        (booking_id,)
    )

    conn.commit()

    wait_photo.pop(uid, None)
    user_data.pop(uid, None)
    booking_step.pop(uid, None)

    await c.message.answer(
        "❌ Бронювання скасовано."
    )

    await c.answer()


# ============================================================
# PAYMENT SCREENSHOT
# ============================================================

@dp.message(
    lambda m: (
        m.photo
        and m.from_user.id in wait_photo
    )
)
async def payment_photo(m: types.Message):

    uid = m.from_user.id

    booking_id = wait_photo.pop(
        uid,
        None
    )


    if not booking_id:

        await m.answer(
            "❌ Бронювання не знайдено.\n"
            "Натисніть «Я оплатив» ще раз."
        )

        return


    # --------------------------------------------------------
    # ПОЛУЧАЕМ БРОНЬ
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            id,
            date,
            time,
            hours,
            tariff,
            name,
            phone,
            guests,
            comment,
            status
        FROM bookings
        WHERE id=?
        """,
        (booking_id,)
    )

    booking = cursor.fetchone()


    if not booking:

        await m.answer(
            "❌ Бронювання не знайдено."
        )

        return


    # --------------------------------------------------------
    # ЕСЛИ ОНА УЖЕ ОПЛАЧЕНА
    # --------------------------------------------------------

    if booking[9] == "paid":

        await m.answer(
            "✅ Ця оплата вже була отримана."
        )

        return


    # --------------------------------------------------------
    # МЕНЯЕМ СТАТУС
    # --------------------------------------------------------

    cursor.execute(
        """
        UPDATE bookings
        SET status='paid'
        WHERE id=?
        """,
        (booking_id,)
    )

    conn.commit()


    # --------------------------------------------------------
    # НАЗВАНИЕ ТАРИФА
    # --------------------------------------------------------

    tariff_name = TARIFFS.get(
        booking[4],
        {}
    ).get(
        "name",
        booking[4]
    )


    # --------------------------------------------------------
    # ОТПРАВЛЯЕМ СКРИН АДМИНУ
    # --------------------------------------------------------

    await bot.send_photo(
        ADMIN_ID,
        m.photo[-1].file_id,

        caption=f"""
💳 ОПЛАТА ПО БРОНИ #{booking_id}

👤 Ім'я:
{booking[5]}

📞 Телефон:
{booking[6]}

📅 Дата:
{booking[1]}

⏰ Час:
{booking[2]}:00

🎮 Тариф:
{tariff_name}

⌛ Тривалість:
{booking[3]} год.

👥 Гості:
{booking[7]}

💬 Коментар:
{booking[8]}

🟢 СТАТУС:
ОПЛАТА ОТРИМАНА

👤 Telegram:
{m.from_user.full_name}

📱 @{m.from_user.username or 'немає'}

🆔 ID:
{uid}
"""
    )


    # --------------------------------------------------------
    # КЛИЕНТУ
    # --------------------------------------------------------

    await m.answer(
        "✅ Скріншот отримано!\n\n"
        "Бронювання передано адміністратору "
        "на перевірку."
    )


# ============================================================
# HEALTH SERVER FOR RENDER
# ============================================================

async def health(request):

    return web.Response(
        text="OK"
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    runner = web.AppRunner(app)

    await runner.setup()

    port = int(
        os.getenv(
            "PORT",
            10000
        )
    )

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=port
    )

    await site.start()

    print(
        f"Web server started on {port}"
    )

    print(
        "DELETE WEBHOOK"
    )

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    print(
        "START POLLING"
    )

    await dp.start_polling(
        bot
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())