import json
import threading
import os

lock = threading.Lock()

def safe_load(filepath):
    """Carga un archivo JSON de forma segura"""
    try:
        if not os.path.exists(filepath):
            return {}
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error cargando {filepath}: {e}")
        return {}

def safe_save(filepath, data):
    """Guarda datos en JSON con lock para evitar corrupción"""
    with lock:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error guardando {filepath}: {e}")
            return False
