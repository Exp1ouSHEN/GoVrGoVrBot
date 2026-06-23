BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
MONO_TOKEN = os.getenv("MONO_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()