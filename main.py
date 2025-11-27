import discord
from discord.ext import commands
import asyncio
from threading import Thread
import traceback

from config import DISCORD_BOT_TOKEN, GUILD_ID, SESIONES_FILE, PORT, RENDER_EXTERNAL_URL
from web.server import run_flask, set_bot
from web.auto_ping import self_ping
from utils.jsondb import safe_load, safe_save
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def limpiar_tokens_expirados():
    sesiones = safe_load(SESIONES_FILE)
    cambios = False
    ahora = datetime.now()

    for uid in list(sesiones.keys()):
        exp_token = sesiones[uid].get("expira_token")
        if not exp_token:
            continue

        try:
            if datetime.fromisoformat(exp_token) < ahora:
                sesiones[uid].pop("token", None)
                sesiones[uid]["expira_token"] = None
                cambios = True
                print(f"🗑️ Token eliminado para usuario {uid}")
        except Exception as e:
            print(f"⚠️ Error parseando fecha de expiración para {uid}: {e}")

    if cambios:
        safe_save(SESIONES_FILE, sesiones)


async def load_cogs():
    """Carga todos los cogs antes de sincronizar"""
    cogs = [
        "cogs.setup_cog",
        "cogs.permisos",
        "cogs.codespace_control",
        "cogs.codespace_minecraft",
        "cogs.info",
    ]

    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"✅ Cog cargado: {cog}")
        except Exception as e:
            print(f"❌ Error cargando {cog}: {e}")
            import traceback
            traceback.print_exc()
            traceback.print_exc()


@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")
    print(f"📊 Conectado a {len(bot.guilds)} servidores")
    
    try:
        # 🔥 SINCRONIZACIÓN HÍBRIDA: Guild específico + Global
        
        # 1. Sincronizar en servidor de pruebas (instantáneo)
        if GUILD_ID:
            guild = discord.utils.get(bot.guilds, id=GUILD_ID)
            
            if guild:
                print(f"🎯 Sincronizando en servidor de pruebas: {guild.name}")
                bot.tree.clear_commands(guild=guild)
                bot.tree.copy_global_to(guild=guild)
                cmds_guild = await bot.tree.sync(guild=guild)
                print(f"✅ {len(cmds_guild)} comandos en {guild.name}: {[c.name for c in cmds_guild]}")
            else:
                print(f"⚠️  Servidor {GUILD_ID} no encontrado")
        
        # 2. Sincronizar globalmente (tarda ~1 hora en propagarse)
        print("🌍 Sincronizando comandos globalmente...")
        cmds_global = await bot.tree.sync()
        print(f"✅ {len(cmds_global)} comandos globales sincronizados")
        print(f"📝 Lista: {[c.name for c in cmds_global]}")
        print("⏱️  Propagación global: hasta 1 hora")
            
    except Exception as e:
        print(f"❌ Error sincronizando comandos: {e}")
        traceback.print_exc()

    limpiar_tokens_expirados()
    print("\n🎮 Bot listo para usar!")
    print("=" * 50)


@bot.event
async def on_guild_join(guild):
    print(f"📥 Bot añadido al servidor: {guild.name} (ID: {guild.id})")


@bot.event
async def on_guild_remove(guild):
    print(f"📤 Bot removido del servidor: {guild.name} (ID: {guild.id})")


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError
):
    if isinstance(error, discord.app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"⏱️ Este comando está en cooldown. Intenta de nuevo en {error.retry_after:.1f}s",
            ephemeral=True
        )
    elif isinstance(error, discord.app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ No tienes permisos suficientes para usar este comando.",
            ephemeral=True
        )
    else:
        print(f"❌ Error en comando: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ Ocurrió un error al ejecutar el comando. Inténtalo de nuevo.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Ocurrió un error al ejecutar el comando.",
                ephemeral=True
            )


async def main():
    print("=" * 50)
    print("🚀 Iniciando doce|tools v2")
    print("=" * 50)

    if not DISCORD_BOT_TOKEN:
        print("❌ Error: DISCORD_BOT_TOKEN no configurado")
        print("Agrega tu token en el archivo .env")
        return

    # Cargar cogs antes de iniciar el bot
    async with bot:
        print("\n📦 Cargando extensiones (cogs)...")
        await load_cogs()
        
        print(f"\n🌳 Comandos cargados en el bot: {len(list(bot.tree.walk_commands()))}")
        for cmd in bot.tree.walk_commands():
            print(f"   • {cmd.name}")
        
        # Iniciar Flask y auto-ping
        set_bot(bot)
        Thread(target=run_flask, daemon=True).start()
        Thread(target=self_ping, daemon=True).start()
        
        print("\n🔌 Conectando a Discord...")
        # Iniciar el bot (on_ready hará el sync)
        await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Adiós!")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        traceback.print_exc()