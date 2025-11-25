import asyncio
from utils.jsondb import safe_load
from config import VINCULACIONES_FILE

def obtener_usuario_por_codespace(codespace_name: str):
    """
    Busca y devuelve el Discord user ID propietario del codespace dado.
    Retorna None si no se encuentra propietario.
    """
    vinculaciones = safe_load(VINCULACIONES_FILE)
    for user_id, data in vinculaciones.items():
        if data.get("codespace") == codespace_name:
            return user_id
    return None

async def enviar_log_al_propietario(bot, codespace_name: str, mensaje: str):
    """
    Envía un mensaje directo (DM) al propietario del codespace con el log/mensaje dado.
    Debe ser llamada desde contexto async o con asyncio.create_task.
    """
    user_id = obtener_usuario_por_codespace(codespace_name)
    if not user_id:
        print(f"⚠️ No se encontró propietario para codespace '{codespace_name}'")
        return

    user = bot.get_user(int(user_id))
    if user is None:
        # Intentar obtener usuario desde API si no está en caché
        try:
            user = await bot.fetch_user(int(user_id))
        except Exception as e:
            print(f"❌ Error obteniendo usuario {user_id} desde API: {e}")
            return

    try:
        await user.send(f"📡 Notificación de tu Codespace `{codespace_name}`:\n{mensaje}")
        print(f"✅ Mensaje enviado a propietario <@{user_id}>")
    except Exception as e:
        print(f"❌ Error enviando DM a <@{user_id}>: {e}")
