import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import json
import subprocess
import os
from threading import Thread
from flask import Flask

# ========== CONFIGURACIÓN ==========
# Reemplaza con el ID de tu servidor de Discord para pruebas
# Para obtenerlo: Click derecho en tu servidor → Copiar ID (necesitas modo desarrollador activado)
MY_GUILD_ID = discord.Object(id=1424589804858904618)  # ⚠️ CAMBIAR ESTE ID

# ========== SERVIDOR HTTP PARA RENDER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ doce|tools bot activo", 200

@app.route('/health')
def health():
    if bot.is_ready():
        return {"status": "online", "bot": str(bot.user)}, 200
    else:
        return {"status": "starting"}, 503

def run_flask():
    """Ejecuta el servidor Flask en un thread separado"""
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Servidor Flask iniciando en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def self_ping():
    """Hace ping al propio servidor para mantenerlo despierto en Render"""
    import time
    import requests
    
    # Espera 2 minutos antes de empezar
    time.sleep(120)
    
    render_url = os.getenv('RENDER_EXTERNAL_URL')
    if not render_url:
        print("⚠️ RENDER_EXTERNAL_URL no configurada, self-ping desactivado")
        return
    
    health_url = f"{render_url}/health"
    print(f"🔔 Self-ping activado: {health_url}")
    
    while True:
        try:
            time.sleep(600)  # Cada 10 minutos
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                print(f"✅ Self-ping OK [{datetime.now().strftime('%H:%M:%S')}]")
            else:
                print(f"⚠️ Self-ping respondió con código {response.status_code}")
        except Exception as e:
            print(f"❌ Self-ping falló: {e}")

# ========== BOT DISCORD ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Almacenamiento de sesiones y vinculaciones
sesiones = {}
vinculaciones = {}

def cargar_vinculaciones():
    """Carga las vinculaciones desde archivo JSON"""
    try:
        with open('vinculaciones.json', 'r') as f:
            data = json.load(f)
            print(f"📂 Vinculaciones cargadas: {len(data)} usuarios")
            return data
    except FileNotFoundError:
        print("📂 No se encontró vinculaciones.json, creando nuevo archivo")
        return {}
    except json.JSONDecodeError:
        print("⚠️ Error al leer vinculaciones.json, usando datos vacíos")
        return {}

def guardar_vinculaciones():
    """Guarda las vinculaciones en archivo JSON"""
    try:
        with open('vinculaciones.json', 'w') as f:
            json.dump(vinculaciones, f, indent=2)
        print(f"💾 Vinculaciones guardadas: {len(vinculaciones)} usuarios")
    except Exception as e:
        print(f"❌ Error al guardar vinculaciones: {e}")

# ========== FUNCIONES GITHUB CLI ==========
def gh_codespace_start(codespace_name):
    """Inicia un Codespace usando GitHub CLI"""
    try:
        result = subprocess.run(
            ['gh', 'codespace', 'start', '-c', codespace_name],
            capture_output=True,
            text=True,
            timeout=60
        )
        success = result.returncode == 0
        mensaje = result.stdout + result.stderr
        print(f"{'✅' if success else '❌'} gh codespace start: {codespace_name}")
        return success, mensaje
    except subprocess.TimeoutExpired:
        return False, "Timeout: El comando tardó demasiado"
    except Exception as e:
        return False, f"Error: {str(e)}"

def gh_codespace_stop(codespace_name):
    """Detiene un Codespace usando GitHub CLI"""
    try:
        result = subprocess.run(
            ['gh', 'codespace', 'stop', '-c', codespace_name],
            capture_output=True,
            text=True,
            timeout=60
        )
        success = result.returncode == 0
        mensaje = result.stdout + result.stderr
        print(f"{'✅' if success else '❌'} gh codespace stop: {codespace_name}")
        return success, mensaje
    except subprocess.TimeoutExpired:
        return False, "Timeout: El comando tardó demasiado"
    except Exception as e:
        return False, f"Error: {str(e)}"

