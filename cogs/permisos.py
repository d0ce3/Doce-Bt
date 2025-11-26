import discord
from discord.ext import commands
from discord import app_commands

from utils.jsondb import safe_load, safe_save
from utils.embed_factory import (
    crear_embed_exito,
    crear_embed_error,
    crear_embed_info,
)
from config import VINCULACIONES_FILE


class PermisosCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="permitir",
        description="Otorga permiso a otro usuario para controlar tu Codespace",
    )
    @app_commands.describe(usuario="Usuario a autorizar")
    async def permitir(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Permite a otro usuario controlar tu codespace"""
        owner_id = str(interaction.user.id)
        vinculaciones = safe_load(VINCULACIONES_FILE)

        if owner_id not in vinculaciones:
            embed = crear_embed_error(
                "❌ Sin Codespace Vinculado",
                "No tienes un Codespace vinculado. Usa `/vincular` primero.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        if usuario.id == interaction.user.id:
            embed = crear_embed_error(
                "❌ Operación Inválida",
                "No puedes darte permiso a ti mismo.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        permisos = vinculaciones[owner_id].setdefault("permisos", [])
        if usuario.id in permisos:
            embed = crear_embed_info(
                "ℹ️ Usuario Ya Autorizado",
                f"<@{usuario.id}> ya tiene acceso a tu Codespace.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        permisos.append(usuario.id)
        safe_save(VINCULACIONES_FILE, vinculaciones)

        codespace = vinculaciones[owner_id]["codespace"]
        embed = crear_embed_exito(
            "✅ Permiso Otorgado",
            (
                f"<@{usuario.id}> ahora puede controlar tu Codespace `{codespace}`.\n\n"
                f"Puede usar `/start`, `/stop` y `/status`."
            ),
            footer=f"Total de usuarios autorizados: {len(permisos)}",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="revocar",
        description="Revoca el permiso de un usuario",
    )
    @app_commands.describe(usuario="Usuario a revocar")
    async def revocar(
        self,
        interaction: discord.Interaction,
        usuario: discord.Member,
    ):
        """Revoca el permiso de un usuario"""
        owner_id = str(interaction.user.id)
        vinculaciones = safe_load(VINCULACIONES_FILE)

        if owner_id not in vinculaciones:
            embed = crear_embed_error(
                "❌ Sin Codespace Vinculado",
                "No tienes un Codespace vinculado.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        permisos = vinculaciones[owner_id].get("permisos", [])
        if usuario.id not in permisos:
            embed = crear_embed_info(
                "ℹ️ Usuario Sin Permisos",
                f"<@{usuario.id}> no tiene acceso a tu Codespace.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        permisos.remove(usuario.id)
        safe_save(VINCULACIONES_FILE, vinculaciones)

        codespace = vinculaciones[owner_id]["codespace"]
        embed = crear_embed_exito(
            "✅ Permiso Revocado",
            f"<@{usuario.id}> ya no puede controlar tu Codespace `{codespace}`.",
            footer=f"Total de usuarios autorizados: {len(permisos)}",
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="permisos",
        description="Ver lista de usuarios autorizados",
    )
    async def permisos_lista(self, interaction: discord.Interaction):
        """Muestra la lista de usuarios con permisos"""
        owner_id = str(interaction.user.id)
        vinculaciones = safe_load(VINCULACIONES_FILE)

        if owner_id not in vinculaciones:
            embed = crear_embed_error(
                "❌ Sin Codespace Vinculado",
                "No tienes un Codespace vinculado.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        data = vinculaciones[owner_id]
        codespace = data.get("codespace", "Desconocido")
        permisos = data.get("permisos", [])

        embed = crear_embed_info(
            "👥 Usuarios Autorizados",
            f"**Codespace:** `{codespace}`\n**Total:** {len(permisos)} usuarios",
        )

        if permisos:
            usuarios_str = "\n".join([f"• <@{uid}>" for uid in permisos])
            embed.add_field(
                name="Lista de Usuarios",
                value=usuarios_str,
                inline=False,
            )
        else:
            embed.add_field(
                name="Lista de Usuarios",
                value="*Ninguno*",
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PermisosCog(bot))
