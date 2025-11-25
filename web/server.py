from flask import Flask
from config import PORT

app = Flask(__name__)

bot_instance = None

def set_bot(bot):
    """Establece la instancia del bot"""
    global bot_instance
    bot_instance = bot

@app.route('/')
def home():
    return "✅ doce|tools v2 activo", 200

@app.route('/health')
def health():
    if bot_instance and bot_instance.is_ready():
        return {
            "status": "online",
            "bot": str(bot_instance.user),
            "guilds": len(bot_instance.guilds)
        }, 200
    else:
        return {"status": "starting"}, 503

def run_flask():
    """Ejecuta el servidor Flask"""
    print(f"🌐 Servidor Flask iniciando en puerto {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
