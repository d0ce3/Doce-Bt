import discord
from flask import request, jsonify
from utils.embed_factory import crear_embed_error, crear_embed_warning
from utils.jsondb import safe_load
from config import VINCULACIONES_FILE


def registrar_webhooks(app, bot_instance_getter):
    """
    Registra los endpoints de webhook en la app Flask
    
    Args:
        app: Instancia de Flask
        bot_instance_getter: Función que retorna la instancia del bot
    """
    
    @app.route('/webhook/megacmd', methods=['POST'])
    def webhook_megacmd():
        """
        Recibe notificaciones de errores de MegaCMD
        
        JSON esperado:
        {
            "user_id": "123456789",
            "error_type": "backup_compression" | "backup_upload" | "backup_general",
            "error_message": "Mensaje de error",
            "codespace_name": "nombre-del-codespace",
            "timestamp": "2025-01-01T12:00:00"
        }
        """
        try:
            bot = bot_instance_getter()
            if not bot:
                return jsonify({"error": "Bot no disponible"}), 503
            
            data = request.json
            
            if not data:
                return jsonify({"error": "No se recibieron datos"}), 400
            
            user_id = data.get("user_id")
            error_type = data.get("error_type", "backup_general")
            error_message = data.get("error_message", "Error desconocido")
            codespace_name = data.get("codespace_name", "Desconocido")
            
            if not user_id:
                return jsonify({"error": "user_id requerido"}), 400
            
            # Buscar el usuario en vinculaciones
            vinculaciones = safe_load(VINCULACIONES_FILE)
            
            if str(user_id) not in vinculaciones:
                return jsonify({"error": "Usuario no encontrado"}), 404
            
            # Mapear tipos de error a títulos y descripciones
            error_info = {
                "backup_compression": {
                    "title": "❌ Error en Compresión de Backup",
                    "description": (
                        f"**Codespace:** `{codespace_name}`\n\n"
                        f"Hubo un error al comprimir el backup:\n"
                        f"```{error_message}```\n\n"
                        "Posibles causas:\n"
                        "• Espacio insuficiente en disco\n"
                        "• Archivos corruptos\n"
                        "• Permisos insuficientes"
                    )
                },
                "backup_upload": {
                    "title": "❌ Error al Subir Backup a MEGA",
                    "description": (
                        f"**Codespace:** `{codespace_name}`\n\n"
                        f"El backup se comprimió correctamente, pero falló la subida a MEGA:\n"
                        f"```{error_message}```\n\n"
                        "Posibles causas:\n"
                        "• Sesión de MEGA expirada\n"
                        "• Espacio insuficiente en MEGA\n"
                        "• Problemas de conectividad"
                    )
                },
                "backup_general": {
                    "title": "❌ Error en Backup Automático",
                    "description": (
                        f"**Codespace:** `{codespace_name}`\n\n"
                        f"Error durante el proceso de backup:\n"
                        f"```{error_message}```"
                    )
                }
            }
            
            error_config = error_info.get(error_type, error_info["backup_general"])
            
            # Crear embed según el tipo de error
            embed = crear_embed_error(
                error_config["title"],
                error_config["description"],
                footer="Revisa los logs de MegaCMD para más detalles"
            )
            
            # Enviar DM al usuario
            try:
                # Usar asyncio para ejecutar la coroutine desde Flask
                import asyncio
                
                # Obtener el loop del bot
                loop = bot.loop
                
                # Crear la tarea de envío
                async def send_notification():
                    try:
                        user = await bot.fetch_user(int(user_id))
                        await user.send(embed=embed)
                        return True, "Notificación enviada"
                    except discord.Forbidden:
                        return False, "No se pudo enviar DM (usuario tiene DMs bloqueados)"
                    except discord.NotFound:
                        return False, "Usuario no encontrado"
                    except Exception as e:
                        return False, f"Error enviando notificación: {str(e)}"
                
                # Ejecutar de forma asíncrona
                future = asyncio.run_coroutine_threadsafe(send_notification(), loop)
                success, message = future.result(timeout=10)
                
                if success:
                    return jsonify({
                        "status": "success",
                        "message": message
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "message": message
                    }), 400
                    
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "message": f"Error procesando notificación: {str(e)}"
                }), 500
        
        except Exception as e:
            print(f"Error en webhook MegaCMD: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/webhook/test', methods=['POST'])
    def webhook_test():
        """Endpoint de prueba para verificar que los webhooks funcionan"""
        data = request.json
        return jsonify({
            "status": "success",
            "received": data,
            "message": "Webhook funcionando correctamente"
        }), 200
