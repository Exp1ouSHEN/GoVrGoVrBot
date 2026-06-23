import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
MONO_TOKEN = os.getenv("MONO_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in environment variables")

if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)
else:
    raise ValueError("ADMIN_ID is missing")