import aiosqlite

DB_NAME = "bookings.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            duration INTEGER,
            name TEXT,
            phone TEXT,
            guests INTEGER,
            comment TEXT
        )
        """)
        await db.commit()


async def add_booking(date, time, duration, name, phone, guests, comment):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        INSERT INTO bookings (date, time, duration, name, phone, guests, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date, time, duration, name, phone, guests, comment))
        await db.commit()


async def get_booked_times(date):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT time, duration FROM bookings WHERE date = ?",
            (date,)
        )
        return await cursor.fetchall()