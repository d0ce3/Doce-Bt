import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List, Optional
from utils.jsondb import safe_load, safe_save
from config import SESIONES_FILE, DATA_DIR

logger = logging.getLogger(__name__)

CODESPACES_FILE = f'{DATA_DIR}/codespaces_monitored.json'


class CodespaceEventConsumer:
    """
    Consumer que pollea eventos desde el Codespace
    Adaptado de d0ce3-Addons/discord_consumer_example.py
    """
    
    def __init__(self, bot, poll_interval: int = 30):
        self.bot = bot
        self.poll_interval = poll_interval
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.stats = {
            'total_polled': 0,
            'total_processed': 0,
            'total_failed': 0,
            'last_poll': None
        }
    
    def get_codespace_urls(self) -> List[str]:
        """Obtiene las URLs de Codespaces desde sesiones"""
        sesiones = safe_load(SESIONES_FILE)
        urls = []
        
        for uid, data in sesiones.items():
            codespace_url = data.get('codespace_url')
            if codespace_url:
                # Asegurar formato correcto
                if not codespace_url.startswith('http'):
                    codespace_url = f'https://{codespace_url}'
                if not codespace_url.endswith(':8080'):
                    codespace_url = codespace_url.rstrip('/') + ':8080'
                urls.append(codespace_url)
        
        return list(set(urls))  # Eliminar duplicados
    
    async def start(self):
        """Inicia el consumer"""
        if self.running:
            logger.warning("Consumer ya está corriendo")
            return
        
        self.running = True
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        
        logger.info(f"🚀 Consumer iniciado - polling cada {self.poll_interval}s")
        
        asyncio.create_task(self._polling_loop())
    
    async def stop(self):
        """Detiene el consumer"""
        self.running = False
        
        if self.session:
            await self.session.close()
            self.session = None
        
        logger.info("⏹️ Consumer detenido")
    
    async def _polling_loop(self):
        """Loop principal de polling"""
        while self.running:
            try:
                codespace_urls = self.get_codespace_urls()
                if codespace_urls:
                    await self._poll_all_codespaces(codespace_urls)
                self.stats['last_poll'] = datetime.now().isoformat()
            except Exception as e:
                logger.error(f"❌ Error en polling loop: {e}", exc_info=True)
            
            await asyncio.sleep(self.poll_interval)
    
    async def _poll_all_codespaces(self, codespace_urls: List[str]):
        """Pollea todos los Codespaces configurados"""
        tasks = [
            self._poll_codespace(url)
            for url in codespace_urls
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _poll_codespace(self, codespace_url: str):
        """Pollea un Codespace específico"""
        try:
            events_url = f"{codespace_url}/discord/events"
            
            async with self.session.get(events_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get('success'):
                        events = data.get('events', [])
                        
                        if events:
                            logger.info(f"📦 {len(events)} evento(s) desde {codespace_url}")
                            
                            for event in events:
                                await self._process_event(event, codespace_url)
                        
                        self.stats['total_polled'] += len(events)
                    else:
                        logger.warning(f"⚠️  Error en respuesta de {codespace_url}: {data.get('error')}")
                
                elif response.status != 404:  # 404 es normal si no hay eventos
                    logger.warning(f"⚠️  HTTP {response.status} desde {codespace_url}")
        
        except aiohttp.ClientError:
            pass  # Conexión fallida, normal si el codespace está apagado
        except Exception as e:
            logger.error(f"❌ Error polling {codespace_url}: {e}")
    
    async def _process_event(self, event: Dict, codespace_url: str):
        """Procesa un evento individual"""
        event_id = event['id']
        event_type = event['event_type']
        user_id = event['user_id']
        payload = event['payload']
        
        try:
            logger.info(f"🔄 Procesando evento #{event_id}: {event_type}")
            
            user = await self.bot.fetch_user(int(user_id))
            if not user:
                logger.warning(f"⚠️  Usuario {user_id} no encontrado")
                await self._mark_failed(event_id, codespace_url, "Usuario no encontrado")
                return
            
            if event_type == 'backup_error':
                await self._handle_backup_error(user, payload)
            
            elif event_type == 'backup_success':
                await self._handle_backup_success(user, payload)
            
            elif event_type == 'minecraft_status':
                await self._handle_minecraft_status(user, payload)
            
            elif event_type == 'codespace_status':
                await self._handle_codespace_status(user, payload)
            
            else:
                logger.warning(f"⚠️  Tipo de evento desconocido: {event_type}")
                await self._mark_failed(event_id, codespace_url, f"Tipo desconocido: {event_type}")
                return
            
            await self._mark_processed(event_id, codespace_url)
            self.stats['total_processed'] += 1
            logger.info(f"✅ Evento #{event_id} procesado")
        
        except Exception as e:
            logger.error(f"❌ Error procesando evento #{event_id}: {e}", exc_info=True)
            await self._mark_failed(event_id, codespace_url, str(e))
            self.stats['total_failed'] += 1
    
    async def _handle_backup_error(self, user, payload):
        """Maneja errores de backup"""
        error_type = payload.get('error_type', 'general')
        error_message = payload.get('error_message', 'Error desconocido')
        codespace_name = payload.get('codespace_name', 'Desconocido')
        
        embed = discord.Embed(
            title="❌ Error en Backup",
            description=f'```\n{error_message}\n```',
            color=0xFF0000,
            timestamp=datetime.now()
        )
        embed.add_field(name='Codespace', value=codespace_name, inline=True)
        embed.add_field(name='Tipo', value=error_type, inline=True)
        embed.set_footer(text='d0ce3|tools • Backup Monitor')
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"No se pudo enviar DM a {user.id}")
    
    async def _handle_backup_success(self, user, payload):
        """Maneja backups exitosos"""
        backup_file = payload.get('backup_file', 'Desconocido')
        size_mb = payload.get('size_mb', 0)
        duration = payload.get('duration_seconds', 0)
        codespace_name = payload.get('codespace_name', 'Desconocido')
        
        embed = discord.Embed(
            title='✅ Backup Completado',
            color=0x00FF00,
            timestamp=datetime.now()
        )
        embed.add_field(name='Archivo', value=f'`{backup_file}`', inline=False)
        embed.add_field(name='Tamaño', value=f'{size_mb:.2f} MB', inline=True)
        embed.add_field(name='Duración', value=f'{duration:.1f}s', inline=True)
        embed.add_field(name='Codespace', value=codespace_name, inline=True)
        embed.set_footer(text='d0ce3|tools • Backup Monitor')
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"No se pudo enviar DM a {user.id}")
    
    async def _handle_minecraft_status(self, user, payload):
        """Maneja cambios de estado de Minecraft"""
        status = payload.get('status', 'unknown')
        ip = payload.get('ip')
        port = payload.get('port', 25565)
        players = payload.get('players_online', 0)
        
        status_emoji = {
            'online': '✅',
            'offline': '❌',
            'starting': '🔄',
            'stopping': '⏹️'
        }.get(status, '❓')
        
        color = 0x00FF00 if status == 'online' else 0xFF0000
        
        embed = discord.Embed(
            title=f'{status_emoji} Servidor Minecraft - {status.upper()}',
            color=color,
            timestamp=datetime.now()
        )
        
        if ip:
            server_address = f'{ip}:{port}' if port != 25565 else ip
            embed.add_field(name='IP', value=f'`{server_address}`', inline=True)
        
        if status == 'online':
            embed.add_field(name='Jugadores', value=str(players), inline=True)
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"No se pudo enviar DM a {user.id}")
    
    async def _handle_codespace_status(self, user, payload):
        """Maneja cambios de estado del Codespace"""
        action = payload.get('action', 'unknown')
        details = payload.get('details', {})
        codespace_name = payload.get('codespace_name', 'Desconocido')
        
        action_emoji = {
            'started': '▶️',
            'stopped': '⏹️',
            'error': '❌'
        }.get(action, '🔔')
        
        color = 0x00FF00 if action == 'started' else 0xFF0000
        
        embed = discord.Embed(
            title=f'{action_emoji} Codespace {action.upper()}',
            description=f'**{codespace_name}**',
            color=color,
            timestamp=datetime.now()
        )
        
        if details:
            for key, value in details.items():
                embed.add_field(
                    name=key.replace('_', ' ').title(),
                    value=str(value),
                    inline=True
                )
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"No se pudo enviar DM a {user.id}")
    
    async def _mark_processed(self, event_id: int, codespace_url: str):
        """Marca un evento como procesado"""
        try:
            url = f"{codespace_url}/discord/events/{event_id}/processed"
            async with self.session.post(url) as response:
                if response.status != 200:
                    logger.warning(f"⚠️  Error marcando evento #{event_id} como procesado")
        except Exception as e:
            logger.error(f"❌ Error marcando procesado #{event_id}: {e}")
    
    async def _mark_failed(self, event_id: int, codespace_url: str, error_message: str):
        """Marca un evento como fallido"""
        try:
            url = f"{codespace_url}/discord/events/{event_id}/failed"
            async with self.session.post(url, json={'error_message': error_message}) as response:
                if response.status != 200:
                    logger.warning(f"⚠️  Error marcando evento #{event_id} como fallido")
        except Exception as e:
            logger.error(f"❌ Error marcando fallido #{event_id}: {e}")
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas del consumer"""
        return self.stats.copy()


class AddonIntegration(commands.Cog):
    """
    Integración con d0ce3-Addons
    - Monitoreo de eventos desde Codespaces
    - Sistema de colas para backups y operaciones
    - Notificaciones automáticas
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.consumer: Optional[CodespaceEventConsumer] = None
    
    async def cog_load(self):
        """Se ejecuta cuando el cog se carga"""
        # Iniciar el consumer automáticamente
        self.consumer = CodespaceEventConsumer(self.bot, poll_interval=30)
        await self.consumer.start()
        logger.info("✅ Consumer de eventos iniciado")
    
    async def cog_unload(self):
        """Se ejecuta cuando el cog se descarga"""
        if self.consumer:
            await self.consumer.stop()
            logger.info("⏹️ Consumer de eventos detenido")
    
    @app_commands.command(
        name="addon_stats",
        description="Ver estadísticas del sistema de eventos"
    )
    async def addon_stats(self, interaction: discord.Interaction):
        """Muestra estadísticas del consumer de eventos"""
        if not self.consumer:
            await interaction.response.send_message(
                "❌ El consumer no está activo",
                ephemeral=True
            )
            return
        
        stats = self.consumer.get_stats()
        codespaces = self.consumer.get_codespace_urls()
        
        embed = discord.Embed(
            title="📊 Estadísticas del Sistema de Eventos",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📦 Eventos Polleados",
            value=str(stats['total_polled']),
            inline=True
        )
        embed.add_field(
            name="✅ Procesados",
            value=str(stats['total_processed']),
            inline=True
        )
        embed.add_field(
            name="❌ Fallidos",
            value=str(stats['total_failed']),
            inline=True
        )
        
        if stats['last_poll']:
            try:
                last_poll = datetime.fromisoformat(stats['last_poll'])
                embed.add_field(
                    name="🕐 Último Polling",
                    value=f"<t:{int(last_poll.timestamp())}:R>",
                    inline=False
                )
            except:
                pass
        
        embed.add_field(
            name="🖥️ Codespaces Monitoreados",
            value=f"{len(codespaces)} activo(s)",
            inline=False
        )
        
        if codespaces:
            embed.add_field(
                name="URLs",
                value="\n".join([f"• `{url}`" for url in codespaces[:5]]),
                inline=False
            )
        
        embed.set_footer(text="d0ce3|tools • Addon Integration")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AddonIntegration(bot))
