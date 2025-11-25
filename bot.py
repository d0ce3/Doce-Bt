import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import json
import subprocess
import os
from threading import Thread
from flask import Flask

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
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def self_ping():
    import time
    import requests
    time.sleep(120)
    render_url = os.getenv('RENDER_EXTERNAL_URL')
    if not render_url:
        return
    health_url = f"{render_url}/health"
    while True:
        try:
            time.sleep(600)
            requests.get(health_url, timeout=5)
            print(f"✅ Self-ping OK [{datetime.now().strftime('%H:%M:%S')}]")
        except:
            pass

# ========== BOT ==========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Almacenamiento
sesiones = {}
vinculaciones = {}

def cargar_vinculaciones():
    try:
        with open('vinculaciones.json', 'r') as f:
            return json.load(f)
    except:
        return {}

def guardar_vinculaciones():
    with open('vinculaciones.json', 'w') as f:
        json.dump(vinculaciones, f, indent=2)

# Funciones con GitHub CLI para controlar Codespace
def gh_codespace_start(codespace_name):
    result = subprocess.run(
        ['gh', 'codespace', 'start', '-c', codespace_name],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr

def gh_codespace_stop(codespace_name):
    result = subprocess.run(
        ['gh', 'codespace', 'stop', '-c', codespace_name],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stdout + result.stderr

def gh_codespace_list():
    result = subprocess.run(
        ['gh', 'codespace', 'list', '--json', 'name,state,owner'],
        capture_output=True,
        text=True
    )
    import json
    try:
        return json.loads(result.stdout)
    except:
        return []

def gh_codespace_status(codespace_name):
    codespaces = gh_codespace_list()
    for cs in codespaces:
        if cs['name'] == codespace_name:
            return cs.get('state', 'Unknown')
    return 'Not Found'

def puede_controlar(calling_user_id, owner_id):
    if str(calling_user_id) == str(owner_id):
        return True
    permisos = vinculaciones.get(str(owner_id), {}).get("permisos", [])
    return calling_user_id in permisos

@tree.command(name="vincular", description="Vincular tu Codespace")
@app_commands.describe(codespace="Nombre de tu Codespace (déjalo vacío para ver lista)")
async def vincular(interaction: discord.Interaction, codespace: str = None):
    usuario_id = str(interaction.user.id)
    if not codespace:
        await interaction.response.defer(ephemeral=True)
        codespaces = gh_codespace_list()
        if not codespaces:
            await interaction.followup.send("❌ No se encontraron Codespaces. Asegúrate de tener al menos uno activo.", ephemeral=True)
            return
        lista = "\n".join([f"`{cs['name']}` - Propietario: `{cs['owner']['login']}` Estado: {cs['state']}" for cs in codespaces])
        await interaction.followup.send(f"**Tus Codespaces:**\n{lista}\n\nUsa `/vincular codespace:<nombre>` para vincular.", ephemeral=True)
        return

    vinculaciones[usuario_id] = {
        "codespace": codespace,
        "permisos": []
    }
    guardar_vinculaciones()
    sesiones[usuario_id] = {
        "codespace": codespace,
        "expira": datetime.now() + timedelta(hours=5)
    }
    await interaction.response.send_message(f"✅ **Codespace vinculado:** `{codespace}`\nSesión válida por 5 horas.", ephemeral=True)

@tree.command(name="permitir", description="Dar permiso a un usuario para controlar tu Codespace")
@app_commands.describe(usuario="Usuario a autorizar")
async def permitir(interaction: discord.Interaction, usuario: discord.Member):
    owner_id = str(interaction.user.id)
    if owner_id not in vinculaciones:
        await interaction.response.send_message("❌ No tienes Codespace vinculado.", ephemeral=True)
        return
    if usuario.id == int(owner_id):
        await interaction.response.send_message("❌ No puedes darte permiso a ti mismo.", ephemeral=True)
        return
    permisos = vinculaciones[owner_id].setdefault("permisos", [])
    if usuario.id in permisos:
        await interaction.response.send_message(f"ℹ️ <@{usuario.id}> ya tiene acceso.", ephemeral=True)
        return
    permisos.append(usuario.id)
    guardar_vinculaciones()
    await interaction.response.send_message(f"✅ Permitido el acceso a <@{usuario.id}>", ephemeral=False)

@tree.command(name="revocar", description="Quitar permiso a un usuario")
@app_commands.describe(usuario="Usuario a revocar")
async def revocar(interaction: discord.Interaction, usuario: discord.Member):
    owner_id = str(interaction.user.id)
    if owner_id not in vinculaciones:
        await interaction.response.send_message("❌ No tienes Codespace vinculado.", ephemeral=True)
        return
    permisos = vinculaciones[owner_id].get("permisos", [])
    if usuario.id not in permisos:
        await interaction.response.send_message(f"ℹ️ <@{usuario.id}> no tiene acceso.", ephemeral=True)
        return
    permisos.remove(usuario.id)
    guardar_vinculaciones()
    await interaction.response.send_message(f"✅ Revocado el acceso a <@{usuario.id}>", ephemeral=False)

@tree.command(name="start", description="Iniciar Codespace o autorizado")
async def start(interaction: discord.Interaction):
    calling_id = interaction.user.id
    owner_id = None
    codespace = None
    if str(calling_id) in vinculaciones:
        owner_id = str(calling_id)
        codespace = vinculaciones[owner_id]["codespace"]
    else:
        for o_id, data in vinculaciones.items():
            if calling_id in data.get("permisos", []):
                owner_id = o_id
                codespace = data["codespace"]
                break
    if not owner_id:
        await interaction.response.send_message("❌ No tienes acceso para controlar ningún Codespace.\nPide al propietario que te otorgue permiso.", ephemeral=True)
        return
    await interaction.response.defer()
    success, mensaje = gh_codespace_start(codespace)
    if success:
        await interaction.followup.send(f"✅ Codespace `{codespace}` iniciado correctamente por <@{calling_id}>.")
    else:
        await interaction.followup.send(f"❌ Error: {mensaje}")

@tree.command(name="stop", description="Detener Codespace o autorizado")
async def stop(interaction: discord.Interaction):
    calling_id = interaction.user.id
    owner_id = None
    codespace = None
    if str(calling_id) in vinculaciones:
        owner_id = str(calling_id)
        codespace = vinculaciones[owner_id]["codespace"]
    else:
        for o_id, data in vinculaciones.items():
            if calling_id in data.get("permisos", []):
                owner_id = o_id
                codespace = data["codespace"]
                break
    if not owner_id:
        await interaction.response.send_message("❌ No tienes acceso para controlar ningún Codespace.\nPide al propietario que te otorgue permiso.", ephemeral=True)
        return
    await interaction.response.defer()
    success, mensaje = gh_codespace_stop(codespace)
    if success:
        await interaction.followup.send(f"✅ Codespace `{codespace}` detenido correctamente por <@{calling_id}>.")
    else:
        await interaction.followup.send(f"❌ Error: {mensaje}")

@tree.command(name="status", description="Ver estado de Codespace o autorizado")
async def status(interaction: discord.Interaction):
    calling_id = interaction.user.id
    owner_id = None
    codespace = None
    if str(calling_id) in vinculaciones:
        owner_id = str(calling_id)
        codespace = vinculaciones[owner_id]["codespace"]
    else:
        for o_id, data in vinculaciones.items():
            if calling_id in data.get("permisos", []):
                owner_id = o_id
                codespace = data["codespace"]
                break
    if not owner_id:
        await interaction.response.send_message("❌ No tienes acceso para ver ningún Codespace.\nPide al propietario que te otorgue permiso.", ephemeral=True)
        return
    estado = gh_codespace_status(codespace)
    sesion = sesiones.get(owner_id)
    if sesion and datetime.now() < sesion["expira"]:
        tiempo_restante = sesion["expira"] - datetime.now()
        horas = int(tiempo_restante.total_seconds() / 3600)
        minutos = int((tiempo_restante.total_seconds() % 3600) / 60)
        estado_sesion = f"🟢 Activa ({horas}h {minutos}m)"
    else:
        estado_sesion = "🔴 Expirada"
    emoji_estado = {
        "Available": "🟢",
        "Starting": "🟡",
        "Shutdown": "🔴",
        "Not Found": "❓"
    }.get(estado, "⚪")
    embed = discord.Embed(title="Estado del Codespace", color=discord.Color.blue())
    embed.add_field(name="Nombre", value=f"`{codespace}`", inline=False)
    embed.add_field(name="Estado", value=f"{emoji_estado} {estado}", inline=True)
    embed.add_field(name="Sesión", value=estado_sesion, inline=True)
    await interaction.response.send_message(embed=embed)

@tree.command(name="info", description="Ver tu configuración")
async def info(interaction: discord.Interaction):
    usuario_id = str(interaction.user.id)
    if usuario_id not in vinculaciones:
        await interaction.response.send_message("❌ No tienes Codespace vinculado", ephemeral=True)
        return
    data = vinculaciones[usuario_id]
    codespace = data["codespace"]
    embed = discord.Embed(title="📋 Tu Configuración - doce|tools", color=discord.Color.blue())
    embed.add_field(name="Codespace", value=f"`{codespace}`", inline=False)
    embed.add_field(name="Permisos Compartidos", value=f"{len(data.get('permisos', []))} usuarios", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    global vinculaciones
    vinculaciones = cargar_vinculaciones()
    await tree.sync()
    print(f'✅ Bot conectado como {bot.user}')
    print(f'✅ {len(tree.get_commands())} slash commands sincronizados')

if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if not TOKEN:
        print("❌ Error: No se encontró DISCORD_BOT_TOKEN")
        exit(1)
    Thread(target=run_flask, daemon=True).start()
    Thread(target=self_ping, daemon=True).start()
    import time
    time.sleep(2)
    print("🤖 Iniciando bot con slash commands...")
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Error: {e}")
