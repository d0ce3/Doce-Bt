import os
from discord import Object
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

GUILD_ID_STR = os.getenv('DISCORD_GUILD_ID', '')
GUILD_ID = int(GUILD_ID_STR) if GUILD_ID_STR else None

DATABASE_URL = os.getenv("DATABASE_URL")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

PORT = int(os.getenv('PORT', 10000))

RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')

BOT_WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook/tunnel_notify" if RENDER_EXTERNAL_URL else "http://localhost:10000/webhook/tunnel_notify"

DATA_DIR = 'data'
LOGS_DIR = 'logs'

VINCULACIONES_FILE = f'{DATA_DIR}/vinculaciones.json'
SESIONES_FILE = f'{DATA_DIR}/sesiones.json'
PERMISOS_FILE = f'{DATA_DIR}/permisos.json'

for directory in [DATA_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)