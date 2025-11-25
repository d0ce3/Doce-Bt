import os
from discord import Object

# Token del bot
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# ID del servidor para pruebas (opcional, deja vacío para global)
GUILD_ID_STR = os.getenv('DISCORD_GUILD_ID', '')
GUILD_ID = int(GUILD_ID_STR) if GUILD_ID_STR else None

# Puerto para Flask
PORT = int(os.getenv('PORT', 10000))

# URL externa (Render, Railway, etc)
RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')

# Directorios
DATA_DIR = 'data'
LOGS_DIR = 'logs'

# Archivos de datos
VINCULACIONES_FILE = f'{DATA_DIR}/vinculaciones.json'
SESIONES_FILE = f'{DATA_DIR}/sesiones.json'

# Crear directorios si no existen
import os
for directory in [DATA_DIR, LOGS_DIR]:
    os.makedirs(directory, exist_ok=True)