def gh_codespace_list():
    """Lista todos los Codespaces del usuario"""
    try:
        result = subprocess.run(
            ['gh', 'codespace', 'list', '--json', 'name,state,owner'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"⚠️ Error al listar codespaces: {result.stderr}")
            return []
    except Exception as e:
        print(f"❌ Error en gh_codespace_list: {e}")
        return []

def gh_codespace_status(codespace_name):
    """Obtiene el estado de un Codespace específico"""
    codespaces = gh_codespace_list()
    for cs in codespaces:
        if cs['name'] == codespace_name:
            return cs.get('state', 'Unknown')
    return 'Not Found'

def puede_controlar(calling_user_id, owner_id):
    """Verifica si un usuario tiene permiso para controlar un Codespace"""
    if str(calling_user_id) == str(owner_id):
        return True
    permisos = vinculaciones.get(str(owner_id), {}).get("permisos", [])
    return calling_user_id in permisos

# ========== COMANDOS SLASH ==========

@tree.command(name="vincular", description="Vincular tu Codespace", guild=MY_GUILD_ID)
@app_commands.describe(codespace="Nombre de tu Codespace (déjalo vacío para ver lista)")
async def vincular(interaction: discord.Interaction, codespace: str = None):
    """Vincula un Codespace a tu cuenta de Discord"""
    usuario_id = str(interaction.user.id)
    
    if not codespace:
        await interaction.response.defer(ephemeral=True)
        codespaces = gh_codespace_list()
        
        if not codespaces:
            await interaction.followup.send(
                "❌ No se encontraron Codespaces.\n"
                "Asegúrate de tener al menos uno activo y que `gh` esté autenticado.",
                ephemeral=True
            )
            return
        
        lista = "\n".join([
            f"• `{cs['name']}` - Propietario: `{cs['owner']['login']}` - Estado: **{cs['state']}**"
            for cs in codespaces
        ])
        
        await interaction.followup.send(
            f"**📋 Tus Codespaces disponibles:**\n{lista}\n\n"
            f"Usa `/vincular codespace:<nombre>` para vincular uno.",
            ephemeral=True
        )
        return
    
    # Guardar vinculación
    vinculaciones[usuario_id] = {
        "codespace": codespace,
        "permisos": []
    }
    guardar_vinculaciones()
    
    # Crear sesión temporal
    sesiones[usuario_id] = {
        "codespace": codespace,
        "expira": datetime.now() + timedelta(hours=5)
    }
    
    await interaction.response.send_message(
        f"✅ **Codespace vinculado exitosamente**\n"
        f"📦 Nombre: `{codespace}`\n"
        f"⏰ Sesión válida por 5 horas\n\n"
        f"Usa `/start`, `/stop` y `/status` para controlarlo.",
        ephemeral=True
    )

@tree.command(name="permitir", description="Dar permiso a un usuario para controlar tu Codespace", guild=MY_GUILD_ID)
@app_commands.describe(usuario="Usuario a autorizar")
async def permitir(interaction: discord.Interaction, usuario: discord.Member):
    """Otorga permisos de control a otro usuario"""
    owner_id = str(interaction.user.id)
    
    if owner_id not in vinculaciones:
        await interaction.response.send_message(
            "❌ No tienes ningún Codespace vinculado.\n"
            "Usa `/vincular` primero.",
            ephemeral=True
        )
        return
    
    if usuario.id == int(owner_id):
        await interaction.response.send_message(
            "❌ No puedes darte permiso a ti mismo.",
            ephemeral=True
        )
        return
    
    permisos = vinculaciones[owner_id].setdefault("permisos", [])
    
    if usuario.id in permisos:
        await interaction.response.send_message(
            f"ℹ️ <@{usuario.id}> ya tiene acceso a tu Codespace.",
            ephemeral=True
        )
        return
    
    permisos.append(usuario.id)
    guardar_vinculaciones()
    
    await interaction.response.send_message(
        f"✅ **Permiso otorgado**\n"
        f"<@{usuario.id}> ahora puede controlar tu Codespace `{vinculaciones[owner_id]['codespace']}`",
        ephemeral=False
    )

@tree.command(name="revocar", description="Quitar permiso a un usuario", guild=MY_GUILD_ID)
@app_commands.describe(usuario="Usuario a revocar")
async def revocar(interaction: discord.Interaction, usuario: discord.Member):
    """Revoca permisos de control a un usuario"""
    owner_id = str(interaction.user.id)
    
    if owner_id not in vinculaciones:
        await interaction.response.send_message(
            "❌ No tienes ningún Codespace vinculado.",
            ephemeral=True
        )
        return
    
    permisos = vinculaciones[owner_id].get("permisos", [])
    
    if usuario.id not in permisos:
        await interaction.response.send_message(
            f"ℹ️ <@{usuario.id}> no tiene acceso a tu Codespace.",
            ephemeral=True
        )
        return
    
    permisos.remove(usuario.id)
    guardar_vinculaciones()
    
    await interaction.response.send_message(
        f"✅ **Permiso revocado**\n"
        f"<@{usuario.id}> ya no puede controlar tu Codespace.",
        ephemeral=False
    )

@tree.command(name="start", description="Iniciar Codespace (tuyo o autorizado)", guild=MY_GUILD_ID)
async def start(interaction: discord.Interaction):
    """Inicia el Codespace vinculado o uno autorizado"""
    calling_id = interaction.user.id
    owner_id = None
    codespace = None
    
    # Verificar si tiene su propio Codespace
    if str(calling_id) in vinculaciones:
        owner_id = str(calling_id)
        codespace = vinculaciones[owner_id]["codespace"]
    else:
        # Buscar si tiene permiso en algún Codespace
        for o_id, data in vinculaciones.items():
            if calling_id in data.get("permisos", []):
                owner_id = o_id
                codespace = data["codespace"]
                break
    
    if not owner_id:
        await interaction.response.send_message(
            "❌ **No tienes acceso**\n"
            "No tienes ningún Codespace vinculado ni permisos en otros.\n"
            "Pide al propietario que use `/permitir @tu_usuario`",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    success, mensaje = gh_codespace_start(codespace)
    
    if success:
        await interaction.followup.send(
            f"✅ **Codespace iniciado**\n"
            f"📦 `{codespace}`\n"
            f"👤 Accionado por <@{calling_id}>\n"
            f"⏳ Espera 30-60 segundos antes de usarlo."
        )
    else:
        await interaction.followup.send(
            f"❌ **Error al iniciar**\n"
            f"```{mensaje}```"
        )

@tree.command(name="stop", description="Detener Codespace (tuyo o autorizado)", guild=MY_GUILD_ID)
async def stop(interaction: discord.Interaction):
    """Detiene el Codespace vinculado o uno autorizado"""
    calling_id = interaction.user.id
    owner_id = None
    codespace = None
    
    # Verificar si tiene su propio Codespace
    if str(calling_id) in vinculaciones:
        owner_id = str(calling_id)
        codespace = vinculaciones[owner_id]["codespace"]
    else:
        # Buscar si tiene permiso en algún Codespace
        for o_id, data in vinculaciones.items():
            if calling_id in data.get("permisos", []):
                owner_id = o_id
                codespace = data["codespace"]
                break
    
    if not owner_id:
        await interaction.response.send_message(
            "❌ **No tienes acceso**\n"
            "No tienes ningún Codespace vinculado ni permisos en otros.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    success, mensaje = gh_codespace_stop(codespace)
    
    if success:
        await interaction.followup.send(
            f"✅ **Codespace detenido**\n"
            f"📦 `{codespace}`\n"
            f"👤 Accionado por <@{calling_id}>"
        )
    else:
        await interaction.followup.send(
            f"❌ **Error al detener**\n"
            f"```{mensaje}```"
        )

@tree.command(name="status", description="Ver estado de Codespace (tuyo o autorizado)", guild=MY_GUILD_ID)
async def status(interaction: discord.Interaction):
    """Muestra el estado del Codespace"""
    calling_id = interaction.user.id
    owner_id = None
    codespace = None
    
    # Verificar si tiene su propio Codespace
    if str(calling_id) in vinculaciones:
        owner_id = str(calling_id)
        codespace = vinculaciones[owner_id]["codespace"]
    else:
        # Buscar si tiene permiso en algún Codespace
        for o_id, data in vinculaciones.items():
            if calling_id in data.get("permisos", []):
                owner_id = o_id
                codespace = data["codespace"]
                break
    
    if not owner_id:
        await interaction.response.send_message(
            "❌ **No tienes acceso**\n"
            "No tienes ningún Codespace vinculado ni permisos en otros.",
            ephemeral=True
        )
        return
    
    # Obtener estado del Codespace
    estado = gh_codespace_status(codespace)
    
    # Verificar estado de sesión
    sesion = sesiones.get(owner_id)
    if sesion and datetime.now() < sesion["expira"]:
        tiempo_restante = sesion["expira"] - datetime.now()
        horas = int(tiempo_restante.total_seconds() / 3600)
        minutos = int((tiempo_restante.total_seconds() % 3600) / 60)
        estado_sesion = f"🟢 Activa ({horas}h {minutos}m restantes)"
    else:
        estado_sesion = "🔴 Expirada"
    
    # Emoji según estado
    emoji_estado = {
        "Available": "🟢",
        "Starting": "🟡",
        "Shutdown": "🔴",
        "Not Found": "❓"
    }.get(estado, "⚪")
    
    embed = discord.Embed(
        title="📊 Estado del Codespace",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="📦 Nombre", value=f"`{codespace}`", inline=False)
    embed.add_field(name="🔌 Estado", value=f"{emoji_estado} **{estado}**", inline=True)
    embed.add_field(name="⏰ Sesión", value=estado_sesion, inline=True)
    embed.set_footer(text=f"Consultado por {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="info", description="Ver tu configuración", guild=MY_GUILD_ID)
async def info(interaction: discord.Interaction):
    """Muestra la configuración del usuario"""
    usuario_id = str(interaction.user.id)
    
    if usuario_id not in vinculaciones:
        await interaction.response.send_message(
            "❌ No tienes ningún Codespace vinculado.\n"
            "Usa `/vincular` para comenzar.",
            ephemeral=True
        )
        return
    
    data = vinculaciones[usuario_id]
    codespace = data["codespace"]
    permisos = data.get("permisos", [])
    
    embed = discord.Embed(
        title="📋 Tu Configuración - doce|tools",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="📦 Codespace Vinculado", value=f"`{codespace}`", inline=False)
    embed.add_field(name="👥 Usuarios Autorizados", value=f"**{len(permisos)}** usuarios", inline=True)
    
    if permisos:
        usuarios_str = "\n".join([f"• <@{user_id}>" for user_id in permisos[:5]])
        if len(permisos) > 5:
            usuarios_str += f"\n... y {len(permisos) - 5} más"
        embed.add_field(name="Lista de Autorizados", value=usuarios_str, inline=False)
    
    embed.set_footer(text=f"Usuario: {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== EVENTOS DEL BOT ==========

@bot.event
async def on_ready():
    """Se ejecuta cuando el bot está listo"""
    global vinculaciones
    vinculaciones = cargar_vinculaciones()
    
    try:
        # Sincronizar comandos en el servidor de prueba
        await tree.sync(guild=MY_GUILD_ID)
        print(f'✅ Comandos sincronizados en servidor {MY_GUILD_ID.id}')
    except Exception as e:
        print(f'❌ Error al sincronizar comandos: {e}')
    
    print(f'✅ Bot conectado como {bot.user}')
    print(f'✅ {len(tree.get_commands())} slash commands registrados')
    print(f'📊 {len(vinculaciones)} vinculaciones cargadas')

# ========== INICIO DEL BOT ==========

if __name__ == "__main__":
    # Verificar token
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        print("❌ Error: No se encontró DISCORD_BOT_TOKEN en variables de entorno")
        exit(1)
    
    print("🚀 Iniciando doce|tools bot...")
    
    # Iniciar servidor Flask en thread separado
    Thread(target=run_flask, daemon=True).start()
    
    # Iniciar self-ping en thread separado (para Render)
    Thread(target=self_ping, daemon=True).start()
    
    # Esperar 2 segundos para que Flask inicie
    import time
    time.sleep(2)
    
    print("🤖 Conectando bot de Discord...")
    
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\n⏹️ Bot detenido por el usuario")
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
