import asyncio
import aiohttp
from typing import Tuple, Optional
from utils.github_api import api_request


async def despertar_codespace_real(
    token: str,
    codespace_name: str,
    codespace_url: Optional[str] = None,
    max_intentos: int = 20,
    timeout_inicial: int = 300
) -> Tuple[bool, str]:
    """
    Despierta REALMENTE un Codespace de hibernación.
    
    Estrategia:
    1. Iniciar vía API (si está apagado)
    2. Hacer conexiones HTTP PERSISTENTES al web_url (esto despierta la VM)
    3. Intentar múltiples puertos (443, 8080) para forzar despertar
    4. Verificar que /health o cualquier endpoint responda
    
    Args:
        token: GitHub Personal Access Token
        codespace_name: Nombre del codespace
        codespace_url: URL del codespace (opcional)
        max_intentos: Intentos máximos (default: 20)
        timeout_inicial: Timeout total en segundos (default: 300 = 5 min)
        
    Returns:
        (success: bool, mensaje: str)
    """
    try:
        print(f"\n{'='*60}")
        print(f"🚀 INICIANDO DESPERTAR REAL DE CODESPACE")
        print(f"   Codespace: {codespace_name}")
        print(f"   Intentos: {max_intentos}")
        print(f"   Timeout: {timeout_inicial}s")
        print(f"{'='*60}\n")
        
        # PASO 1: Iniciar vía API
        print("📡 Paso 1: Iniciando vía API de GitHub...")
        _, error = api_request(
            token,
            f"/user/codespaces/{codespace_name}/start",
            method="POST"
        )
        
        if error and "already" not in error.lower() and "running" not in error.lower():
            print(f"   ❌ Error en API: {error}")
            return False, f"Error en API de GitHub: {error}"
        
        print("   ✅ API respondió OK")
        
        # PASO 2: Obtener información del codespace
        print("\n📋 Paso 2: Obteniendo información del Codespace...")
        data, error = api_request(token, f"/user/codespaces/{codespace_name}")
        if error:
            print(f"   ❌ Error obteniendo info: {error}")
            return False, f"Error obteniendo info: {error}"
        
        estado_inicial = data.get("state", "Unknown")
        print(f"   Estado en API: {estado_inicial}")
        
        # Obtener web_url (esta es la URL PRINCIPAL del navegador)
        web_url = data.get("web_url")
        if not web_url:
            print("   ❌ No se encontró web_url")
            return False, "No se pudo obtener la URL del Codespace"
        
        print(f"   Web URL: {web_url}")
        
        # PASO 3: URLs a probar (múltiples estrategias)
        urls_a_probar = []
        
        # URL principal del navegador (esta SIEMPRE despierta el Codespace)
        urls_a_probar.append(("web_principal", web_url))
        
        # Si tenemos codespace_url personalizada (tunnel), agregarla
        if codespace_url and codespace_url != web_url:
            urls_a_probar.append(("custom", codespace_url))
            urls_a_probar.append(("custom_health", f"{codespace_url}/health"))
        
        # URL del puerto 8080 si existe
        if "web_url" in data:
            base_url = web_url.replace("https://", "").split(".app.github.dev")[0]
            url_8080 = f"https://{base_url}-8080.app.github.dev"
            urls_a_probar.append(("puerto_8080", url_8080))
            urls_a_probar.append(("puerto_8080_health", f"{url_8080}/health"))
        
        print(f"\n🌐 Paso 3: Probando {len(urls_a_probar)} URLs para despertar VM...")
        
        tiempo_por_intento = timeout_inicial / max_intentos
        conexion_exitosa = False
        url_exitosa = None
        tipo_exitoso = None
        
        # Headers que simulan un navegador real
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        
        async with aiohttp.ClientSession() as session:
            for intento in range(max_intentos):
                print(f"\n🔄 Intento {intento + 1}/{max_intentos}")
                
                # Probar cada URL en este intento
                for tipo, url in urls_a_probar:
                    try:
                        print(f"   → Probando {tipo}: {url[:60]}...")
                        
                        async with session.get(
                            url,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=tiempo_por_intento),
                            allow_redirects=True,
                            ssl=False  # Ignorar certificados SSL
                        ) as resp:
                            status = resp.status
                            
                            # Cualquier respuesta 2xx o 3xx indica que el servidor responde
                            if 200 <= status < 400:
                                print(f"   ✅ {tipo} respondió HTTP {status}")
                                conexion_exitosa = True
                                url_exitosa = url
                                tipo_exitoso = tipo
                                
                                # Si es la URL principal, definitivamente está despierto
                                if tipo == "web_principal":
                                    print(f"\n{'='*60}")
                                    print(f"🎉 VM DESPERTADA EXITOSAMENTE")
                                    print(f"   URL: {url}")
                                    print(f"   Intentos: {intento + 1}")
                                    print(f"   Tiempo: ~{int((intento + 1) * tiempo_por_intento)}s")
                                    print(f"{'='*60}\n")
                                    
                                    # Verificar estado final
                                    await asyncio.sleep(2)
                                    estado_data, _ = api_request(token, f"/user/codespaces/{codespace_name}")
                                    if estado_data:
                                        estado_final = estado_data.get("state")
                                        return True, f"Codespace despertado (estado: {estado_final}, tomó ~{int((intento + 1) * tiempo_por_intento)}s)"
                                    
                                    return True, f"Codespace despertado exitosamente (tomó ~{int((intento + 1) * tiempo_por_intento)}s)"
                            
                            # 503 = Service Unavailable (VM iniciando)
                            elif status == 503:
                                print(f"   🟡 {tipo} HTTP 503 - VM iniciando...")
                            
                            # 502 = Bad Gateway (VM no lista aún)
                            elif status == 502:
                                print(f"   🟡 {tipo} HTTP 502 - VM no lista...")
                            
                            else:
                                print(f"   ⚠️ {tipo} HTTP {status}")
                    
                    except asyncio.TimeoutError:
                        print(f"   ⏱️ {tipo} - Timeout")
                    
                    except aiohttp.ClientConnectorError:
                        print(f"   ⚠️ {tipo} - No se pudo conectar")
                    
                    except Exception as e:
                        print(f"   ⚠️ {tipo} - Error: {type(e).__name__}")
                
                # Si ya tuvimos una conexión exitosa, verificar estado
                if conexion_exitosa and intento >= 3:
                    print(f"\n🔍 Verificando estado después de conexión exitosa...")
                    estado_data, _ = api_request(token, f"/user/codespaces/{codespace_name}")
                    if estado_data:
                        estado_actual = estado_data.get("state")
                        print(f"   Estado actual: {estado_actual}")
                        
                        if estado_actual == "Available":
                            print(f"\n{'='*60}")
                            print(f"🎉 CODESPACE COMPLETAMENTE ACTIVO")
                            print(f"   URL que respondió: {url_exitosa}")
                            print(f"   Tipo: {tipo_exitoso}")
                            print(f"   Tiempo total: ~{int((intento + 1) * tiempo_por_intento)}s")
                            print(f"{'='*60}\n")
                            return True, f"Codespace activo (verificado vía {tipo_exitoso}, tomó ~{int((intento + 1) * tiempo_por_intento)}s)"
                
                # Esperar antes del siguiente intento
                if intento < max_intentos - 1:
                    await asyncio.sleep(3)
        
        # Si hubo alguna conexión exitosa pero no llegó a Available
        if conexion_exitosa:
            print(f"\n⚠️ Hubo conexión exitosa pero estado no confirmado")
            return True, f"Codespace respondió (vía {tipo_exitoso}) pero estado no confirmado. Puede estar iniciando servicios."
        
        # Si llegamos aquí, no hubo éxito
        print(f"\n{'='*60}")
        print(f"❌ NO SE PUDO DESPERTAR EL CODESPACE")
        print(f"   Intentos: {max_intentos}")
        print(f"   Tiempo: {timeout_inicial}s")
        print(f"{'='*60}\n")
        
        return False, (
            f"El Codespace no respondió después de {max_intentos} intentos "
            f"({timeout_inicial}s). La VM puede requerir inicio manual desde GitHub. "
            f"Estado en API: {estado_inicial}"
        )
    
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {str(e)}")
        import traceback
        traceback.print_exc()
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
    
    # Timeout
    estado_final, _ = await verificar_estado_codespace(token, codespace_name)
    return False, f"Timeout esperando estado 'Available'. Estado actual: {estado_final}"