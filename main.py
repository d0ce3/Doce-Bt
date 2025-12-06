import discord
from discord.ext import commands
import asyncio
from threading import Thread
import traceback
import os
import json
from config import DISCORD_BOT_TOKEN, GUILD_ID
from web.server import run_flask, set_bot
from web.auto_ping import self_ping
from utils.database import get_db
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

def cleanup_legacy_json_files():
    json_files = [
        'data/sesiones.json',
        'data/vinculaciones.json',
        'data/permisos.json'
    ]
    
    for filepath in json_files:
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️  {filepath} corrupto, eliminando...")
                try:
                    os.remove(filepath)
                    print(f"✅ {filepath} eliminado")
                except Exception as e:
                    print(f"❌ Error eliminando {filepath}: {e}")
            except Exception as e:
                print(f"⚠️  Error leyendo {filepath}: {e}")

def limpiar_tokens_expirados():
    try:
        db = get_db()
        sesiones = db.get_all_sesiones()
        ahora = datetime.now()
        
        for uid, sesion in sesiones.items():
            exp_token = sesion.get("expira_token")
            if not exp_token:
                continue
            
            try:
                if datetime.fromisoformat(exp_token) < ahora:
                    sesion["token"] = None
                    sesion["expira_token"] = None
                    db.save_sesion(uid, sesion)
                    print(f"🗑️ Token eliminado para usuario {uid}")
            except Exception as e:
                print(f"⚠️ Error parseando fecha para {uid}: {e}")
    except Exception as e:
        print(f"❌ Error limpiando tokens: {e}")

async def load_cogs():
    cogs = [
        "cogs.setup_cog",
        "cogs.permisos",
        "cogs.codespace_control",
        "cogs.codespace_minecraft",
        "cogs.info",
        "cogs.addon_integration",
    ]

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ Cog cargado: {cog}")
        except Exception as e:
            print(f"❌ Error cargando {cog}: {e}")
            traceback.print_exc()

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    print(f"📊 Conectado a {len(bot.guilds)} servidores")
    
    try:
        db = get_db()
        print("✅ Conectado a Supabase")
    except Exception as e:
        print(f"❌ Error conectando a Supabase: {e}")
        traceback.print_exc()
    
    try:
        if GUILD_ID:
            guild = discord.utils.get(bot.guilds, id=GUILD_ID)
            
            if guild:
                print(f"🎯 Sincronizando en servidor: {guild.name}")
                bot.tree.clear_commands(guild=guild)
                bot.tree.copy_global_to(guild=guild)
                cmds_guild = await bot.tree.sync(guild=guild)
                print(f"✅ {len(cmds_guild)} comandos en {guild.name}")
        
        print("🌍 Sincronizando comandos globalmente...")
        cmds_global = await bot.tree.sync()
        print(f"✅ {len(cmds_global)} comandos globales")
            
    except Exception as e:
        print(f"❌ Error sincronizando comandos: {e}")
        traceback.print_exc()

    limpiar_tokens_expirados()
    print("\n🎮 Bot listo!")
    print("=" * 50)

@bot.event
async def on_guild_join(guild):
    print(f"📥 Bot añadido al servidor: {guild.name} (ID: {guild.id})")

@bot.event
async def on_guild_remove(guild):
    print(f"📤 Bot removido del servidor: {guild.name} (ID: {guild.id})")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏱️ Cooldown. Intenta en {error.retry_after:.1f}s", ephemeral=True)
    elif isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message("❌ No tienes permisos para este comando.", ephemeral=True)
    else:
        print(f"❌ Error en comando: {error}")
        traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Ocurrió un error. Inténtalo de nuevo.", ephemeral=True)

async def main():
    print("=" * 50)
    print("🚀 Iniciando Doce-Bt")
    print("=" * 50)
    print()

    if not DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN no configurado")
        return

    cleanup_legacy_json_files()

    async with bot:
        print("📦 Cargando extensiones...")
        await load_cogs()
        
        print(f"\n🌳 Comandos cargados: {len(list(bot.tree.walk_commands()))}")
        for cmd in bot.tree.walk_commands():
            print(f"   • {cmd.name}")
        
        set_bot(bot)
        Thread(target=run_flask, daemon=True).start()
        Thread(target=self_ping, daemon=True).start()
        
        print("\n🔌 Conectando a Discord...")
        await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Adiós!")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        traceback.print_exc()