import discord
from discord.ext import commands
from discord import app_commands
from utils.jsondb import safe_load
from utils.permissions import obtener_contexto_usuario, sesion_valida
from utils.embed_factory import crear_embed_info, crear_embed_error
from config import VINCULACIONES_FILE
from datetime import datetime

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="info", description="Ver tu configuración y permisos")
    async def info(self, interaction: discord.Interaction):
        """Muestra información del usuario"""
        user_id = str(interaction.user.id)
        vinculaciones = safe_load(VINCULACIONES_FILE)

        if user_id not in vinculaciones:
            embed = crear_embed_error(
                "❌ Sin Configuración",
                "No tienes un Codespace vinculado.\n\n"
                "Usa `/setup` y `/vincular` para comenzar."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        data = vinculaciones[user_id]
        codespace = data.get("codespace", "Desconocido")
        permisos = data.get("permisos", [])

        # Verificar estado de sesión
        owner_id, _, sesion = obtener_contexto_usuario(interaction.user.id)
        sesion_activa = sesion_valida(sesion)

        tiempo_restante = "❌ Expirada"
        if sesion_activa and sesion:
            try:
                expira = datetime.fromisoformat(sesion.get("expira", ""))
                diff = expira - datetime.now()
                h = int(diff.total_seconds() // 3600)
                m = int((diff.total_seconds() % 3600) // 60)
                tiempo_restante = f"✅ {h}h {m}m restantes"
            except:
                tiempo_restante = "❓ Desconocido"

        embed = crear_embed_info(
            "📋 Tu Configuración - doce|tools",
            f"**Usuario:** <@{user_id}>"
        )

        embed.add_field(
            name="🖥️ Codespace Vinculado",
            value=f"`{codespace}`",
            inline=False
        )

        embed.add_field(
            name="⏱️ Sesión",
            value=tiempo_restante,
            inline=True
        )

        embed.add_field(
            name="👥 Usuarios Autorizados",
            value=f"{len(permisos)} usuarios",
            inline=True
        )

        if permisos:
            usuarios_str = "\n".join([f"• <@{uid}>" for uid in permisos[:5]])
            if len(permisos) > 5:
                usuarios_str += f"\n... y {len(permisos) - 5} más"
            embed.add_field(name="Lista de Autorizados", value=usuarios_str, inline=False)

        embed.set_footer(text="doce|tools v2")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ayuda", description="Muestra todos los comandos disponibles")
    async def ayuda(self, interaction: discord.Interaction):
        """Muestra la ayuda del bot"""
        embed = discord.Embed(
            title="🛠️ doce|tools v2 - Comandos",
            description="Bot para controlar GitHub Codespaces desde Discord",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="⚙️ Configuración Inicial",
            value=(
                "`/setup token:<tu_token>` - Configura tu token de GitHub\n"
                "`/vincular [codespace]` - Vincula tu Codespace"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 Control de Codespace",
            value=(
                "`/start` - Inicia tu Codespace\n"
                "`/stop` - Detiene tu Codespace\n"
                "`/status` - Consulta el estado"
            ),
            inline=False
        )

        embed.add_field(
            name="👥 Gestión de Permisos",
            value=(
                "`/permitir @usuario` - Otorga acceso a otro usuario\n"
                "`/revocar @usuario` - Revoca el acceso\n"
                "`/permisos` - Lista de usuarios autorizados"
            ),
            inline=False
        )

        embed.add_field(
            name="ℹ️ Información",
            value=(
                "`/info` - Tu configuración actual\n"
                "`/ayuda` - Este mensaje"
            ),
            inline=False
        )

        embed.add_field(
            name="🔗 Enlaces Útiles",
            value=(
                "[Crear Token GitHub](https://github.com/settings/tokens)\n"
                "[Documentación](https://github.com/tu-repo/doce-tools)"
            ),
            inline=False
        )

        embed.set_footer(text="doce|tools v2 - Control de Codespaces multiusuario")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))
