import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = os.getenv('DISCORD_GUILD_ID')

async def sync_commands():
    """Script para sincronizar o limpiar comandos"""
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = discord.app_commands.CommandTree(client)

    @client.event
    async def on_ready():
        print(f"✅ Conectado como {client.user}")

        # Menú de opciones
        print("\n" + "=" * 50)
        print("Opciones de sincronización:")
        print("=" * 50)
        print("1. Sincronizar comandos en servidor de pruebas")
        print("2. Sincronizar comandos globalmente")
        print("3. Limpiar comandos del servidor de pruebas")
        print("4. Limpiar comandos globales")
        print("5. Salir")
        print("=" * 50)

        opcion = input("\nSelecciona una opción (1-5): ")

        try:
            if opcion == "1":
                if GUILD_ID:
                    guild = discord.Object(id=int(GUILD_ID))
                    await tree.sync(guild=guild)
                    print(f"✅ Comandos sincronizados en servidor {GUILD_ID}")
                else:
                    print("❌ DISCORD_GUILD_ID no configurado")

            elif opcion == "2":
                await tree.sync()
                print("✅ Comandos sincronizados globalmente")

            elif opcion == "3":
                if GUILD_ID:
                    guild = discord.Object(id=int(GUILD_ID))
                    tree.clear_commands(guild=guild)
                    await tree.sync(guild=guild)
                    print(f"✅ Comandos limpiados del servidor {GUILD_ID}")
                else:
                    print("❌ DISCORD_GUILD_ID no configurado")

            elif opcion == "4":
                tree.clear_commands(guild=None)
                await tree.sync()
                print("✅ Comandos globales limpiados")

            elif opcion == "5":
                print("👋 Saliendo...")

            else:
                print("❌ Opción inválida")
        
        except Exception as e:
            print(f"❌ Error: {e}")

        await client.close()

    await client.start(TOKEN)

if __name__ == "__main__":
    print("🔄 Script de sincronización de comandos")
    asyncio.run(sync_commands())
