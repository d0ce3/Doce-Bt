import discord
from discord.ext import commands
from discord import app_commands

from utils.permissions import obtener_contexto_usuario, sesion_valida
from utils.github_api import (
    iniciar_codespace,
    detener_codespace,
    estado_codespace,
)
from utils.embed_factory import (
    crear_embed_exito,
    crear_embed_error,
    crear_embed_info,
)
from utils.notify import enviar_log_al_propietario
from utils.jsondb import safe_load, safe_save
from config import SESIONES_FILE
from datetime import datetime, timedelta


class CodespaceControlCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def renovar_vinculacion(self, user_id):
        sesiones = safe_load(SESIONES_FILE)
        if user_id in sesiones:
            sesiones[user_id]["expira_vinculacion"] = (
                datetime.now() + timedelta(days=3)
            ).isoformat()
            safe_save(SESIONES_FILE, sesiones)

    @app_commands.command(
        name="start",
        description="Inicia tu Codespace o uno autorizado",
    )
    async def start(self, interaction: discord.Interaction):
        calling_id = interaction.user.id
        owner_id, codespace, sesion = obtener_contexto_usuario(
            calling_id
        )

        if not owner_id:
            embed = crear_embed_error(
                "❌ Sin Acceso",
                (
                    "No tienes permiso para iniciar ningún Codespace.\n\n"
                    "Pide al propietario que te otorgue acceso con `/permitir`."
                ),
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        if not sesion_valida(sesion):
            embed = crear_embed_error(
                "⏱️ Sesión Expirada",
                (
                    "La sesión del propietario expiró.\n\n"
                    "Pide al propietario que renueve su token con `/setup`."
                ),
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        self.renovar_vinculacion(owner_id)

        await interaction.response.defer()

        token = sesion["token"]
        success, mensaje = iniciar_codespace(token, codespace)

        if success:
            embed = crear_embed_exito(
                "✅ Codespace Iniciado",
                (
                    f"**Codespace:** `{codespace}`\n"
                    f"**Iniciado por:** <@{calling_id}>\n\n"
                    "⏳ Espera ~30 segundos para que esté completamente listo."
                ),
                footer="Usa /status para verificar el estado",
            )
            await interaction.followup.send(embed=embed)

            await enviar_log_al_propietario(
                self.bot,
                codespace,
                f"Tu Codespace fue iniciado por <@{calling_id}>",
            )
        else:
            embed = crear_embed_error(
                "❌ Error al Iniciar",
                f"**Codespace:** `{codespace}`\n\n**Error:** {mensaje}",
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="stop",
        description="Detiene tu Codespace o uno autorizado",
    )
    async def stop(self, interaction: discord.Interaction):
        calling_id = interaction.user.id
        owner_id, codespace, sesion = obtener_contexto_usuario(
            calling_id
        )

        if not owner_id:
            embed = crear_embed_error(
                "❌ Sin Acceso",
                "No tienes permiso para detener ningún Codespace.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        if not sesion_valida(sesion):
            embed = crear_embed_error(
                "⏱️ Sesión Expirada",
                "La sesión del propietario expiró.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        self.renovar_vinculacion(owner_id)

        await interaction.response.defer()

        token = sesion["token"]
        success, mensaje = detener_codespace(token, codespace)

        if success:
            embed = crear_embed_exito(
                "✅ Codespace Detenido",
                (
                    f"**Codespace:** `{codespace}`\n"
                    f"**Detenido por:** <@{calling_id}>"
                ),
                footer="doce|tools v2",
            )
            await interaction.followup.send(embed=embed)

            await enviar_log_al_propietario(
                self.bot,
                codespace,
                f"Tu Codespace fue detenido por <@{calling_id}>",
            )
        else:
            embed = crear_embed_error(
                "❌ Error al Detener",
                f"**Codespace:** `{codespace}`\n\n**Error:** {mensaje}",
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="status",
        description="Consulta el estado de tu Codespace o uno autorizado",
    )
    async def status(self, interaction: discord.Interaction):
        calling_id = interaction.user.id
        owner_id, codespace, sesion = obtener_contexto_usuario(
            calling_id
        )

        if not owner_id:
            embed = crear_embed_error(
                "❌ Sin Acceso",
                "No tienes acceso a ningún Codespace.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        if not sesion_valida(sesion):
            embed = crear_embed_error(
                "⏱️ Sesión Expirada",
                "La sesión del propietario expiró.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        self.renovar_vinculacion(owner_id)

        await interaction.response.defer()

        token = sesion["token"]
        estado, error = estado_codespace(token, codespace)

        expira_str = sesion.get("expira", "")
        tiempo_restante = "Desconocido"

        try:
            expira = datetime.fromisoformat(expira_str)
            diff = expira - datetime.now()
            h = int(diff.total_seconds() // 3600)
            m = int((diff.total_seconds() % 3600) // 60)
            tiempo_restante = f"🟢 {h}h {m}m restantes"
        except Exception:
            pass

        emojis = {
            "Available": "🟢",
            "Starting": "🟡",
            "Shutdown": "🔴",
            "Unknown": "❓",
        }
        emoji_estado = emojis.get(estado, "⚪")

        embed = crear_embed_info(
            "📊 Estado del Codespace",
            f"**Codespace:** `{codespace}`",
        )
        embed.add_field(
            name="Estado",
            value=f"{emoji_estado} {estado}",
            inline=True,
        )
        embed.add_field(
            name="Sesión",
            value=tiempo_restante,
            inline=True,
        )
        if error:
            embed.add_field(
                name="⚠️ Advertencia",
                value=error,
                inline=False,
            )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CodespaceControlCog(bot))
