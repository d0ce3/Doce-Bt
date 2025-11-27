import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional

from utils.permissions import obtener_contexto_usuario, sesion_valida
from utils.github_api import iniciar_codespace, estado_codespace
from utils.embed_factory import (
    crear_embed_exito,
    crear_embed_error,
    crear_embed_info,
    crear_embed_warning,
)
from utils.notify import enviar_log_al_propietario
from utils.jsondb import safe_load, safe_save
from config import SESIONES_FILE, VINCULACIONES_FILE


class CodespaceMinecraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitoreando = {}  # {user_id: {"ip": "...", "channel_id": ...}}
        self.ultimo_estado = {}  # {user_id: True/False}
        self.monitor_loop.start()

    def cog_unload(self):
        self.monitor_loop.cancel()

    @tasks.loop(minutes=1)
    async def monitor_loop(self):
        """Monitorea servidores de Minecraft cada minuto"""
        for user_id, data in list(self.monitoreando.items()):
            try:
                ip = data.get("ip")
                channel_id = data.get("channel_id")
                
                if not ip or not channel_id:
                    continue
                
                # Consultar estado del servidor
                online = await self.verificar_servidor_minecraft(ip)
                estado_anterior = self.ultimo_estado.get(user_id, False)
                
                # Si cambió el estado, notificar
                if online != estado_anterior:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        if online:
                            embed = crear_embed_exito(
                                "🟢 Servidor Online",
                                f"**IP:** `{ip}`\n\n"
                                f"El servidor de Minecraft está ahora **ONLINE** y aceptando conexiones.",
                                footer="Monitoreando cada 1 minuto"
                            )
                        else:
                            embed = crear_embed_warning(
                                "🔴 Servidor Offline",
                                f"**IP:** `{ip}`\n\n"
                                f"El servidor de Minecraft está ahora **OFFLINE**.",
                                footer="Monitoreando cada 1 minuto"
                            )
                        
                        await channel.send(embed=embed)
                    
                    self.ultimo_estado[user_id] = online
                    
            except Exception as e:
                print(f"Error monitoreando servidor para {user_id}: {e}")

    @monitor_loop.before_loop
    async def before_monitor_loop(self):
        await self.bot.wait_until_ready()

    async def verificar_servidor_minecraft(self, ip: str) -> bool:
        """Verifica si un servidor de Minecraft está online usando mcstatus.io"""
        try:
            # Separar IP y puerto si existe
            if ":" in ip:
                host, port = ip.split(":", 1)
            else:
                host = ip
                port = "25565"
            
            url = f"https://api.mcstatus.io/v2/status/java/{host}:{port}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("online", False)
                    return False
        except Exception as e:
            print(f"Error verificando servidor {ip}: {e}")
            return False

    @app_commands.command(
        name="minecraft_start",
        description="Inicia tu Codespace y monitorea el servidor de Minecraft"
    )
    @app_commands.describe(
        ip="IP del servidor Minecraft (ej: ejemplo.com:25565)"
    )
    async def minecraft_start(
        self,
        interaction: discord.Interaction,
        ip: Optional[str] = None
    ):
        """Inicia codespace y comienza monitoreo de servidor Minecraft"""
        calling_id = interaction.user.id
        owner_id, codespace, sesion = obtener_contexto_usuario(calling_id)

        if not owner_id:
            embed = crear_embed_error(
                "❌ Sin Acceso",
                "No tienes permiso para iniciar ningún Codespace."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not sesion_valida(sesion):
            embed = crear_embed_error(
                "⏱️ Sesión Expirada",
                "La sesión del propietario expiró."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Iniciar codespace
        token = sesion["token"]
        success, mensaje = iniciar_codespace(token, codespace)

        if not success:
            embed = crear_embed_error(
                "❌ Error al Iniciar",
                f"**Codespace:** `{codespace}`\n\n**Error:** {mensaje}"
            )
            await interaction.followup.send(embed=embed)
            return

        # Si se proporcionó IP, iniciar monitoreo
        if ip:
            self.monitoreando[str(owner_id)] = {
                "ip": ip,
                "channel_id": interaction.channel_id
            }
            self.ultimo_estado[str(owner_id)] = False
            
            embed = crear_embed_exito(
                "✅ Codespace Iniciado",
                (
                    f"**Codespace:** `{codespace}`\n"
                    f"**Iniciado por:** <@{calling_id}>\n"
                    f"**IP Minecraft:** `{ip}`\n\n"
                    "⏳ Esperando ~30 segundos para que el Codespace esté listo...\n"
                    "🔍 Monitoreando servidor Minecraft (recibirás notificación cuando esté online)"
                ),
                footer="Usa /minecraft_stop para detener"
            )
        else:
            embed = crear_embed_exito(
                "✅ Codespace Iniciado",
                (
                    f"**Codespace:** `{codespace}`\n"
                    f"**Iniciado por:** <@{calling_id}>\n\n"
                    "⏳ Esperando ~30 segundos para que esté listo.\n\n"
                    "💡 Usa `/minecraft_start ip:<tu_ip>` para monitorear el servidor"
                ),
                footer="Usa /stop para detener"
            )

        await interaction.followup.send(embed=embed)
        await enviar_log_al_propietario(
            self.bot,
            codespace,
            f"Tu Codespace fue iniciado por <@{calling_id}>"
        )

    @app_commands.command(
        name="minecraft_stop",
        description="Detiene el monitoreo del servidor de Minecraft"
    )
    async def minecraft_stop(self, interaction: discord.Interaction):
        """Detiene el monitoreo de Minecraft"""
        calling_id = interaction.user.id
        owner_id, codespace, sesion = obtener_contexto_usuario(calling_id)

        if not owner_id:
            embed = crear_embed_error(
                "❌ Sin Acceso",
                "No tienes ningún servidor siendo monitoreado."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if str(owner_id) in self.monitoreando:
            ip = self.monitoreando[str(owner_id)].get("ip", "Desconocido")
            del self.monitoreando[str(owner_id)]
            self.ultimo_estado.pop(str(owner_id), None)
            
            embed = crear_embed_exito(
                "✅ Monitoreo Detenido",
                f"**IP:** `{ip}`\n\nYa no se monitoreará este servidor.",
                footer="doce|tools v2"
            )
        else:
            embed = crear_embed_info(
                "ℹ️ Sin Monitoreo Activo",
                "No hay ningún servidor siendo monitoreado actualmente."
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="minecraft_status",
        description="Consulta el estado de un servidor de Minecraft"
    )
    @app_commands.describe(
        ip="IP del servidor (ej: mc.hypixel.net)"
    )
    async def minecraft_status(
        self,
        interaction: discord.Interaction,
        ip: str
    ):
        """Consulta el estado de un servidor de Minecraft"""
        await interaction.response.defer()

        try:
            # Separar IP y puerto
            if ":" in ip:
                host, port = ip.split(":", 1)
            else:
                host = ip
                port = "25565"
            
            url = f"https://api.mcstatus.io/v2/status/java/{host}:{port}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        embed = crear_embed_error(
                            "❌ Error",
                            f"No se pudo consultar el servidor `{ip}`"
                        )
                        await interaction.followup.send(embed=embed)
                        return
                    
                    data = await resp.json()
            
            online = data.get("online", False)
            
            if not online:
                embed = crear_embed_error(
                    "🔴 Servidor Offline",
                    f"**IP:** `{ip}`\n\nEl servidor no está respondiendo."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Servidor online - mostrar información
            players_online = data.get("players", {}).get("online", 0)
            players_max = data.get("players", {}).get("max", 0)
            version = data.get("version", {}).get("name_clean", "Desconocido")
            motd = data.get("motd", {}).get("clean", "Sin descripción")
            
            embed = crear_embed_exito(
                "🟢 Servidor Online",
                f"**IP:** `{ip}`\n**Versión:** {version}\n**MOTD:** {motd}"
            )
            
            embed.add_field(
                name="👥 Jugadores",
                value=f"{players_online}/{players_max}",
                inline=True
            )
            
            # Latencia si está disponible
            if "latency" in data:
                latency = data["latency"]
                embed.add_field(
                    name="📡 Latencia",
                    value=f"{latency}ms",
                    inline=True
                )
            
            embed.set_footer(text="Powered by mcstatus.io")
            
            # Agregar favicon si existe
            if data.get("icon"):
                embed.set_thumbnail(url=data["icon"])
            
            await interaction.followup.send(embed=embed)
            
        except asyncio.TimeoutError:
            embed = crear_embed_error(
                "⏱️ Timeout",
                f"El servidor `{ip}` no respondió a tiempo."
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = crear_embed_error(
                "❌ Error",
                f"Error al consultar el servidor:\n```{str(e)}```"
            )
            await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(CodespaceMinecraftCog(bot))
