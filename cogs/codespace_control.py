import discord
from discord.ext import commands
from discord import app_commands

from utils.permissions import obtener_contexto_usuario, sesion_valida
from utils.github_api import detener_codespace, estado_codespace
from utils.codespace_wake import despertar_codespace_real, verificar_estado_codespace
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
        description="Inicia tu Codespace (REALMENTE lo despierta, no solo cambia estado)",
    )
    async def start(self, interaction: discord.Interaction):
        calling_id = interaction.user.id
        owner_id, codespace, sesion = obtener_contexto_usuario(calling_id)

        if not owner_id:
            embed = crear_embed_error(
                "❌ Sin Acceso",
                (
                    "No tienes permiso para iniciar ningún Codespace.\n\n"
                    "Pide al propietario que te otorgue acceso con `/permitir`."
                ),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not sesion_valida(sesion):
            embed = crear_embed_error(
                "⏱️ Sesión Expirada",
                (
                    "La sesión del propietario expiró.\n\n"
                    "Pide al propietario que renueve su token con `/setup`."
                ),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        self.renovar_vinculacion(owner_id)

        # Mostrar mensaje inicial
        await interaction.response.defer()

        token = sesion["token"]
        
        # Obtener URL del codespace (priorizar Cloudflare Tunnel)
        codespace_url = sesion.get("tunnel_url") or sesion.get("codespace_url")
        
        # Crear embed de inicio
        embed_inicio = crear_embed_info(
            "🔄 Iniciando Codespace",
            (
                f"**Codespace:** `{codespace}`\n"
                f"**Iniciado por:** <@{calling_id}>\n\n"
                "⏳ **Despertando la máquina virtual...**\n\n"
                "Este proceso puede tardar 1-3 minutos:\n"
                "1. ✅ Cambiar estado en API\n"
                "2. 🔄 Despertar VM con requests HTTP\n"
                "3. ✅ Verificar que esté completamente activo\n\n"
                "💡 Esto es diferente al `/start` anterior que solo cambiaba el estado."
            ),
            footer="Ten paciencia, estamos iniciando la VM REALMENTE"
        )
        await interaction.followup.send(embed=embed_inicio)
        
        # 🔥 USAR NUEVA FUNCIÓN: Despertar REALMENTE el codespace
        print(f"🚀 Despertando Codespace '{codespace}' para usuario {owner_id}")
        
        success, mensaje = await despertar_codespace_real(
            token=token,
            codespace_name=codespace,
            codespace_url=codespace_url,
            max_intentos=12,  # 12 intentos
            timeout_inicial=180  # 3 minutos máximo
        )

        if success:
            embed = crear_embed_exito(
                "✅ Codespace Iniciado y Listo",
                (
                    f"**Codespace:** `{codespace}`\n"
                    f"**Iniciado por:** <@{calling_id}>\n\n"
                    f"✅ **{mensaje}**\n\n"
                    "🎮 La VM está completamente activa y lista para usar.\n"
                    "Ahora puedes:\n"
                    "• Ejecutar `/minecraft_start` para iniciar Minecraft\n"
                    "• Conectarte vía navegador o VS Code\n"
                    "• Ejecutar comandos remotos"
                ),
                footer="La VM está REALMENTE despierta, no en hibernación"
            )
            await interaction.edit_original_response(embed=embed)

            await enviar_log_al_propietario(
                self.bot,
                codespace,
                f"✅ Tu Codespace fue iniciado EXITOSAMENTE por <@{calling_id}>.\n\n"
                f"Mensaje: {mensaje}"
            )
        else:
            # Obtener estado actual para diagnóstico
            estado_actual, _ = await verificar_estado_codespace(token, codespace)
            
            embed = crear_embed_error(
                "❌ Error al Despertar Codespace",
                (
                    f"**Codespace:** `{codespace}`\n"
                    f"**Estado actual:** `{estado_actual}`\n\n"
                    f"**Error:** {mensaje}\n\n"
                    "**Posibles causas:**\n"
                    "• El Codespace está tardando más de lo normal\n"
                    "• Problemas de conectividad con GitHub\n"
                    "• El Codespace puede requerir inicio manual\n\n"
                    "**Soluciones:**\n"
                    "1. Espera 2-3 minutos y usa `/status` para verificar\n"
                    "2. Intenta iniciar manualmente desde GitHub\n"
                    "3. Si el estado es 'Available', el Codespace está listo"
                ),
            )
            await interaction.edit_original_response(embed=embed)

    @app_commands.command(
        name="stop",
        description="Detiene tu Codespace o uno autorizado",
    )
    async def stop(self, interaction: discord.Interaction):
        calling_id = interaction.user.id
        owner_id, codespace, sesion = obtener_contexto_usuario(calling_id)

        if not owner_id:
            embed = crear_embed_error(
                "❌ Sin Acceso",
                "No tienes permiso para detener ningún Codespace.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not sesion_valida(sesion):
            embed = crear_embed_error(
                "⏱️ Sesión Expirada",
                "La sesión del propietario expiró.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
                    f"**Detenido por:** <@{calling_id}>\n\n"
                    "La VM se está apagando correctamente."
                ),
                footer="d0ce3|tools v2"
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
        owner_id, codespace, sesion = obtener_contexto_usuario(calling_id)

        if not owner_id:
            embed = crear_embed_error(
                "❌ Sin Acceso",
                "No tienes acceso a ningún Codespace.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not sesion_valida(sesion):
            embed = crear_embed_error(
                "⏱️ Sesión Expirada",
                "La sesión del propietario expiró.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        # Información adicional según el estado
        info_adicional = {
            "Available": "✅ Completamente activo y listo para usar",
            "Starting": "⏳ Iniciando... usa `/start` si tardó más de 3 minutos",
            "Shutdown": "🔴 Apagado - usa `/start` para iniciar",
            "Unknown": "❓ Estado desconocido - verifica en GitHub"
        }

        embed = crear_embed_info(
            "📊 Estado del Codespace",
            f"**Codespace:** `{codespace}`",
        )
        embed.add_field(
            name="Estado",
            value=f"{emoji_estado} **{estado}**\n{info_adicional.get(estado, '')}",
            inline=False,
        )
        embed.add_field(
            name="Sesión del Token",
            value=tiempo_restante,
            inline=True,
        )
        
        # Mostrar URL si está disponible
        tunnel_url = sesion.get("tunnel_url")
        if tunnel_url:
            embed.add_field(
                name="🌐 Conexión",
                value="Cloudflare Tunnel activo",
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