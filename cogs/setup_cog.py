import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import base64
import json
from datetime import datetime
from utils.database import get_db
from config import RENDER_EXTERNAL_URL

class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="setup")
    async def setup_unified(self, interaction: discord.Interaction, github_token: str):
        await interaction.response.defer(ephemeral=True)
        
        user_id = str(interaction.user.id)
        db = get_db()
        
        try:
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.github.com/user", headers=headers) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            "❌ Token inválido o sin permisos suficientes.\n"
                            "Asegúrate de que tenga los scopes: `repo`, `codespace`, `user`",
                            ephemeral=True
                        )
                        return
                    
                    user_data = await resp.json()
                    github_username = user_data["login"]
                    github_id = str(user_data["id"])
                
                async with session.get("https://api.github.com/user/codespaces", headers=headers) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            "❌ No se pudieron obtener tus Codespaces.\n"
                            "Verifica que el token tenga el scope `codespace`.",
                            ephemeral=True
                        )
                        return
                    
                    codespaces_data = await resp.json()
                    codespaces = codespaces_data.get("codespaces", [])
                    
                    if not codespaces:
                        await interaction.followup.send(
                            "⚠️ No tienes Codespaces creados.\n"
                            "Crea uno primero en GitHub y vuelve a intentar.",
                            ephemeral=True
                        )
                        return
                    
                    codespace = codespaces[0]
                    codespace_name = codespace["name"]
                    repo_full_name = codespace["repository"]["full_name"]
                    repo_name = codespace["repository"]["name"]
            
            print(f"✅ Vinculando usuario {user_id} ({github_username})")
            
            db.save_sesion(user_id, {
                "github_username": github_username,
                "github_id": github_id,
                "token": github_token,
                "codespace": codespace_name,
                "repo_name": repo_name,
                "repo_full_name": repo_full_name,
                "vinculado_at": datetime.now().isoformat()
            })
            
            db.save_vinculacion(user_id, github_username)
            
            embed_config = discord.Embed(
                title="⚙️ Configurando Codespace Automáticamente...",
                description=(
                    f"**GitHub:** `{github_username}`\n"
                    f"**Repositorio:** `{repo_full_name}`\n"
                    f"**Codespace:** `{codespace_name}`\n\n"
                    "Creando archivos de configuración..."
                ),
                color=discord.Color.yellow()
            )
            msg = await interaction.followup.send(embed=embed_config, ephemeral=True)
            
            needs_devcontainer = await self._check_needs_devcontainer(github_token, repo_full_name)
            
            devcontainer_result = "exists"
            if needs_devcontainer:
                devcontainer_result = await self._create_devcontainer(github_token, repo_full_name, user_id)
            
            startup_result = await self._create_startup(github_token, repo_full_name, user_id)
            
            sesion = db.get_sesion(user_id)
            sesion["auto_configured"] = True
            sesion["devcontainer_created"] = (devcontainer_result == True)
            sesion["startup_created"] = (startup_result == True)
            sesion["configured_at"] = datetime.now().isoformat()
            db.save_sesion(user_id, sesion)
            
            print(f"✅ Usuario {user_id} configurado completamente")
            
            status_devcontainer = "✅ Creado" if devcontainer_result == True else ("ℹ️ Ya existía" if devcontainer_result == "exists" else "⚠️ Error")
            status_startup = "✅ Creado/Actualizado" if startup_result else "⚠️ Error"
            
            embed_done = discord.Embed(
                title="✅ Configuración Completa",
                description=(
                    f"**GitHub:** `{github_username}`\n"
                    f"**Repositorio:** `{repo_full_name}`\n"
                    f"**Codespace:** `{codespace_name}`\n\n"
                ),
                color=discord.Color.green()
            )
            
            embed_done.add_field(
                name="📁 Archivos Configurados",
                value=(
                    f"{status_devcontainer} `.devcontainer/devcontainer.json`\n"
                    f"{status_startup} `startup.sh`"
                ),
                inline=False
            )
            
            embed_done.add_field(
                name="🚀 Próximos Pasos",
                value=(
                    "**1. Reconstruir Codespace** (solo la primera vez):\n"
                    f"   → https://github.com/{repo_full_name}\n"
                    "   → Code → Codespaces → ... → Rebuild Container\n\n"
                    "**2. O usa `/start`** directamente\n"
                    "   → El bot iniciará tu Codespace automáticamente\n\n"
                    "**3. Recibe notificación**\n"
                    "   → Te enviaré un DM con la IP del tunnel cuando esté listo"
                ),
                inline=False
            )
            
            embed_done.set_footer(text="💡 Ahora todo se ejecuta automáticamente al iniciar tu Codespace")
            
            await msg.edit(embed=embed_done)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error durante la configuración:\n```{e}```\n\nIntenta nuevamente o contacta al administrador.", ephemeral=True)
    
    async def _check_needs_devcontainer(self, github_token: str, repo_full_name: str) -> bool:
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.github.com/repos/{repo_full_name}/contents/.devcontainer/devcontainer.json",
                headers=headers
            ) as resp:
                if resp.status == 404:
                    return True
                elif resp.status == 200:
                    data = await resp.json()
                    content = base64.b64decode(data["content"]).decode()
                    
                    try:
                        config = json.loads(content)
                        if "postStartCommand" not in config:
                            print(f"⚠️  devcontainer.json existe pero sin postStartCommand")
                            return True
                        print(f"ℹ️  devcontainer.json ya existe y está configurado")
                        return False
                    except:
                        return True
                else:
                    return True
    
    async def _create_devcontainer(self, github_token: str, repo_full_name: str, discord_user_id: str) -> bool:
        print(f"📝 Creando devcontainer.json para {repo_full_name}")
        
        devcontainer_config = {
            "name": "Minecraft Server Codespace (Auto-configured by Doce-Bt)",
            "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
            "postStartCommand": "bash ${containerWorkspaceFolder}/startup.sh",
            "forwardPorts": [25565, 24454, 8080],
            "portsAttributes": {
                "25565": {"label": "Minecraft Server", "onAutoForward": "notify"},
                "24454": {"label": "SimpleVoiceChat (UDP)", "onAutoForward": "silent"},
                "8080": {"label": "Web Server + Cloudflare Tunnel", "onAutoForward": "silent"}
            },
            "containerEnv": {
                "DISCORD_USER_ID": discord_user_id,
                "BOT_WEBHOOK_URL": f"{RENDER_EXTERNAL_URL}/webhook/tunnel_notify",
                "MINECRAFT_PORT": "25565",
                "VOICECHAT_PORT": "24454",
                "AUTO_START": "true"
            },
            "features": {
                "ghcr.io/devcontainers/features/python:1": {"version": "3.11"},
                "ghcr.io/devcontainers/features/github-cli:1": {}
            },
            "customizations": {
                "vscode": {
                    "extensions": ["ms-python.python", "ms-python.vscode-pylance"],
                    "settings": {
                        "python.defaultInterpreterPath": "/usr/local/bin/python",
                        "terminal.integrated.defaultProfile.linux": "bash"
                    }
                }
            },
            "postCreateCommand": "pip install -r requirements.txt || true"
        }
        
        content_str = json.dumps(devcontainer_config, indent=2)
        content_base64 = base64.b64encode(content_str.encode()).decode()
        
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                existing_sha = None
                async with session.get(
                    f"https://api.github.com/repos/{repo_full_name}/contents/.devcontainer/devcontainer.json",
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        existing_sha = data.get("sha")
                        print(f"ℹ️  Actualizando devcontainer.json existente")
                
                payload = {
                    "message": "🤖 Auto-configure Codespace by Doce-Bt",
                    "content": content_base64,
                    "branch": "main"
                }
                
                if existing_sha:
                    payload["sha"] = existing_sha
                
                async with session.put(
                    f"https://api.github.com/repos/{repo_full_name}/contents/.devcontainer/devcontainer.json",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status in [200, 201]:
                        print(f"✅ devcontainer.json creado/actualizado")
                        return True
                    else:
                        error_data = await resp.json()
                        print(f"❌ Error creando devcontainer.json: {error_data}")
                        return False
        except Exception as e:
            print(f"❌ Excepción creando devcontainer.json: {e}")
            return False
    
    async def _create_startup(self, github_token: str, repo_full_name: str, discord_user_id: str) -> bool:
        print(f"📝 Creando startup.sh para {repo_full_name}")
        
        startup_script = f'''#!/bin/bash
set -e

LOG_FILE="/tmp/codespace_startup.log"
DISCORD_USER_ID="{discord_user_id}"
BOT_WEBHOOK_URL="${{BOT_WEBHOOK_URL:-{RENDER_EXTERNAL_URL}/webhook/tunnel_notify}}"

echo "🚀 [$(date)] Iniciando scripts de startup..." | tee -a "$LOG_FILE"

GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
BLUE='\\033[0;34m'
NC='\\033[0m'

WORKSPACE_ROOT="${{CODESPACE_VSCODE_FOLDER:-/workspaces/$(basename $(pwd))}}"
cd "$WORKSPACE_ROOT" || {{
    echo -e "${{RED}}❌ No se pudo acceder al workspace: $WORKSPACE_ROOT${{NC}}" | tee -a "$LOG_FILE"
    exit 1
}}

echo -e "${{BLUE}}📂 Workspace: $WORKSPACE_ROOT${{NC}}" | tee -a "$LOG_FILE"

if [ -f requirements.txt ]; then
    echo -e "${{YELLOW}}📦 Instalando dependencias de Python...${{NC}}" | tee -a "$LOG_FILE"
    pip install --quiet -r requirements.txt > /tmp/pip_install.log 2>&1 && \\
        echo -e "${{GREEN}}✅ Dependencias instaladas${{NC}}" | tee -a "$LOG_FILE" || \\
        echo -e "${{YELLOW}}⚠️  Algunas dependencias fallaron${{NC}}" | tee -a "$LOG_FILE"
fi

if [ -f web_server.py ]; then
    echo -e "${{YELLOW}}🌐 Iniciando Web Server con Cloudflare Tunnel...${{NC}}" | tee -a "$LOG_FILE"
    
    nohup python3 web_server.py > /tmp/web_server.log 2>&1 &
    WEB_PID=$!
    echo -e "${{GREEN}}✅ Web server iniciado (PID: $WEB_PID)${{NC}}" | tee -a "$LOG_FILE"
    
    echo -e "${{YELLOW}}⏳ Esperando a que Cloudflare Tunnel inicie (45s)...${{NC}}" | tee -a "$LOG_FILE"
    sleep 45
    
    TUNNEL_URL=""
    
    if [ -f /tmp/cloudflared.log ]; then
        TUNNEL_URL=$(grep -oP 'https://[a-z0-9-]+\\\\.trycloudflare\\\\.com' /tmp/cloudflared.log | tail -1)
        if [ -n "$TUNNEL_URL" ]; then
            echo -e "${{GREEN}}✅ Tunnel detectado desde logs: $TUNNEL_URL${{NC}}" | tee -a "$LOG_FILE"
        fi
    fi
    
    if [ -z "$TUNNEL_URL" ]; then
        echo -e "${{YELLOW}}🔍 Consultando endpoint local...${{NC}}" | tee -a "$LOG_FILE"
        TUNNEL_RESPONSE=$(curl -s http://localhost:8080/get_url 2>/dev/null || echo "{{}}")
        TUNNEL_URL=$(echo "$TUNNEL_RESPONSE" | grep -oP '"tunnel_url"\\\\s*:\\\\s*"\\\\K[^"]+' || echo "")
        
        if [ -n "$TUNNEL_URL" ]; then
            echo -e "${{GREEN}}✅ Tunnel detectado desde API: $TUNNEL_URL${{NC}}" | tee -a "$LOG_FILE"
        fi
    fi
    
    if [ -z "$TUNNEL_URL" ]; then
        echo -e "${{YELLOW}}⏳ Reintentando detección en 15s...${{NC}}" | tee -a "$LOG_FILE"
        sleep 15
        
        TUNNEL_URL=$(grep -oP 'https://[a-z0-9-]+\\\\.trycloudflare\\\\.com' /tmp/cloudflared.log | tail -1)
        
        if [ -z "$TUNNEL_URL" ]; then
            TUNNEL_RESPONSE=$(curl -s http://localhost:8080/get_url 2>/dev/null || echo "{{}}")
            TUNNEL_URL=$(echo "$TUNNEL_RESPONSE" | grep -oP '"tunnel_url"\\\\s*:\\\\s*"\\\\K[^"]+' || echo "")
        fi
    fi
    
    if [ -n "$TUNNEL_URL" ]; then
        echo -e "${{GREEN}}✅ Cloudflare Tunnel detectado: $TUNNEL_URL${{NC}}" | tee -a "$LOG_FILE"
        
        echo "$TUNNEL_URL" > /tmp/tunnel_url.txt
        
        echo -e "${{YELLOW}}📤 Notificando al bot de Discord...${{NC}}" | tee -a "$LOG_FILE"
        
        CODESPACE_NAME="${{CODESPACE_NAME:-unknown}}"
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S")
        
        JSON_PAYLOAD=$(cat <<EOF
{{
  "user_id": "$DISCORD_USER_ID",
  "codespace_name": "$CODESPACE_NAME",
  "tunnel_url": "$TUNNEL_URL",
  "tunnel_type": "cloudflare",
  "timestamp": "$TIMESTAMP",
  "auto_started": true
}}
EOF
)
        
        RESPONSE=$(curl -s -X POST "$BOT_WEBHOOK_URL" \\\\
          -H "Content-Type: application/json" \\\\
          -d "$JSON_PAYLOAD" \\\\
          -w "\\\\n%{{http_code}}")
        
        HTTP_CODE=$(echo "$RESPONSE" | tail -1)
        
        if [ "$HTTP_CODE" = "200" ]; then
            echo -e "${{GREEN}}✅ Bot notificado exitosamente${{NC}}" | tee -a "$LOG_FILE"
        else
            echo -e "${{YELLOW}}⚠️  No se pudo notificar al bot (HTTP $HTTP_CODE)${{NC}}" | tee -a "$LOG_FILE"
        fi
    else
        echo -e "${{RED}}❌ No se pudo detectar URL del Cloudflare Tunnel${{NC}}" | tee -a "$LOG_FILE"
        echo -e "${{YELLOW}}Últimas 30 líneas de cloudflared.log:${{NC}}" | tee -a "$LOG_FILE"
        tail -30 /tmp/cloudflared.log 2>/dev/null | tee -a "$LOG_FILE" || echo "  (log no encontrado)" | tee -a "$LOG_FILE"
    fi
    
elif [ -f auto_webserver_setup.sh ]; then
    echo -e "${{YELLOW}}🌐 Ejecutando auto_webserver_setup.sh...${{NC}}" | tee -a "$LOG_FILE"
    nohup bash auto_webserver_setup.sh > /tmp/web_server.log 2>&1 &
    echo -e "${{GREEN}}✅ Script de webserver iniciado${{NC}}" | tee -a "$LOG_FILE"
else
    echo -e "${{YELLOW}}⚠️  web_server.py no encontrado${{NC}}" | tee -a "$LOG_FILE"
fi

if [ -f start_server.sh ]; then
    echo -e "${{YELLOW}}🎮 Iniciando servidor de Minecraft...${{NC}}" | tee -a "$LOG_FILE"
    nohup bash start_server.sh > /tmp/minecraft_server.log 2>&1 &
    MC_PID=$!
    echo -e "${{GREEN}}✅ Minecraft iniciado (PID: $MC_PID)${{NC}}" | tee -a "$LOG_FILE"
elif [ -f run.sh ]; then
    echo -e "${{YELLOW}}🎮 Iniciando servidor con run.sh...${{NC}}" | tee -a "$LOG_FILE"
    nohup bash run.sh > /tmp/minecraft_server.log 2>&1 &
    MC_PID=$!
    echo -e "${{GREEN}}✅ Servidor iniciado (PID: $MC_PID)${{NC}}" | tee -a "$LOG_FILE"
fi

if [ -f main.py ] && [ -d "d0ce3-Addons" ] || grep -q "d0ce3-Addons" main.py 2>/dev/null; then
    echo -e "${{YELLOW}}🔧 Iniciando d0ce3-Addons...${{NC}}" | tee -a "$LOG_FILE"
    nohup python3 main.py > /tmp/addons.log 2>&1 &
    ADDONS_PID=$!
    echo -e "${{GREEN}}✅ d0ce3-Addons iniciado (PID: $ADDONS_PID)${{NC}}" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo -e "${{YELLOW}}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${{NC}}" | tee -a "$LOG_FILE"
echo -e "${{GREEN}}   ✨ Startup completado${{NC}}" | tee -a "$LOG_FILE"
echo -e "${{YELLOW}}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${{NC}}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo -e "${{GREEN}}📊 Procesos activos:${{NC}}" | tee -a "$LOG_FILE"
ps aux | grep -E "python3|cloudflared|java" | grep -v grep | tee -a "$LOG_FILE" || echo "  (ninguno detectado)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if [ -n "$TUNNEL_URL" ]; then
    echo -e "${{GREEN}}🌐 Tunnel URL: $TUNNEL_URL${{NC}}" | tee -a "$LOG_FILE"
fi

echo -e "${{YELLOW}}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${{NC}}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

echo "✅ [$(date)] Startup script finalizado" | tee -a "$LOG_FILE"
'''
        
        content_base64 = base64.b64encode(startup_script.encode()).decode()
        
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                existing_sha = None
                async with session.get(
                    f"https://api.github.com/repos/{repo_full_name}/contents/startup.sh",
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        existing_sha = data.get("sha")
                        print(f"ℹ️  Actualizando startup.sh existente")
                
                payload = {
                    "message": "🤖 Auto-create startup script by Doce-Bt",
                    "content": content_base64,
                    "branch": "main"
                }
                
                if existing_sha:
                    payload["sha"] = existing_sha
                
                async with session.put(
                    f"https://api.github.com/repos/{repo_full_name}/contents/startup.sh",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status in [200, 201]:
                        print(f"✅ startup.sh creado/actualizado")
                        return True
                    else:
                        error_data = await resp.json()
                        print(f"❌ Error creando startup.sh: {error_data}")
                        return False
        except Exception as e:
            print(f"❌ Excepción creando startup.sh: {e}")
            return False

async def setup(bot):
    await bot.add_cog(SetupCog(bot))