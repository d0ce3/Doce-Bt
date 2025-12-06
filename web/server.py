from flask import Flask, request, jsonify
from utils.database import get_db
from datetime import datetime
import asyncio

app = Flask(__name__)
bot_instance = None

def set_bot(bot):
    global bot_instance
    bot_instance = bot

def get_bot():
    return bot_instance

@app.route('/api/user/config/<discord_user_id>', methods=['GET'])
def get_user_config(discord_user_id):
    try:
        db = get_db()
        sesion = db.get_sesion(discord_user_id)
        
        if not sesion:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        return jsonify({
            "discord_user_id": discord_user_id,
            "github_username": sesion.get("github_username"),
            "codespace_name": sesion.get("codespace"),
            "repo_name": sesion.get("repo_name"),
            "tunnel_url": sesion.get("tunnel_url"),
            "tunnel_port": sesion.get("tunnel_port"),
            "tunnel_type": sesion.get("tunnel_type"),
            "webhook_url": f"{request.host_url.rstrip('/')}/webhook/tunnel_notify",
            "auto_configured": sesion.get("auto_configured", False)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/user/tunnel', methods=['POST'])
def update_tunnel_url():
    try:
        data = request.json
        
        user_id = data.get("discord_user_id")
        tunnel_url = data.get("tunnel_url")
        tunnel_type = data.get("tunnel_type", "cloudflare")
        tunnel_port = data.get("tunnel_port", 25565)
        
        if not user_id or not tunnel_url:
            return jsonify({"error": "Faltan campos requeridos"}), 400
        
        db = get_db()
        sesion = db.get_sesion(user_id)
        
        if not sesion:
            return jsonify({"error": "Usuario no encontrado"}), 404
        
        sesion["tunnel_url"] = tunnel_url
        sesion["tunnel_type"] = tunnel_type
        sesion["tunnel_port"] = tunnel_port
        sesion["tunnel_actualizado"] = datetime.now().isoformat()
        
        db.save_sesion(user_id, sesion)
        
        return jsonify({
            "status": "success",
            "message": "Tunnel URL actualizada",
            "tunnel_url": tunnel_url
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/tunnel_notify', methods=['POST'])
def webhook_tunnel_notify():
    try:
        bot = get_bot()
        if not bot:
            return jsonify({"error": "Bot no disponible"}), 503

        data = request.json
        if not data:
            return jsonify({"error": "No se recibieron datos"}), 400

        user_id = data.get("user_id")
        codespace_name = data.get("codespace_name")
        tunnel_type = data.get("tunnel_type", "cloudflare")
        tunnel_host = data.get("tunnel_url")
        tunnel_port = data.get("tunnel_port", 25565)
        voicechat_address = data.get("voicechat_address")
        
        if not all([user_id, codespace_name, tunnel_host]):
            return jsonify({"error": "Faltan campos requeridos"}), 400

        print(f"📥 Webhook: {tunnel_type} para usuario {user_id}")
        print(f"   Tunnel: {tunnel_host}:{tunnel_port}")

        db = get_db()
        sesion = db.get_sesion(user_id)
        
        if sesion:
            sesion["tunnel_url"] = tunnel_host
            sesion["tunnel_port"] = tunnel_port
            sesion["tunnel_type"] = tunnel_type
            sesion["voicechat_address"] = voicechat_address
            sesion["tunnel_actualizado"] = datetime.now().isoformat()
            sesion["codespace"] = codespace_name
            
            db.save_sesion(user_id, sesion)
            
            async def send_notification():
                try:
                    import discord
                    user = await bot.fetch_user(int(user_id))
                    
                    description = (
                        f"**Codespace:** `{codespace_name}`\n"
                        f"**IP Minecraft:** `{tunnel_host}:{tunnel_port}`\n"
                    )
                    
                    if voicechat_address:
                        description += f"**IP VoiceChat:** `{voicechat_address}`\n"
                    
                    description += "\n✅ Tunnel guardado automáticamente."
                    
                    embed = discord.Embed(
                        title=f"🟢 Tunnel Detectado ({tunnel_type.upper()})",
                        description=description,
                        color=discord.Color.green()
                    )
                    
                    await user.send(embed=embed)
                    return True
                except:
                    return False

            loop = bot.loop
            future = asyncio.run_coroutine_threadsafe(send_notification(), loop)
            success = future.result(timeout=10)

            return jsonify({
                "status": "success",
                "message": "Tunnel guardado",
                "notification_sent": success
            }), 200
        else:
            return jsonify({
                "status": "warning",
                "message": "Usuario no tiene sesión"
            }), 200

    except Exception as e:
        print(f"❌ Error en webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    db_status = "disconnected"
    try:
        db = get_db()
        if db and db.conn:
            db.conn.cursor().execute("SELECT 1")
            db_status = "connected"
    except Exception as e:
        print(f"Health check DB error: {e}")
    
    return jsonify({
        "status": "ok",
        "database": db_status,
        "bot": "running" if get_bot() else "not_ready"
    }), 200

def run_flask():
    from config import PORT
    app.run(host='0.0.0.0', port=PORT, debug=False)