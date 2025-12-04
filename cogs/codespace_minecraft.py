import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional

from utils.permissions import obtener_contexto_usuario, sesion_valida
from utils.codespace_wake import despertar_codespace_real, verificar_estado_codespace
from utils.embed_factory import (
    crear_embed_exito,
    crear_embed_error,
    crear_embed_info,
    crear_embed_warning,
)
from utils.notify import enviar_log_al_propietario
from utils.jsondb import safe_load, safe_save
from config import SESIONES_FILE


class CodespaceMinecraftCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitoreando = {}
        self.ultimo_estado = {}
        self.monitor_loop.start()

    def cog_unload(self):
        self.monitor_loop.cancel()

    @tasks.loop(minutes=1)
    async def monitor_loop(self):
        """Loop de monitoreo de servidores de Minecraft"""
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
                                f"**IP:** `{ip}`\n\nEl servidor de Minecraft está ahora **ONLINE** y aceptando conexiones.",
                                footer="Monitoreando cada 1 minuto"
                            )
                        else:
                            embed = crear_embed_warning(
                                "🔴 Servidor Offline",
                                f"**IP:** `{ip}`\n\nEl servidor de Minecraft está ahora **OFFLINE**.",
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
        """Obtiene la IP del servidor de Minecraft desde el webhook"""
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

    async def esperar_servidor_web(self, codespace_url: str, max_intentos: int = 40) -> bool:
        """Espera a que el servidor web del Codespace esté disponible"""
        for intento in range(max_intentos):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{codespace_url}/health",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            return True
            except:
                pass
            
            await asyncio.sleep(5)
        
        return False

    async def obtener_tunnel_url(self, codespace_url_nativa: str, max_intentos: int = 20) -> Optional[str]:
        for intento in range(max_intentos):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{codespace_url_nativa}/get_url",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            tunnel_url = data.get('tunnel_url')
                            if tunnel_url:
                                return tunnel_url
            except:
                pass
            
            await asyncio.sleep(3)
        
        return None

    @app_commands.command(
        name="minecraft_start",
        description="Inicia tu Codespace y ejecuta el servidor de Minecraft automáticamente!"
    )
    async def minecraft_start(self, interaction: discord.Interaction):
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

        token = sesion["token"]
        
        # Obtener URLs guardadas
        sesiones = safe_load(SESIONES_FILE)
        tunnel_url = sesiones.get(str(owner_id), {}).get("tunnel_url")
        codespace_url_nativa = sesiones.get(str(owner_id), {}).get("codespace_url")

        # VALIDACIÓN: Cloudflare Tunnel es OBLIGATORIO para Minecraft
        if not tunnel_url:
            embed = crear_embed_error(
                "❌ Cloudflare Tunnel No Configurado",
                (
                    "**Minecraft requiere Cloudflare Tunnel activo.**\n\n"
                    "El puerto 8080 nativo siempre queda privado, por eso usamos el túnel.\n\n"
                    "**Solución:**\n"
                    "1. Ve a tu Codespace manualmente\n"
                    "2. Asegúrate que `auto_webserver_setup` esté corriendo\n"
                    "3. Verifica que Cloudflare Tunnel esté activo\n"
                    "4. Usa `/actualizar_tunnel` para detectar la URL\n"
                    "5. Intenta `/minecraft_start` nuevamente"
                )
            )
            await interaction.followup.send(embed=embed)
            return
        
        print(f"🌐 Usando Cloudflare Tunnel: {tunnel_url}")

        embed = crear_embed_info(
            "🚀 Iniciando Sistema Completo",
            (
                f"**Codespace:** `{codespace}`\n"
                f"**Iniciado por:** <@{calling_id}>\n\n"
                "**Fase 1: Despertar Codespace (REAL)**\n"
                "⏳ Iniciando VM con requests HTTP...\n"
                "⏳ Esto puede tardar 1-3 minutos\n\n"
                f"🌐 Usando: Cloudflare Tunnel\n"
                "Esto despierta la VM."
            ),
            footer="Ten paciencia, estamos iniciando la VM completa"
        )
        msg = await interaction.followup.send(embed=embed)

        print(f"🚀 [Minecraft Start] Fase 1: Despertando Codespace '{codespace}'")
        print(f"🌐 [Minecraft Start] Cloudflare Tunnel: {tunnel_url}")
        
        # Usar SOLO Cloudflare Tunnel para despertar
        success, mensaje = await despertar_codespace_real(
            token=token,
            codespace_name=codespace,
            codespace_url=tunnel_url,  # SOLO tunnel, NO nativa
            max_intentos=15,
            timeout_inicial=240  # 4 minutos
        )

        if not success:
            embed = crear_embed_error(
                "❌ Error al Despertar Codespace",
                (
                    f"**Codespace:** `{codespace}`\n\n"
                    f"**Error:** {mensaje}\n\n"
                    "**Posibles causas:**\n"
                    "• El Codespace está tardando más de lo normal\n"
                    "• Problemas de conectividad con GitHub\n"
                    "• El Codespace requiere inicio manual\n\n"
                    "**Soluciones:**\n"
                    "1. Espera 2-3 minutos y usa `/status`\n"
                    "2. Inicia manualmente desde GitHub\n"
                    "3. Intenta de nuevo"
                )
            )
            await msg.edit(embed=embed)
            return

        print(f"✅ [Minecraft Start] Fase 1 completa: {mensaje}")

        # ============================================================
        # PASO 2: VERIFICAR QUE CLOUDFLARE TUNNEL SIGA ACTIVO
        # ============================================================
        embed = crear_embed_info(
            "🚀 Iniciando Sistema Completo",
            (
                f"**Codespace:** `{codespace}`\n\n"
                "**Fase 1: Despertar Codespace** ✅\n"
                f"└─ {mensaje}\n\n"
                "**Fase 2: Verificar Cloudflare Tunnel**\n"
                "⏳ Confirmando que el túnel siga activo...\n"
                f"🌐 `{tunnel_url[:50]}...`"
            ),
            footer="Cloudflare Tunnel bypasea el problema del puerto privado"
        )
        await msg.edit(embed=embed)

        print(f"🔍 [Minecraft Start] Fase 2: Verificando Cloudflare Tunnel...")
        
        # Verificar que el tunnel actual siga funcionando
        tunnel_activo = await self.esperar_servidor_web(tunnel_url, max_intentos=5)
        
        codespace_url = tunnel_url  # SIEMPRE usar el tunnel
        
        if not tunnel_activo:
            print(f"⚠️ [Minecraft Start] Tunnel guardado no responde, intentando detectar nuevo...")
            
            # Si el tunnel guardado no funciona, buscar uno nuevo
            # PERO solo si tenemos la URL nativa como fallback
            if codespace_url_nativa:
                nuevo_tunnel = await self.obtener_tunnel_url(codespace_url_nativa, max_intentos=15)
                
                if nuevo_tunnel:
                    codespace_url = nuevo_tunnel
                    # Guardar el nuevo tunnel
                    sesiones[str(owner_id)]["tunnel_url"] = nuevo_tunnel
                    safe_save(SESIONES_FILE, sesiones)
                    print(f"✅ [Minecraft Start] Nuevo Cloudflare Tunnel detectado: {nuevo_tunnel}")
                else:
                    embed = crear_embed_error(
                        "❌ Cloudflare Tunnel No Disponible",
                        (
                            "**El Cloudflare Tunnel no está respondiendo.**\n\n"
                            "✅ Codespace despierto\n"
                            "❌ Pero el túnel no está activo\n\n"
                            "**Solución:**\n"
                            "1. Ve a tu Codespace manualmente\n"
                            "2. Verifica que `auto_webserver_setup` esté corriendo\n"
                            "3. Verifica que Cloudflare Tunnel esté activo\n"
                            "4. Usa `/actualizar_tunnel` para detectar la nueva URL\n"
                            "5. Intenta `/minecraft_start` nuevamente"
                        )
                    )
                    await msg.edit(embed=embed)
                    return
            else:
                embed = crear_embed_error(
                    "❌ Cloudflare Tunnel No Disponible",
                    (
                        "El túnel no responde y no hay URL nativa configurada.\n\n"
                        "Usa `/actualizar_tunnel` para detectar la URL del túnel."
                    )
                )
                await msg.edit(embed=embed)
                return
        
        print(f"✅ [Minecraft Start] Cloudflare Tunnel activo: {codespace_url}")

        # ============================================================
        # PASO 3: VERIFICAR SERVIDOR WEB (Puerto 8080 vía Tunnel)
        # ============================================================
        embed = crear_embed_info(
            "🚀 Iniciando Sistema Completo",
            (
                f"**Codespace:** `{codespace}`\n\n"
                "**Fase 1: Despertar Codespace** ✅\n"
                "**Fase 2: Cloudflare Tunnel** ✅\n\n"
                "**Fase 3: Verificar Servidor Web**\n"
                "⏳ Esperando que el servidor web responda...\n"
                f"🌐 Conectando vía túnel a puerto 8080"
            ),
            footer="El túnel bypasea el problema del puerto privado"
        )
        await msg.edit(embed=embed)

        print(f"🔄 [Minecraft Start] Fase 3: Esperando servidor web en {codespace_url}")
        
        servidor_listo = await self.esperar_servidor_web(codespace_url, max_intentos=30)

        if not servidor_listo:
            embed = crear_embed_error(
                "❌ Servidor Web No Disponible",
                (
                    f"**Codespace:** `{codespace}`\n\n"
                    "✅ Codespace despierto\n"
                    "❌ Pero el servidor web (puerto 8080) no responde\n\n"
                    "**Posibles causas:**\n"
                    "• El puerto 8080 no está configurado como público\n"
                    "• auto_webserver_setup no se ejecutó\n"
                    "• El servidor web tardó más de 3 minutos\n\n"
                    "**Solución:**\n"
                    "1. Ve a tu Codespace manualmente\n"
                    "2. Ejecuta: `bash start_web_server.sh`\n"
                    "3. Configura el puerto 8080 como público\n"
                    "4. Intenta `/minecraft_start` nuevamente"
                )
            )
            await msg.edit(embed=embed)
            return

        print(f"✅ [Minecraft Start] Fase 3 completa: Servidor web respondiendo")

        # ============================================================
        # PASO 4: OBTENER TOKEN DE AUTENTICACIÓN
        # ============================================================
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{codespace_url}/get_token",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    token_data = await resp.json()
                    auth_token = token_data['token']
            
            print(f"✅ [Minecraft Start] Token de autenticación obtenido")
        except Exception as e:
            embed = crear_embed_error(
                "❌ Error Obteniendo Token",
                (
                    f"No se pudo obtener el token de autenticación:\n"
                    f"```{str(e)}```\n\n"
                    "Verifica que el servidor web esté configurado correctamente."
                )
            )
            await msg.edit(embed=embed)
            return

        # ============================================================
        # PASO 5: INICIAR MINECRAFT
        # ============================================================
        embed = crear_embed_info(
            "🚀 Iniciando Sistema Completo",
            (
                f"**Codespace:** `{codespace}`\n\n"
                "**Fase 1: Despertar Codespace** ✅\n"
                "**Fase 2: Detectar Tunnel** ✅\n"
                "**Fase 3: Servidor Web** ✅\n"
                "**Fase 4: Token** ✅\n\n"
                "**Fase 5: Minecraft**\n"
                "⏳ Ejecutando msx.py...\n"
                "   (iniciando servidor de Minecraft)"
            ),
            footer="Último paso - espera ~1 minuto"
        )
        await msg.edit(embed=embed)

        print(f"🎮 [Minecraft Start] Fase 5: Iniciando Minecraft...")
        
        resultado = await self.llamar_webhook_minecraft(codespace_url, auth_token)

        if not resultado.get("success"):
            embed = crear_embed_error(
                "❌ Error al Iniciar Minecraft",
                (
                    f"**Error:** {resultado.get('error')}\n\n"
                    "💡 **Posibles causas:**\n"
                    "  • El servidor web está activo pero msx.py falló\n"
                    "  • Token de autenticación inválido\n"
                    "  • msx.py no encontrado o con errores\n\n"
                    "Verifica los logs en tu Codespace."
                )
            )
            await msg.edit(embed=embed)
            return

        print(f"✅ [Minecraft Start] Fase 5 completa: Minecraft iniciado")

        # ============================================================
        # PASO 6: OBTENER IP Y CONFIGURAR MONITOREO
        # ============================================================
        print(f"🔍 [Minecraft Start] Fase 6: Obteniendo IP del servidor...")
        await asyncio.sleep(30)

        ip = await self.obtener_ip_desde_webhook(codespace_url, auth_token)

        if not ip:
            data = resultado.get("data", {})
            estado = data.get("estado", {})
            ip = estado.get("ip")

        if ip:
            self.monitoreando[str(owner_id)] = {
                "ip": ip,
                "channel_id": interaction.channel_id
            }
            self.ultimo_estado[str(owner_id)] = False

            conexion_info = "🌐 Cloudflare Tunnel" if 'trycloudflare.com' in codespace_url else "🔗 Codespace Nativo"

            embed = crear_embed_exito(
                "✅ Sistema Completamente Iniciado",
                (
                    f"**Codespace:** `{codespace}`\n"
                    f"**IP del Servidor:** `{ip}`\n"
                    f"**Conexión:** {conexion_info}\n\n"
                    "✅ **Fase 1:** Codespace despierto\n"
                    "✅ **Fase 2:** Cloudflare Tunnel detectado\n"
                    "✅ **Fase 3:** Servidor web activo\n"
                    "✅ **Fase 4:** Autenticación OK\n"
                    "✅ **Fase 5:** Minecraft iniciado\n"
                    "✅ **Fase 6:** IP obtenida\n\n"
                    "🔍 Monitoreando estado (recibirás notificación cuando esté online)\n\n"
                    "🎮 **Conéctate con:**\n"
                    f"```{ip}```"
                ),
                footer="Usa /minecraft_stop para detener el monitoreo"
            )
            print(f"✅ [Minecraft Start] COMPLETADO - IP: {ip}")
        else:
            embed = crear_embed_warning(
                "⚠️ Minecraft Iniciado (IP no detectada)",
                (
                    f"**Codespace:** `{codespace}`\n\n"
                    "✅ Codespace despierto\n"
                    "✅ Minecraft iniciado\n"
                    "⚠️ No se pudo detectar la IP automáticamente\n\n"
                    "**Posibles razones:**\n"
                    "• El servidor está iniciando aún\n"
                    "• El puerto no está configurado\n"
                    "• Problemas con la detección de IP\n\n"
                    "Usa `/minecraft_status` para verificar manualmente."
                ),
                footer="Puede tardar 2-3 minutos en estar completamente listo"
            )
            print(f"⚠️ [Minecraft Start] COMPLETADO pero sin IP detectada")

        await msg.edit(embed=embed)
        await enviar_log_al_propietario(
            self.bot,
            codespace,
            (
                f"✅ Sistema completo iniciado por <@{calling_id}>\n\n"
                f"Detalles técnicos:\n"
                f"• {mensaje}\n"
                f"• Conexión: {'Cloudflare Tunnel' if 'trycloudflare.com' in codespace_url else 'Nativa'}\n"
                f"• IP: {ip if ip else 'No detectada'}"
            )
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
                footer="d0ce3|tools"
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