import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

from utils.jsondb import safe_load, safe_save
from utils.github_api import validar_token, listar_codespaces
from utils.embed_factory import (
    crear_embed_exito,
    crear_embed_error,
    crear_embed_info,
)
from config import VINCULACIONES_FILE, SESIONES_FILE


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="Configura tu token personal de GitHub",
    )
    @app_commands.describe(
        token="Tu token personal con scope 'codespace'"
    )
    async def setup(self, interaction: discord.Interaction, token: str):
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        valido, resultado = validar_token(token)

        if not valido:
            embed = crear_embed_error(
                "❌ Token Inválido",
                (
                    f"No se pudo validar el token.\n\n**Error:** {resultado}\n\n"
                    "Asegúrate que tenga scope `codespace`."
                ),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        sesiones = safe_load(SESIONES_FILE)
        
        # Preservar codespace anterior si existe
        codespace_anterior = sesiones.get(user_id, {}).get("codespace")
        
        sesiones[user_id] = {
            "token": token,
            "expira": (datetime.now() + timedelta(hours=5)).isoformat(),
            "usuario_github": resultado,
            "codespace": codespace_anterior,
            "token_actualizado": datetime.now().isoformat()
        }
        safe_save(SESIONES_FILE, sesiones)

        embed = crear_embed_exito(
            "✅ Token Configurado",
            (
                f"Token guardado por 5 horas.\n"
                f"Usuario GitHub: `{resultado}`\n\n"
                "Ahora usa `/vincular` para conectar tu Codespace."
            ),
            footer="doce|tools v2"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="vincular",
        description="Vincula tu Codespace a tu cuenta",
    )
    @app_commands.describe(
        codespace="Nombre de tu Codespace (opcional, se mostrará lista)"
    )
    async def vincular(
        self,
        interaction: discord.Interaction,
        codespace: str | None = None,
    ):
        user_id = str(interaction.user.id)
        sesiones = safe_load(SESIONES_FILE)

        if user_id not in sesiones or not sesiones[user_id].get("token"):
            embed = crear_embed_error(
                "❌ Token no configurado",
                "Antes configura tu token con `/setup`",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        token = sesiones[user_id]["token"]

        # Si no especificó codespace, mostrar lista
        if not codespace:
            await interaction.response.defer(ephemeral=True)

            codespaces_list, error = listar_codespaces(token)
            if error:
                embed = crear_embed_error(
                    "❌ Error listando Codespaces",
                    f"Error: {error}",
                )
                await interaction.followup.send(
                    embed=embed, ephemeral=True
                )
                return

            if not codespaces_list:
                embed = crear_embed_error(
                    "❌ No tienes Codespaces",
                    "Crea uno en GitHub y vuelve a intentarlo.",
                )
                await interaction.followup.send(
                    embed=embed, ephemeral=True
                )
                return

            # Mostrar lista con información detallada
            vinculaciones = safe_load(VINCULACIONES_FILE)
            codespace_actual = vinculaciones.get(user_id, {}).get("codespace")
            historial = vinculaciones.get(user_id, {}).get("historial", [])
            
            lista = []
            for c in codespaces_list[:10]:
                nombre = c['name']
                estado = c['state']
                
                # Marcar si es el actual
                marca = "⭐" if nombre == codespace_actual else "  "
                
                # Buscar en historial
                fecha_vinculacion = None
                for h in historial:
                    if h.get("codespace") == nombre:
                        fecha_vinculacion = h.get("fecha")
                        break
                
                if fecha_vinculacion:
                    # Parsear fecha
                    try:
                        dt = datetime.fromisoformat(fecha_vinculacion)
                        fecha_str = dt.strftime("%d/%m %H:%M")
                        lista.append(f"{marca} `{nombre}` - {estado} (vinculado: {fecha_str})")
                    except:
                        lista.append(f"{marca} `{nombre}` - {estado}")
                else:
                    lista.append(f"{marca} `{nombre}` - {estado}")
            
            descripcion = "\n".join(lista)
            descripcion += "\n\n⭐ = Codespace actual"
            descripcion += "\n\nUsa `/vincular codespace:<nombre>` para vincular uno."
            
            embed = crear_embed_info(
                "📋 Tus Codespaces",
                descripcion
            )
            await interaction.followup.send(
                embed=embed, ephemeral=True
            )
            return

        # Vincular el codespace especificado
        vinculaciones = safe_load(VINCULACIONES_FILE)
        permisos_previos = vinculaciones.get(user_id, {}).get("permisos", [])
        historial = vinculaciones.get(user_id, {}).get("historial", [])
        
        # Agregar al historial
        fecha_actual = datetime.now().isoformat()
        
        # Actualizar historial (máximo 10 entradas)
        nueva_entrada = {
            "codespace": codespace,
            "fecha": fecha_actual
        }
        
        # Remover entrada anterior del mismo codespace si existe
        historial = [h for h in historial if h.get("codespace") != codespace]
        historial.insert(0, nueva_entrada)
        historial = historial[:10]  # Mantener solo últimos 10

        vinculaciones[user_id] = {
            "codespace": codespace,
            "permisos": permisos_previos,
            "historial": historial,
            "ultima_vinculacion": fecha_actual
        }
        safe_save(VINCULACIONES_FILE, vinculaciones)

        sesiones[user_id]["codespace"] = codespace
        sesiones[user_id]["expira"] = (datetime.now() + timedelta(hours=5)).isoformat()
        safe_save(SESIONES_FILE, sesiones)

        # Formatear fecha para mostrar
        dt = datetime.now()
        fecha_legible = dt.strftime("%d/%m/%Y %H:%M")

        embed = crear_embed_exito(
            "✅ Codespace Vinculado",
            (
                f"**Codespace:** `{codespace}`\n"
                f"**Fecha:** {fecha_legible}\n\n"
                "Ahora puedes usar los comandos de control desde Discord."
            ),
            footer="La sesión expira en 5 horas"
        )
        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )

    @app_commands.command(
        name="refrescar",
        description="Renueva tu sesión por 5 horas más",
    )
    async def refrescar(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        sesiones = safe_load(SESIONES_FILE)

        if user_id not in sesiones or not sesiones[user_id].get("token"):
            await interaction.response.send_message(
                "❌ No tienes token configurado. Usa `/setup` para registrar tu token.",
                ephemeral=True,
            )
            return

        # Renovar sesión
        sesiones[user_id]["expira"] = (
            datetime.now() + timedelta(hours=5)
        ).isoformat()
        safe_save(SESIONES_FILE, sesiones)

        # Calcular tiempo restante
        expira = datetime.fromisoformat(sesiones[user_id]["expira"])
        tiempo_restante = expira - datetime.now()
        horas = int(tiempo_restante.total_seconds() // 3600)
        minutos = int((tiempo_restante.total_seconds() % 3600) // 60)

        embed = crear_embed_exito(
            "✅ Sesión Renovada",
            f"Tu sesión ha sido renovada.\n\n**Expira en:** {horas}h {minutos}m",
            footer="Usa /refrescar cuando necesites renovar"
        )
        
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @app_commands.command(
        name="historial",
        description="Ver historial de Codespaces vinculados",
    )
    async def historial(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        vinculaciones = safe_load(VINCULACIONES_FILE)

        if user_id not in vinculaciones:
            embed = crear_embed_error(
                "❌ Sin Codespaces",
                "No has vinculado ningún Codespace aún.\n\nUsa `/vincular` para comenzar.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        data = vinculaciones[user_id]
        codespace_actual = data.get("codespace", "Ninguno")
        historial = data.get("historial", [])

        if not historial:
            embed = crear_embed_info(
                "📋 Historial de Codespaces",
                f"**Actual:** `{codespace_actual}`\n\nNo hay historial previo.",
            )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        # Construir lista
        lista = []
        for i, entrada in enumerate(historial[:10], 1):
            nombre = entrada.get("codespace", "Desconocido")
            fecha = entrada.get("fecha", "")
            
            # Formatear fecha
            try:
                dt = datetime.fromisoformat(fecha)
                fecha_str = dt.strftime("%d/%m/%Y %H:%M")
            except:
                fecha_str = "Fecha desconocida"
            
            # Marcar el actual
            marca = "⭐" if nombre == codespace_actual else f"{i}."
            lista.append(f"{marca} `{nombre}` - {fecha_str}")

        descripcion = "\n".join(lista)
        descripcion += "\n\n⭐ = Codespace actual"

        embed = crear_embed_info(
            "📋 Historial de Codespaces",
            descripcion,
            footer=f"Total: {len(historial)} codespaces vinculados"
        )
        
        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))