import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import requests
import asyncio
import os
from threading import Thread
from flask import Flask
import time

# ========== SERVIDOR HTTP PARA RENDER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot de Discord activo", 200

@app.route('/health')
def health():
    if bot.is_ready():
        return {"status": "online", "bot": str(bot.user), "latency": f"{bot.latency*1000:.2f}ms"}, 200
    else:
        return {"status": "starting"}, 503

def run_flask():
    """Ejecutar Flask en thread separado"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ========== SELF-PING PARA EVITAR SLEEP ==========
def self_ping():
    """Hacer ping a sí mismo para evitar que Render duerma el servicio"""
    # Esperar 2 minutos antes de empezar
    time.sleep(120)
    
    # Obtener URL del servicio desde variable de entorno
    render_url = os.getenv('RENDER_EXTERNAL_URL')
    
    if not render_url:
        print("⚠️ RENDER_EXTERNAL_URL no configurada")
        print("⚠️ Self-ping desactivado - el bot puede dormirse")
        print("⚠️ Configura la variable en Render o usa UptimeRobot")
        return
    
    health_url = f"{render_url}/health"
    print(f"✅ Self-ping activado → {health_url}")
    
    while True:
        try:
            # Hacer ping cada 10 minutos (600 segundos)
            # 10 min < 15 min (límite de Render)
            time.sleep(600)
            
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"✅ Self-ping OK [{timestamp}]")
            else:
                print(f"⚠️ Self-ping status: {response.status_code}")
        except Exception as e:
            print(f"❌ Self-ping error: {e}")
            # Continuar intentando aunque falle
            time.sleep(60)

# ========== CONFIGURACIÓN DEL BOT ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Almacenamiento en memoria (temporal)
sesiones = {}  # {user_id: {"token": ..., "codespace": ..., "expira": ...}}

# Almacenamiento persistente (archivo)
vinculaciones = {}  # {user_id: {"codespace": ..., "permisos": [], "logs": ...}}

# ========== FUNCIONES DE PERSISTENCIA ==========

def cargar_vinculaciones():
    """Cargar vinculaciones desde archivo"""
    try:
        with open('vinculaciones.json', 'r') as f:
            return json.load(f)
    except:
        return {}

def guardar_vinculaciones():
    """Guardar vinculaciones en archivo"""
    with open('vinculaciones.json', 'w') as f:
        json.dump(vinculaciones, f, indent=2)

# ========== FUNCIONES DE GITHUB API ==========

def encender_codespace(github_token, codespace_name):
    """Encender un Codespace usando GitHub API"""
    headers = {
        'Authorization': f'Bearer {github_token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    # Obtener información del usuario
    try:
        user_response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
        if user_response.status_code != 200:
            return False, "Token inválido"
        
        username = user_response.json()['login']
        
        # Iniciar el Codespace
        url = f'https://api.github.com/user/codespaces/{codespace_name}/start'
        response = requests.post(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return True, "Codespace iniciado correctamente"
        elif response.status_code == 404:
            return False, "Codespace no encontrado"
        elif response.status_code == 401:
            return False, "Token inválido o expirado"
        else:
            return False, f"Error: {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout al conectar con GitHub"
    except Exception as e:
        return False, f"Error: {str(e)}"

def apagar_codespace(github_token, codespace_name):
    """Apagar un Codespace"""
    headers = {
        'Authorization': f'Bearer {github_token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    try:
        url = f'https://api.github.com/user/codespaces/{codespace_name}/stop'
        response = requests.post(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return True, "Codespace apagado correctamente"
        else:
            return False, f"Error al apagar: {response.status_code}"
    except Exception as e:
        return False, f"Error: {str(e)}"

def estado_codespace(github_token, codespace_name):
    """Obtener estado de un Codespace"""
    headers = {
        'Authorization': f'Bearer {github_token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }
    
    try:
        url = f'https://api.github.com/user/codespaces/{codespace_name}'
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            estado = data.get('state', 'Unknown')
            return True, estado
        else:
            return False, "No se pudo obtener el estado"
    except Exception as e:
        return False, f"Error: {str(e)}"

# ========== FUNCIONES DE LOGS ==========

async def enviar_log(propietario_id, mensaje):
    """Enviar log al destino configurado (webhook o canal)"""
    if propietario_id not in vinculaciones:
        return
    
    config_log = vinculaciones[propietario_id].get("logs", "ninguno")
    
    if config_log == "ninguno" or not config_log:
        return
    
    # Formatear mensaje para Discord
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mensaje_formateado = f"[{timestamp}] {mensaje}"
    
    if config_log.startswith("webhook:"):
        # Enviar via webhook
        webhook_url = config_log.split(":", 1)[1]
        try:
            requests.post(webhook_url, json={
                "content": f"``````"
            }, timeout=5)
        except Exception as e:
            print(f"Error enviando webhook: {e}")
    
    elif config_log.startswith("canal:"):
        # Enviar via bot a canal específico
        canal_id = int(config_log.split(":")[1])
        try:
            canal = bot.get_channel(canal_id)
            if canal:
                # Dividir mensajes largos
                if len(mensaje_formateado) > 1900:
                    await canal.send(f"``````")
                else:
                    await canal.send(f"``````")
        except Exception as e:
            print(f"Error enviando a canal: {e}")

# ========== COMANDOS DEL BOT ==========

@bot.event
async def on_ready():
    """Evento cuando el bot se conecta"""
    global vinculaciones
    vinculaciones = cargar_vinculaciones()
    verificar_expiraciones.start()
    print(f'✅ Bot conectado como {bot.user}')
    print(f'ID: {bot.user.id}')
    print(f'Usuarios vinculados: {len(vinculaciones)}')

@bot.command()
async def vincular(ctx, codespace_name: str, log_config: str = "ninguno"):
    """
    Vincular tu Codespace
    Ejemplos:
      !vincular mi-codespace
      !vincular mi-codespace webhook:https://discord.com/api/webhooks/...
      !vincular mi-codespace canal:123456789
    """
    usuario_id = str(ctx.author.id)
    
    # Crear vinculación
    vinculaciones[usuario_id] = {
        "codespace": codespace_name,
        "permisos": [],
        "logs": log_config
    }
    guardar_vinculaciones()
    
    # Mensaje según configuración de logs
    if log_config.startswith("webhook:"):
        log_msg = "✅ Logs configurados via webhook"
    elif log_config.startswith("canal:"):
        canal_id = log_config.split(":")[1]
        log_msg = f"✅ Logs se enviarán a <#{canal_id}>"
    else:
        log_msg = "ℹ️ Logs desactivados (usa `!configurar_logs` para activar)"
    
    await ctx.send(
        f"✅ **Codespace vinculado:** `{codespace_name}`\n{log_msg}\n\n"
        f"Te enviaré un DM para configurar el token..."
    )
    
    # Pedir token por DM
    try:
        dm = await ctx.author.create_dm()
        await dm.send(
            f"🔐 **Configuración de {codespace_name}**\n\n"
            f"Envíame tu GitHub Personal Access Token (PAT)\n"
            f"Se guardará temporalmente por 2 horas.\n\n"
            f"**Cómo obtener el token:**\n"
            f"1. Ve a https://github.com/settings/tokens\n"
            f"2. Generate new token (classic)\n"
            f"3. Selecciona scope: `codespace`\n"
            f"4. Copia y envía el token aquí"
        )
        
        def check(m):
            return m.author.id == ctx.author.id and isinstance(m.channel, discord.DMChannel)
        
        msg = await bot.wait_for('message', check=check, timeout=300)
        github_token = msg.content.strip()
        
        # Validar token
        headers = {'Authorization': f'Bearer {github_token}'}
        response = requests.get('https://api.github.com/user', headers=headers, timeout=5)
        
        if response.status_code != 200:
            await dm.send("❌ Token inválido. Usa `!vincular` nuevamente con un token válido")
            return
        
        # Guardar sesión temporal
        sesiones[usuario_id] = {
            "token": github_token,
            "codespace": codespace_name,
            "expira": datetime.now() + timedelta(hours=2)
        }
        
        await dm.send(
            "✅ **Token guardado correctamente**\n\n"
            "**Comandos disponibles:**\n"
            "`!start` - Iniciar Codespace\n"
            "`!stop` - Apagar Codespace\n"
            "`!status` - Ver estado\n"
            "`!permitir @usuario` - Dar acceso a otro usuario\n"
            "`!revocar @usuario` - Quitar acceso\n"
            "`!permisos` - Ver usuarios autorizados"
        )
        
    except asyncio.TimeoutError:
        await ctx.author.send("⏱️ Tiempo expirado. Usa `!vincular` nuevamente cuando estés listo")
    except discord.Forbidden:
        await ctx.send("❌ No puedo enviarte DM. Verifica tu configuración de privacidad")

@bot.command()
async def start(ctx):
    """Iniciar tu Codespace o uno autorizado"""
    usuario_id = ctx.author.id
    
    # Buscar Codespace que puede controlar
    propietario_id = None
    codespace_name = None
    
    # Verificar si es propietario
    if str(usuario_id) in vinculaciones:
        propietario_id = str(usuario_id)
        codespace_name = vinculaciones[propietario_id]["codespace"]
    else:
        # Buscar si tiene permisos
        for owner_id, data in vinculaciones.items():
            if usuario_id in data.get("permisos", []):
                propietario_id = owner_id
                codespace_name = data["codespace"]
                break
    
    if not propietario_id:
        await ctx.send("❌ No tienes permisos para controlar ningún Codespace\nUsa `!vincular` para configurar el tuyo")
        return
    
    # Verificar sesión del propietario
    sesion = sesiones.get(propietario_id)
    
    if not sesion or datetime.now() > sesion["expira"]:
        # Notificar al propietario
        propietario = await bot.fetch_user(int(propietario_id))
        await propietario.send(
            f"🔐 **Renovación de sesión requerida**\n\n"
            f"<@{ctx.author.id}> intentó iniciar tu Codespace `{codespace_name}`\n"
            f"Tu sesión expiró. Envíame tu GitHub Token para renovarla:"
        )
        
        await ctx.send(
            f"⏱️ La sesión del propietario expiró\n"
            f"Se le envió una notificación a <@{propietario_id}> para renovarla"
        )
        return
    
    # Iniciar Codespace
    await ctx.send(f"🔄 Iniciando Codespace `{codespace_name}`...")
    
    success, mensaje = encender_codespace(sesion["token"], codespace_name)
    
    if success:
        await ctx.send(f"✅ {mensaje}")
        await enviar_log(propietario_id, f"Codespace iniciado por {ctx.author.name} ({ctx.author.id})")
    else:
        await ctx.send(f"❌ {mensaje}")
        await enviar_log(propietario_id, f"Error al iniciar Codespace: {mensaje}")

@bot.command()
async def stop(ctx):
    """Apagar tu Codespace"""
    usuario_id = ctx.author.id
    
    # Buscar Codespace
    propietario_id = None
    codespace_name = None
    
    if str(usuario_id) in vinculaciones:
        propietario_id = str(usuario_id)
        codespace_name = vinculaciones[propietario_id]["codespace"]
    else:
        for owner_id, data in vinculaciones.items():
            if usuario_id in data.get("permisos", []):
                propietario_id = owner_id
                codespace_name = data["codespace"]
                break
    
    if not propietario_id:
        await ctx.send("❌ No tienes permisos")
        return
    
    sesion = sesiones.get(propietario_id)
    
    if not sesion or datetime.now() > sesion["expira"]:
        await ctx.send("⏱️ Sesión expirada. Usa `!start` para renovarla")
        return
    
    await ctx.send(f"🔄 Apagando Codespace `{codespace_name}`...")
    
    success, mensaje = apagar_codespace(sesion["token"], codespace_name)
    
    if success:
        await ctx.send(f"✅ {mensaje}")
        await enviar_log(propietario_id, f"Codespace apagado por {ctx.author.name}")
    else:
        await ctx.send(f"❌ {mensaje}")

@bot.command()
async def status(ctx):
    """Ver estado de tu Codespace y sesión"""
    usuario_id = ctx.author.id
    
    # Buscar Codespace
    propietario_id = None
    codespace_name = None
    
    if str(usuario_id) in vinculaciones:
        propietario_id = str(usuario_id)
        codespace_name = vinculaciones[propietario_id]["codespace"]
        es_propietario = True
    else:
        for owner_id, data in vinculaciones.items():
            if usuario_id in data.get("permisos", []):
                propietario_id = owner_id
                codespace_name = data["codespace"]
                es_propietario = False
                break
    
    if not propietario_id:
        await ctx.send("❌ No tienes Codespace vinculado")
        return
    
    sesion = sesiones.get(propietario_id)
    
    # Estado de sesión
    if sesion and datetime.now() < sesion["expira"]:
        tiempo_restante = sesion["expira"] - datetime.now()
        minutos = int(tiempo_restante.total_seconds() / 60)
        estado_sesion = f"🟢 Activa ({minutos} min restantes)"
        
        # Consultar estado del Codespace
        success, estado = estado_codespace(sesion["token"], codespace_name)
        if success:
            estado_codespace_str = f"🟢 {estado}" if estado == "Available" else f"🟡 {estado}"
        else:
            estado_codespace_str = "❓ No disponible"
    else:
        estado_sesion = "🔴 Expirada"
        estado_codespace_str = "❓ Requiere sesión activa"
    
    rol = "👑 Propietario" if es_propietario else "👥 Usuario autorizado"
    
    await ctx.send(
        f"**Estado de Codespace**\n\n"
        f"**Nombre:** `{codespace_name}`\n"
        f"**Tu rol:** {rol}\n"
        f"**Sesión:** {estado_sesion}\n"
        f"**Codespace:** {estado_codespace_str}\n"
        f"**Propietario:** <@{propietario_id}>"
    )

@bot.command()
async def permitir(ctx, miembro: discord.Member):
    """Dar permiso a otro usuario para controlar tu Codespace"""
    propietario_id = str(ctx.author.id)
    
    if propietario_id not in vinculaciones:
        await ctx.send("❌ No tienes un Codespace vinculado")
        return
    
    nuevo_id = miembro.id
    
    if nuevo_id == ctx.author.id:
        await ctx.send("❌ No puedes agregarte a ti mismo")
        return
    
    permisos = vinculaciones[propietario_id].get("permisos", [])
    
    if nuevo_id not in permisos:
        vinculaciones[propietario_id]["permisos"].append(nuevo_id)
        guardar_vinculaciones()
        
        codespace = vinculaciones[propietario_id]["codespace"]
        await ctx.send(
            f"✅ {miembro.mention} ahora puede controlar tu Codespace `{codespace}`\n"
            f"Puede usar: `!start`, `!stop`, `!status`"
        )
        await enviar_log(propietario_id, f"Permiso otorgado a {miembro.name} ({miembro.id})")
    else:
        await ctx.send(f"{miembro.mention} ya tiene permisos")

@bot.command()
async def revocar(ctx, miembro: discord.Member):
    """Quitar permiso a un usuario"""
    propietario_id = str(ctx.author.id)
    
    if propietario_id not in vinculaciones:
        await ctx.send("❌ No tienes un Codespace vinculado")
        return
    
    usuario_id = miembro.id
    permisos = vinculaciones[propietario_id].get("permisos", [])
    
    if usuario_id in permisos:
        vinculaciones[propietario_id]["permisos"].remove(usuario_id)
        guardar_vinculaciones()
        await ctx.send(f"✅ Permisos revocados para {miembro.mention}")
        await enviar_log(propietario_id, f"Permiso revocado a {miembro.name} ({miembro.id})")
    else:
        await ctx.send(f"{miembro.mention} no tiene permisos")

@bot.command()
async def permisos(ctx):
    """Ver usuarios autorizados"""
    propietario_id = str(ctx.author.id)
    
    if propietario_id not in vinculaciones:
        await ctx.send("❌ No tienes un Codespace vinculado")
        return
    
    data = vinculaciones[propietario_id]
    codespace = data["codespace"]
    autorizados = data.get("permisos", [])
    
    if not autorizados:
        await ctx.send(f"**Codespace:** `{codespace}`\n\nSolo tú tienes acceso")
        return
    
    menciones = [f"• <@{uid}>" for uid in autorizados]
    await ctx.send(
        f"**Codespace:** `{codespace}`\n\n"
        f"**Usuarios autorizados:**\n" + "\n".join(menciones)
    )

@bot.command()
async def configurar_logs(ctx, tipo: str, destino: str = "-"):
    """
    Configurar destino de logs de tu Codespace
    Ejemplos:
      !configurar_logs webhook https://discord.com/api/webhooks/...
      !configurar_logs canal 123456789
      !configurar_logs ninguno
    """
    usuario_id = str(ctx.author.id)
    
    if usuario_id not in vinculaciones:
        await ctx.send("❌ No tienes un Codespace vinculado")
        return
    
    if tipo == "webhook":
        if not destino.startswith("https://discord.com/api/webhooks/"):
            await ctx.send("❌ URL de webhook inválida")
            return
        vinculaciones[usuario_id]["logs"] = f"webhook:{destino}"
        await ctx.send("✅ Logs configurados para webhook")
    
    elif tipo == "canal":
        try:
            canal_id = int(destino)
            canal = bot.get_channel(canal_id)
            if not canal:
                await ctx.send("❌ No puedo acceder a ese canal. Asegúrate de que el bot esté en el servidor")
                return
            vinculaciones[usuario_id]["logs"] = f"canal:{destino}"
            await ctx.send(f"✅ Logs se enviarán a <#{destino}>")
        except ValueError:
            await ctx.send("❌ ID de canal inválida")
            return
    
    elif tipo == "ninguno":
        vinculaciones[usuario_id]["logs"] = "ninguno"
        await ctx.send("✅ Logs desactivados")
    
    else:
        await ctx.send("❌ Tipo inválido. Usa: `webhook`, `canal` o `ninguno`")
        return
    
    guardar_vinculaciones()

@bot.command()
async def desvincular(ctx):
    """Eliminar tu Codespace y todos los datos asociados"""
    usuario_id = str(ctx.author.id)
    
    if usuario_id not in vinculaciones:
        await ctx.send("❌ No tienes un Codespace vinculado")
        return
    
    codespace = vinculaciones[usuario_id]["codespace"]
    
    # Confirmar
    await ctx.send(
        f"⚠️ ¿Estás seguro de desvincular `{codespace}`?\n"
        f"Esto eliminará todos los permisos y configuraciones.\n"
        f"Responde `confirmar` en 30 segundos para continuar"
    )
    
    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=30)
        if msg.content.lower() == "confirmar":
            del vinculaciones[usuario_id]
            if usuario_id in sesiones:
                del sesiones[usuario_id]
            guardar_vinculaciones()
            await ctx.send(f"✅ Codespace `{codespace}` desvinculado correctamente")
        else:
            await ctx.send("❌ Operación cancelada")
    except asyncio.TimeoutError:
        await ctx.send("⏱️ Tiempo expirado. Operación cancelada")

@bot.command()
async def ayuda(ctx):
    """Mostrar comandos disponibles"""
    embed = discord.Embed(
        title="🤖 Bot de Control de Codespaces",
        description="Controla tu GitHub Codespace desde Discord",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📋 Configuración Inicial",
        value=(
            "`!vincular <nombre>` - Vincular tu Codespace\n"
            "`!desvincular` - Eliminar vinculación\n"
            "`!configurar_logs <tipo> <destino>` - Configurar logs"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎮 Control",
        value=(
            "`!start` - Iniciar Codespace\n"
            "`!stop` - Apagar Codespace\n"
            "`!status` - Ver estado"
        ),
        inline=False
    )
    
    embed.add_field(
        name="👥 Permisos",
        value=(
            "`!permitir @usuario` - Dar acceso\n"
            "`!revocar @usuario` - Quitar acceso\n"
            "`!permisos` - Ver usuarios autorizados"
        ),
        inline=False
    )
    
    embed.set_footer(text="Desarrollado para gestión de Codespaces")
    
    await ctx.send(embed=embed)

# ========== TAREAS AUTOMÁTICAS ==========

@tasks.loop(minutes=5)
async def verificar_expiraciones():
    """Verificar y notificar sesiones próximas a expirar"""
    ahora = datetime.now()
    
    for user_id, sesion in list(sesiones.items()):
        tiempo_restante = sesion["expira"] - ahora
        
        # Avisar 10 minutos antes
        if timedelta(minutes=9) < tiempo_restante < timedelta(minutes=11):
            try:
                user = await bot.fetch_user(int(user_id))
                await user.send(
                    f"⚠️ **Tu sesión expirará en 10 minutos**\n\n"
                    f"Codespace: `{sesion['codespace']}`\n"
                    f"Usa `!start` para renovar automáticamente"
                )
            except:
                pass
        
        # Eliminar si ya expiró
        elif tiempo_restante < timedelta(0):
            try:
                user = await bot.fetch_user(int(user_id))
                await user.send(
                    f"🔴 **Tu sesión expiró**\n\n"
                    f"Codespace: `{sesion['codespace']}`\n"
                    f"Usa `!start` cuando necesites el servidor nuevamente"
                )
            except:
                pass
            
            del sesiones[user_id]
            print(f"Sesión expirada para usuario {user_id}")

# ========== INICIAR BOT ==========

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("❌ Error: No se encontró DISCORD_BOT_TOKEN")
        exit(1)
    
    # Iniciar servidor HTTP en background para Render
    print("🌐 Iniciando servidor HTTP para Render...")
    Thread(target=run_flask, daemon=True).start()
    
    # Iniciar self-ping para evitar que Render duerma el servicio
    print("⏰ Iniciando self-ping...")
    Thread(target=self_ping, daemon=True).start()
    
    # Dar tiempo al servidor HTTP
    time.sleep(2)
    
    # Iniciar bot
    print("🤖 Iniciando bot de Discord...")
    print(f"🔑 Token: {TOKEN[:20]}...{TOKEN[-5:]}")
    
    try:
        bot.run(TOKEN, log_handler=None)
    except discord.LoginFailure:
        print("\n" + "="*50)
        print("❌ ERROR: Token inválido")
        print("="*50)
        print("Soluciones:")
        print("1. Ve a https://discord.com/developers/applications")
        print("2. Bot → Reset Token")
        print("3. Copia el nuevo token")
        print("4. Actualiza DISCORD_BOT_TOKEN en Render")
        print("="*50)
        exit(1)
    except discord.PrivilegedIntentsRequired:
        print("\n" + "="*50)
        print("❌ ERROR: Faltan Privileged Intents")
        print("="*50)
        print("Soluciones:")
        print("1. Ve a https://discord.com/developers/applications")
        print("2. Selecciona tu bot → Bot")
        print("3. Activa todos los Privileged Gateway Intents:")
        print("   - Presence Intent")
        print("   - Server Members Intent")
        print("   - Message Content Intent")
        print("4. Guarda y reinicia el bot en Render")
        print("="*50)
        exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
