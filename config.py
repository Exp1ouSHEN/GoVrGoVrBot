BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)
MONO_TOKEN = os.getenv("MONO_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in environment variables")