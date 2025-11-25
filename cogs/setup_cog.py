import discord
from discord.ext import commands
from discord import app_commands
from utils.jsondb import safe_load, safe_save
from utils.github_api import validar_token, listar_codespaces
from utils.embed_factory import crear_embed_exito, crear_embed_error, crear_embed_info
from config import VINCULACIONES_FILE, SESIONES_FILE
from datetime import datetime, timedelta

class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configura tu token personal de GitHub")
    @app_commands.describe(token="Tu token personal con scope 'codespace'")
    async def setup(self, interaction: discord.Interaction, token: str):
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        valido, resultado = validar_token(token)

        if not valido:
            embed = crear_embed_error(
                "❌ Token Inválido",
                f"No se pudo validar el token.\n\n**Error:** {resultado}\n\n"
                "Asegúrate que tenga scope `codespace`."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        sesiones = safe_load(SESIONES_FILE)
        # Guardar token y renovaciones (mantener vinculacion y usuario github si existe)
        sesiones[user_id] = {
            "token": token,
            "expira_token": (datetime.now() + timedelta(hours=5)).isoformat(),
            "expira_vinculacion": sesiones.get(user_id, {}).get("expira_vinculacion",
                                       (datetime.now() + timedelta(days=3)).isoformat()),
            "usuario_github": resultado,
            "codespace": sesiones.get(user_id, {}).get("codespace")
        }
        safe_save(SESIONES_FILE, sesiones)

        embed = crear_embed_exito(
            "✅ Token Configurado",
            f"Token guardado por 5 horas.\nUsuario GitHub: `{resultado}`\n"
            "Ahora usa `/vincular` para ligar tu Codespace.",
            footer="doce|tools v2"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="vincular", description="Vincula tu Codespace a tu cuenta")
    @app_commands.describe(codespace="Nombre de tu Codespace (déjalo vacío para ver lista)")
    async def vincular(self, interaction: discord.Interaction, codespace: str = None):
        user_id = str(interaction.user.id)
        sesiones = safe_load(SESIONES_FILE)

        if user_id not in sesiones:
            embed = crear_embed_error(
                "❌ Token no configurado",
                "Antes configura tu token con `/setup`"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        token = sesiones[user_id]["token"]

        if not codespace:
            await interaction.response.defer(ephemeral=True)
            codespaces, error = listar_codespaces(token)
            if error:
                embed = crear_embed_error(
                    "❌ Error listando Codespaces",
                    f"Error: {error}"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            if not codespaces:
                embed = crear_embed_error(
                    "❌ No tienes Codespaces",
                    "Crea uno en GitHub y vuelve a intentarlo."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            lista = "\n".join([f"• `{c['name']}` Estado: **{c['state']}**" for c in codespaces[:10]])
            embed = crear_embed_info(
                "📋 Tus Codespaces",
                f"{lista}\nUsa `/vincular codespace:<nombre>` para vincular uno."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        vinculaciones = safe_load(VINCULACIONES_FILE)

        permisos_previos = vinculaciones.get(user_id, {}).get("permisos", [])
        # Reemplaza o añade vinculacion
        vinculaciones[user_id] = {
            "codespace": codespace,
            "permisos": permisos_previos
        }

        safe_save(VINCULACIONES_FILE, vinculaciones)

        # Guardar en sesiones renovando vinculación a 3 días
        sesiones[user_id]["codespace"] = codespace
        sesiones[user_id]["expira_vinculacion"] = (datetime.now() + timedelta(days=3)).isoformat()
        safe_save(SESIONES_FILE, sesiones)

        embed = crear_embed_exito(
            "✅ Codespace Vinculado",
            f"Codespace `{codespace}` vinculado a tu cuenta.\n"
            "La vinculación expirará en 3 días si no usas comandos.\n"
            "El token expirará en 5 horas si no lo refrescas con `/refrescar`.",
            footer="doce|tools v2"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="refrescar", description="Extiende 5 horas la validez de tu token de GitHub")
    async def refrescar(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        sesiones = safe_load(SESIONES_FILE)
        if user_id not in sesiones:
            await interaction.response.send_message("❌ No tienes token configurado. Usa `/setup` para registrar tu token.", ephemeral=True)
            return
        sesiones[user_id]["expira_token"] = (datetime.now() + timedelta(hours=5)).isoformat()
        safe_save(SESIONES_FILE, sesiones)
        await interaction.response.send_message("✅ Tu token ha sido renovado por 5 horas.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
