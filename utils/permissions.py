from utils.jsondb import safe_load
from config import VINCULACIONES_FILE, SESIONES_FILE
from datetime import datetime

def obtener_contexto_usuario(calling_id):
    """
    Obtiene el contexto de control para un usuario.
    Retorna: (owner_id, codespace, sesion) o (None, None, None)
    """
    calling_id = str(calling_id)
    vinculaciones = safe_load(VINCULACIONES_FILE)
    sesiones = safe_load(SESIONES_FILE)

    # Es el propietario?
    if calling_id in vinculaciones:
        owner_id = calling_id
        codespace = vinculaciones[owner_id].get("codespace")
        sesion = sesiones.get(owner_id)
        return owner_id, codespace, sesion

    # Tiene permisos de algún propietario?
    for owner_id, data in vinculaciones.items():
        permisos = data.get("permisos", [])
        if int(calling_id) in permisos or calling_id in permisos:
            codespace = data.get("codespace")
            sesion = sesiones.get(owner_id)
            return owner_id, codespace, sesion

    return None, None, None

def sesion_valida(sesion):
    """Verifica si una sesión aún es válida"""
    if not sesion:
        return False

    expira_str = sesion.get("expira")
    if not expira_str:
        return False

    try:
        expira = datetime.fromisoformat(expira_str)
        return datetime.now() < expira
    except:
        return False

def puede_controlar(calling_id, owner_id):
    """Verifica si un usuario puede controlar el codespace de otro"""
    calling_id = str(calling_id)
    owner_id = str(owner_id)

    if calling_id == owner_id:
        return True

    vinculaciones = safe_load(VINCULACIONES_FILE)
    permisos = vinculaciones.get(owner_id, {}).get("permisos", [])

    return int(calling_id) in permisos or calling_id in permisos
