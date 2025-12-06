import discord
from discord import app_commands
from discord.ext import commands
from utils.database import get_db

class NotificacionesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="notificaciones")
    @app_commands.describe(
        modo="Dónde recibir notificaciones del tunnel",
        canal="Canal específico (solo si modo es 'canal')"
    )
    @app_commands.choices(modo=[
        app_commands.Choice(name="🔕 Desactivadas", value="disabled"),
        app_commands.Choice(name="💬 DM Privado", value="dm"),
        app_commands.Choice(name="📢 Canal de Discord", value="channel")
    ])
    async def configurar_notificaciones(
        self,
        interaction: discord.Interaction,
        modo: app_commands.Choice[str],
        canal: discord.TextChannel = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        user_id = str(interaction.user.id)
        db = get_db()
        sesion = db.get_sesion(user_id)
        
        if not sesion:
            await interaction.followup.send(
                "❌ No estás vinculado. Usa `/setup` primero.",
                ephemeral=True
            )
            return
        
        modo_valor = modo.value
        
        if modo_valor == "channel":
            if not canal:
                await interaction.followup.send(
                    "❌ Debes especificar un canal cuando eliges modo 'Canal de Discord'",
                    ephemeral=True
                )
                return
            
            perms = canal.permissions_for(interaction.guild.me)
            if not perms.send_messages:
                await interaction.followup.send(
                    f"❌ No tengo permisos para enviar mensajes en {canal.mention}",
                    ephemeral=True
                )
                return
            
            sesion["notification_mode"] = "channel"
            sesion["notification_channel_id"] = str(canal.id)
            sesion["notification_guild_id"] = str(interaction.guild.id)
            
            db.save_sesion(user_id, sesion)
            
            embed = discord.Embed(
                title="✅ Notificaciones Configuradas",
                description=f"Recibirás notificaciones en {canal.mention}",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            test_embed = discord.Embed(
                title="🔔 Notificaciones Activadas",
                description=(
                    f"{interaction.user.mention} recibirá aquí las notificaciones de tunnel.\n\n"
                    "Esto incluye:\n"
                    "• Cuando el tunnel de Cloudflare esté listo\n"
                    "• IP del servidor Minecraft\n"
                    "• IP de VoiceChat (si aplica)"
                ),
                color=discord.Color.blue()
            )
            test_embed.set_footer(text="Puedes cambiar esto con /notificaciones")
            
            await canal.send(embed=test_embed)
        
        elif modo_valor == "dm":
            sesion["notification_mode"] = "dm"
            sesion["notification_channel_id"] = None
            sesion["notification_guild_id"] = None
            
            db.save_sesion(user_id, sesion)
            
            embed = discord.Embed(
                title="✅ Notificaciones Configuradas",
                description="Recibirás notificaciones por **DM privado**",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        elif modo_valor == "disabled":
            sesion["notification_mode"] = "disabled"
            sesion["notification_channel_id"] = None
            sesion["notification_guild_id"] = None
            
            db.save_sesion(user_id, sesion)
            
            embed = discord.Embed(
                title="🔕 Notificaciones Desactivadas",
                description=(
                    "Ya no recibirás notificaciones automáticas.\n\n"
                    "Puedes ver el estado del tunnel con:\n"
                    "• `/status` - Estado del Codespace\n"
                    "• `/minecraft_info` - Info completa del servidor"
                ),
                color=discord.Color.orange()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="ver_notificaciones")
    async def ver_configuracion_notificaciones(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        user_id = str(interaction.user.id)
        db = get_db()
        sesion = db.get_sesion(user_id)
        
        if not sesion:
            await interaction.followup.send(
                "❌ No estás vinculado. Usa `/setup` primero.",
                ephemeral=True
            )
            return
        
        notification_mode = sesion.get("notification_mode", "dm")
        
        if notification_mode == "disabled":
            modo_texto = "🔕 Desactivadas"
            descripcion = "No recibes notificaciones automáticas"
        elif notification_mode == "channel":
            channel_id = sesion.get("notification_channel_id")
            if channel_id:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    modo_texto = f"📢 Canal: {channel.mention}"
                    descripcion = "Las notificaciones se envían a este canal"
                else:
                    modo_texto = "⚠️ Canal no encontrado"
                    descripcion = "El canal configurado ya no existe. Configura uno nuevo."
            else:
                modo_texto = "⚠️ No configurado"
                descripcion = "Modo canal seleccionado pero sin canal específico"
        else:
            modo_texto = "💬 DM Privado (predeterminado)"
            descripcion = "Recibes notificaciones por mensaje privado"
        
        embed = discord.Embed(
            title="🔔 Configuración de Notificaciones",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Modo Actual",
            value=modo_texto,
            inline=False
        )
        
        embed.add_field(
            name="Descripción",
            value=descripcion,
            inline=False
        )
        
        embed.add_field(
            name="Cambiar Configuración",
            value="Usa `/notificaciones` para cambiar dónde recibes las notificaciones",
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(NotificacionesCog(bot))