import discord
from datetime import datetime

def crear_embed_exito(titulo, descripcion, footer=None):
    """Crea un embed de éxito (verde)"""
    embed = discord.Embed(
        title=titulo,
        description=descripcion,
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    if footer:
        embed.set_footer(text=footer)
    return embed

def crear_embed_error(titulo, descripcion, footer=None):
    """Crea un embed de error (rojo)"""
    embed = discord.Embed(
        title=titulo,
        description=descripcion,
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    if footer:
        embed.set_footer(text=footer)
    return embed

def crear_embed_info(titulo, descripcion, footer=None):
    """Crea un embed informativo (azul)"""
    embed = discord.Embed(
        title=titulo,
        description=descripcion,
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    if footer:
        embed.set_footer(text=footer)
    return embed

def crear_embed_warning(titulo, descripcion, footer=None):
    """Crea un embed de advertencia (naranja)"""
    embed = discord.Embed(
        title=titulo,
        description=descripcion,
        color=discord.Color.orange(),
        timestamp=datetime.now()
    )
    if footer:
        embed.set_footer(text=footer)
    return embed
