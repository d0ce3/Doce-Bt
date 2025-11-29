import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional
import os

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
        for user_id, data in list(self.monitoreando.items()):
            try:
                ip = data.get("ip")
                channel_id = data.get("channel_id")
                
                if not ip or not channel_id:
                    continue
                
                online = await self.verificar_servidor_minecraft(ip)
                estado_anterior = self.ultimo_estado.get(user_id, False)
                
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
        try:
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

    async def llamar_webhook_minecraft(self, codespace_url: str, auth_token: str) -> dict:
        try:
            url = f"{codespace_url}/minecraft/start"
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status in [200, 201]:
                        data = await resp.json()
                        return {"success": True, "data": data}
                    else:
                        text = await resp.text()
                        return {
                            "success": False,
                            "error": f"HTTP {resp.status}: {text}"
                        }
        except asyncio.TimeoutError:
            return {"success": False, "error": "Timeout al conectar con el Codespace"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def obtener_ip_desde_webhook(self, codespace_url: str, auth_token: str = None) -> Optional[str]:
        try:
            url = f"{codespace_url}/minecraft/ip"
            headers = {}
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success"):
                            return data.get("ip")
            return None
        except Exception as e:
            print(f"Error obteniendo IP: {e}")
            return None

    @app_commands.command(
        name="minecraft_start",
        description="Inicia tu Codespace y el servidor de Minecraft automáticamente"
    )
    async def minecraft_start(
        self,
        interaction: discord.Interaction
    ):
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

        # 1. Iniciar codespace
        token = sesion["token"]
        success, mensaje = iniciar_codespace(token, codespace)

        if not success:
            embed = crear_embed_error(
                "❌ Error al Iniciar",
                f"**Codespace:** `{codespace}`\n\n**Error:** {mensaje}"
            )
            await interaction.followup.send(embed=embed)
            return

        # Mensaje inicial
        embed = crear_embed_info(
            "⏳ Iniciando Sistema",
            (
                f"**Codespace:** `{codespace}`\n"
                f"**Iniciado por:** <@{calling_id}>\n\n"
                "✅ Codespace iniciado\n"
                "⏳ Esperando que esté listo (30 segundos)...\n"
                "🎮 Luego se iniciará Minecraft automáticamente"
            ),
            footer="Esto puede tardar 1-2 minutos"
        )
        msg = await interaction.followup.send(embed=embed)

        # 2. Esperar a que el Codespace esté listo
        await asyncio.sleep(30)

        # 3. Obtener URL del Codespace y auth token
        codespace_url = sesion.get("codespace_url")

        if not codespace_url:
            embed = crear_embed_error(
                "❌ Configuración Incompleta",
                (
                    "No se encontró la URL del Codespace.\n\n"
                    "Usa `/vincular` nuevamente para configurar correctamente."
                )
            )
            await msg.edit(embed=embed)
            return

        # Verificar servidor web + obtener token automáticamente
        async with aiohttp.ClientSession() as session:
            # 1. Health check
            try:
                async with session.get(f"{codespace_url}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        embed = crear_embed_error(
                            "❌ Servidor Web No Activo",
                            "Ejecuta auto_webserver_setup en tu Codespace"
                        )
                        await msg.edit(embed=embed)
                        return
            except Exception:
                embed = crear_embed_error(
                    "❌ Servidor Web No Activo",
                    "Ejecuta auto_webserver_setup en tu Codespace"
                )
                await msg.edit(embed=embed)
                return

            # 2. Obtener token
            try:
                async with session.get(f"{codespace_url}/get_token", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        embed = crear_embed_error(
                            "❌ Token No Disponible",
                            "Ejecuta auto_webserver_setup en tu Codespace"
                        )
                        await msg.edit(embed=embed)
                        return
                    token_data = await resp.json()
                    auth_token = token_data['token']
            except Exception:
                embed = crear_embed_error(
                    "❌ Error Obteniendo Token",
                    "Ejecuta auto_webserver_setup en tu Codespace"
                )
                await msg.edit(embed=embed)
                return

        # Actualizar mensaje
        embed = crear_embed_info(
            "⏳ Iniciando Minecraft",
            (
                f"**Codespace:** `{codespace}`\n\n"
                "✅ Codespace listo\n"
                "🚀 Ejecutando msx.py...\n"
                "⏳ Iniciando servidor de Minecraft..."
            ),
            footer="Espera aproximadamente 1 minuto"
        )
        await msg.edit(embed=embed)

        # 4. Llamar al webhook para iniciar Minecraft
        resultado = await self.llamar_webhook_minecraft(codespace_url, auth_token)

        if not resultado.get("success"):
            embed = crear_embed_error(
                "❌ Error al Iniciar Minecraft",
                (
                    f"**Error:** {resultado.get('error')}\n\n"
                    "💡 **Posibles causas:**\n"
                    "  • El servidor web no está ejecutándose en el Codespace\n"
                    "  • Token de autenticación inválido\n"
                    "  • msx.py no encontrado\n\n"
                    "**Solución:**\n"
                    "Ejecuta en el Codespace: `bash start_web_server.sh`"
                )
            )
            await msg.edit(embed=embed)
            return

        # 5. Esperar a que el servidor esté completamente listo
        await asyncio.sleep(30)

        # 6. Obtener IP del servidor
        ip = await self.obtener_ip_desde_webhook(codespace_url, auth_token)

        if not ip:
            data = resultado.get("data", {})
            estado = data.get("estado", {})
            ip = estado.get("ip")

        # 7. Mensaje final
        if ip:
            self.monitoreando[str(owner_id)] = {
                "ip": ip,
                "channel_id": interaction.channel_id
            }
            self.ultimo_estado[str(owner_id)] = False

            embed = crear_embed_exito(
                "✅ Minecraft Iniciado",
                (
                    f"**Codespace:** `{codespace}`\n"
                    f"**IP del Servidor:** `{ip}`\n\n"
                    "✅ Servidor de Minecraft iniciado correctamente\n"
                    "🔍 Monitoreando estado (recibirás notificación cuando esté online)\n\n"
                    "🎮 **Conéctate con:**\n"
                    f"`{ip}`"
                ),
                footer="Usa /minecraft_stop para detener el monitoreo"
            )
        else:
            embed = crear_embed_warning(
                "⚠️ Minecraft Iniciado (IP no detectada)",
                (
                    f"**Codespace:** `{codespace}`\n\n"
                    "✅ Servidor de Minecraft iniciado\n"
                    "⚠️ No se pudo detectar la IP automáticamente\n\n"
                    "Usa `/minecraft_status` en el Codespace para ver la IP"
                ),
                footer="Puede tardar unos minutos en estar completamente listo"
            )

        await msg.edit(embed=embed)
        await enviar_log_al_propietario(
            self.bot,
            codespace,
            f"Minecraft iniciado por <@{calling_id}>"
        )

    @app_commands.command(
        name="minecraft_stop",
        description="Detiene el monitoreo del servidor de Minecraft"
    )
    async def minecraft_stop(self, interaction: discord.Interaction):
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
                footer="d0ce3|tools v2"
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
        await interaction.response.defer()

        try:
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
            
            if "latency" in data:
                latency = data["latency"]
                embed.add_field(
                    name="📡 Latencia",
                    value=f"{latency}ms",
                    inline=True
                )
            
            embed.set_footer(text="Powered by mcstatus.io")
            
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
    
