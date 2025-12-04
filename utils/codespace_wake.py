"""
utils/codespace_wake.py

Módulo para DESPERTAR REALMENTE un Codespace (no solo cambiar estado en API).
Usa requests HTTP para simular abrir el navegador, lo que inicia la VM.

Compatible con:
- URLs nativas de Codespace
- Cloudflare Tunnel
- Sistema multiusuario
"""

import asyncio
import aiohttp
from typing import Tuple, Optional
from utils.github_api import api_request


async def despertar_codespace_real(
    token: str,
    codespace_name: str,
    codespace_url: Optional[str] = None,
    max_intentos: int = 12,
    timeout_inicial: int = 180
) -> Tuple[bool, str]:
    """
    Despierta REALMENTE un Codespace iniciando la VM.
    
    Este método hace 3 cosas:
    1. Inicia el Codespace vía API (cambia estado a "Starting")
    2. Hace requests HTTP al endpoint web del Codespace (simula abrir navegador)
    3. Verifica que el estado final sea "Available"
    
    Args:
        token: GitHub Personal Access Token
        codespace_name: Nombre del codespace
        codespace_url: URL del codespace (si no se provee, se construye)
        max_intentos: Número máximo de intentos de conexión
        timeout_inicial: Tiempo total máximo de espera (segundos)
        
    Returns:
        (success: bool, mensaje: str)
    """
    try:
        # Paso 1: Iniciar el codespace con la API
        print(f"🔄 Iniciando Codespace '{codespace_name}' vía API...")
        _, error = api_request(
            token,
            f"/user/codespaces/{codespace_name}/start",
            method="POST"
        )
        
        # No es error si ya está iniciado
        if error and "already" not in error.lower() and "running" not in error.lower():
            return False, f"Error en API de GitHub: {error}"
        
        # Paso 2: Obtener información del codespace
        data, error = api_request(token, f"/user/codespaces/{codespace_name}")
        if error:
            return False, f"Error obteniendo info del codespace: {error}"
        
        # Construir URL web del codespace
        if not codespace_url:
            web_url = data.get("web_url")
            if not web_url:
                return False, "No se pudo obtener la URL del Codespace"
        else:
            web_url = codespace_url
        
        print(f"🌐 URL del Codespace: {web_url}")
        
        # Paso 3: Hacer requests HTTP para despertar la VM
        headers = {
            "User-Agent": "Mozilla/5.0 (d0ce3-Bt/2.0) Discord Bot",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
        }
        
        print(f"⏳ Intentando despertar VM del Codespace...")
        print(f"   Intentos máximos: {max_intentos}")
        print(f"   Timeout total: {timeout_inicial}s")
        
        tiempo_por_intento = timeout_inicial / max_intentos
        
        async with aiohttp.ClientSession() as session:
            for intento in range(max_intentos):
                try:
                    print(f"   Intento {intento + 1}/{max_intentos}...")
                    
                    # Hacer request GET al codespace
                    async with session.get(
                        web_url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=tiempo_por_intento),
                        allow_redirects=True
                    ) as resp:
                        status = resp.status
                        
                        # 200: Codespace respondió (probablemente esté listo)
                        if status == 200:
                            print(f"   ✅ Respuesta 200 - Codespace respondiendo")
                            
                            # Esperar un poco más para asegurar
                            await asyncio.sleep(5)
                            
                            # Verificar estado final
                            estado_data, _ = api_request(
                                token,
                                f"/user/codespaces/{codespace_name}"
                            )
                            
                            if estado_data:
                                estado_final = estado_data.get("state")
                                
                                if estado_final == "Available":
                                    tiempo_total = (intento + 1) * tiempo_por_intento
                                    return True, f"Codespace despertado exitosamente (tomó ~{int(tiempo_total)}s)"
                                else:
                                    print(f"   ⚠️ Estado aún es '{estado_final}', continuando...")
                        
                        # 202: Aceptado pero aún procesando
                        elif status == 202:
                            print(f"   🔄 HTTP 202 - Codespace iniciando...")
                        
                        # 503: Servicio no disponible (aún cargando)
                        elif status == 503:
                            print(f"   ⏳ HTTP 503 - VM aún cargando...")
                        
                        # 302/307: Redirección (puede ser parte del inicio)
                        elif status in [302, 307, 308]:
                            print(f"   🔀 HTTP {status} - Siguiendo redirección...")
                        
                        else:
                            print(f"   ⚠️ HTTP {status} - Estado inesperado")
                
                except asyncio.TimeoutError:
                    print(f"   ⏱️ Timeout en intento {intento + 1}")
                
                except aiohttp.ClientError as e:
                    print(f"   ⚠️ Error de conexión: {type(e).__name__}")
                
                except Exception as e:
                    print(f"   ❌ Error inesperado: {str(e)}")
                
                # Esperar antes del siguiente intento
                if intento < max_intentos - 1:
                    await asyncio.sleep(3)
        
        # Si llegamos aquí, agotamos los intentos
        return False, (
            f"El Codespace no respondió después de {max_intentos} intentos "
            f"({timeout_inicial}s). Puede estar tardando más de lo usual. "
            "Intenta verificar manualmente en GitHub."
        )
    
    except Exception as e:
        return False, f"Error inesperado: {str(e)}"


async def verificar_estado_codespace(token: str, codespace_name: str) -> Tuple[str, Optional[str]]:
    """
    Verifica el estado actual de un Codespace.
    
    Returns:
        (estado: str, error: Optional[str])
        Posibles estados: "Available", "Starting", "Shutdown", "Unknown"
    """
    data, error = api_request(token, f"/user/codespaces/{codespace_name}")
    
    if error:
        return "Unknown", error
    
    return data.get("state", "Unknown"), None


async def esperar_codespace_listo(
    token: str,
    codespace_name: str,
    max_espera: int = 60,
    intervalo: int = 5
) -> Tuple[bool, str]:
    """
    Espera a que un Codespace esté en estado "Available".
    
    Args:
        token: GitHub token
        codespace_name: Nombre del codespace
        max_espera: Tiempo máximo de espera en segundos
        intervalo: Intervalo entre checks en segundos
        
    Returns:
        (listo: bool, estado_final: str)
    """
    intentos = max_espera // intervalo
    
    for i in range(intentos):
        estado, error = await verificar_estado_codespace(token, codespace_name)
        
        if error:
            print(f"⚠️ Error verificando estado: {error}")
            await asyncio.sleep(intervalo)
            continue
        
        print(f"   Estado actual: {estado} ({i+1}/{intentos})")
        
        if estado == "Available":
            return True, estado
        
        if estado == "Shutdown":
            return False, "El Codespace se detuvo inesperadamente"
        
        await asyncio.sleep(intervalo)
    
    estado_final, _ = await verificar_estado_codespace(token, codespace_name)
    return False, f"Timeout esperando estado 'Available'. Estado actual: {estado_final}"