import time
import requests
from config import RENDER_EXTERNAL_URL

def self_ping():
    """Realiza pings periódicos para mantener el servicio activo"""
    if not RENDER_EXTERNAL_URL:
        print("⚠️  RENDER_EXTERNAL_URL no configurado, self-ping desactivado")
        return

    time.sleep(120)  # Esperar 2 minutos antes del primer ping
    health_url = f"{RENDER_EXTERNAL_URL}/health"

    print(f"🔄 Self-ping activado: {health_url}")

    while True:
        try:
            time.sleep(600)  # Ping cada 10 minutos
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Self-ping OK [{time.strftime('%H:%M:%S')}]")
            else:
                print(f"⚠️  Self-ping: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ Self-ping error: {e}")
