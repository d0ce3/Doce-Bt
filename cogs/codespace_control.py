import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
from utils.database import get_db

class CodespaceControl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="start")
    async def start_codespace(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        db = get_db()
        sesion = db.get_sesion(user_id)
        
        if not sesion:
            await interaction.followup.send("❌ No estás vinculado. Usa `/setup` primero.", ephemeral=True)
            return
        
        try:
            github_token = sesion["token"]
            codespace_name = sesion["codespace"]
            
            if not sesion.get("auto_configured"):
                embed_warning = discord.Embed(
                    title="⚠️ Codespace No Configurado",
                    description=(
                        "Tu Codespace no tiene auto-inicio configurado.\n\n"
                        "Usa `/setup` de nuevo para configuración automática."
                    ),
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed_warning, ephemeral=True)
                return
            
            embed_starting = discord.Embed(
                title="⏳ Iniciando Codespace...",
                description=(
                    f"**Codespace:** `{codespace_name}`\n\n"
                    "Los scripts se ejecutarán automáticamente.\n"
                    "Espera ~60-90 segundos..."
                ),
                color=discord.Color.yellow()
            )
            msg = await interaction.followup.send(embed=embed_starting)
            
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://api.github.com/user/codespaces/{codespace_name}/start",
                    headers=headers
                ) as resp:
                    if resp.status not in [200, 202]:
                        raise Exception(f"Error iniciando Codespace: {resp.status}")
            
            await asyncio.sleep(60)
            
            sesion_updated = db.get_sesion(user_id)
            tunnel_url = sesion_updated.get("tunnel_url")
            
            if tunnel_url:
                embed_success = discord.Embed(
                    title="✅ Codespace Iniciado y Configurado",
                    description=(
                        f"**Codespace:** `{codespace_name}`\n"
                        f"**Tunnel URL:** `{tunnel_url}`\n\n"
                        "✅ Los scripts se ejecutaron automáticamente.\n"
                        "Usa `/minecraft_info` para ver la información completa."
                    ),
                    color=discord.Color.green()
                )
            else:
                embed_success = discord.Embed(
                    title="✅ Codespace Iniciado",
                    description=(
                        f"**Codespace:** `{codespace_name}`\n\n"
                        "⏳ Esperando notificación del tunnel...\n"
                        "Si no recibes notificación en ~2 minutos, revisa los logs."
                    ),
                    color=discord.Color.orange()
                )
            
            await msg.edit(embed=embed_success)
            
        except Exception as e:
            embed_error = discord.Embed(
                title="❌ Error",
                description=f"No se pudo iniciar el Codespace:\n```{e}```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed_error, ephemeral=True)
    
    @app_commands.command(name="stop")
    async def stop_codespace(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        db = get_db()
        sesion = db.get_sesion(user_id)
        
        if not sesion:
            await interaction.followup.send("❌ No estás vinculado", ephemeral=True)
            return
        
        try:
            github_token = sesion["token"]
            codespace_name = sesion["codespace"]
            
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://api.github.com/user/codespaces/{codespace_name}/stop",
                    headers=headers
                ) as resp:
                    if resp.status in [200, 202]:
                        embed = discord.Embed(
                            title="✅ Codespace Detenido",
                            description=f"**Codespace:** `{codespace_name}`",
                            color=discord.Color.green()
                        )
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send(f"❌ Error deteniendo Codespace (HTTP {resp.status})", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)
    
    @app_commands.command(name="status")
    async def codespace_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        db = get_db()
        sesion = db.get_sesion(user_id)
        
        if not sesion:
            await interaction.followup.send("❌ No estás vinculado", ephemeral=True)
            return
        
        try:
            github_token = sesion["token"]
            codespace_name = sesion["codespace"]
            
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.github.com/user/codespaces/{codespace_name}",
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        state = data.get("state", "Unknown")
                        
                        state_emoji = {
                            "Available": "🟢",
                            "Unavailable": "🔴",
                            "Starting": "🟡",
                            "Stopped": "⚫"
                        }.get(state, "⚪")
                        
                        embed = discord.Embed(
                            title=f"{state_emoji} Estado del Codespace",
                            description=(
                                f"**Codespace:** `{codespace_name}`\n"
                                f"**Estado:** `{state}`\n"
                                f"**Repositorio:** `{sesion.get('repo_full_name')}`"
                            ),
                            color=discord.Color.blue()
                        )
                        
                        if sesion.get("tunnel_url"):
                            embed.add_field(
                                name="🌐 Tunnel",
                                value=f"`{sesion['tunnel_url']}`",
                                inline=False
                            )
                        
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send(f"❌ Error obteniendo estado (HTTP {resp.status})", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CodespaceControl(bot))