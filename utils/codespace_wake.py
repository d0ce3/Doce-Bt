import asyncio
import aiohttp
from typing import Tuple, Optional
from utils.github_api import api_request


async def hacer_request_agresivo(session: aiohttp.ClientSession, url: str, intento: int):
    """Hace un request agresivo con diferentes configuraciones"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) Firefox/121.0",
    ]
    
    headers = {
        "User-Agent": user_agents[intento % len(user_agents)],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    
    try:
        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
            allow_redirects=True,
            ssl=False
        ) as resp:
            return resp.status, await resp.text()
    except Exception as e:
        return None, str(e)


async def bombardear_url(url: str, duracion: int = 120):
    """
    Bombardea una URL con requests constantes durante X segundos.
    Esto FUERZA al Codespace a despertar.
    """
    print(f"💣 Bombardeando {url} durante {duracion}s...")
    
    connector = aiohttp.TCPConnector(limit=10, force_close=False)
    timeout = aiohttp.ClientTimeout(total=15)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tareas = []
        inicio = asyncio.get_event_loop().time()
        intento = 0
        
        while (asyncio.get_event_loop().time() - inicio) < duracion:
            # Lanzar 3 requests simultáneos cada 2 segundos
            for _ in range(3):
                tarea = hacer_request_agresivo(session, url, intento)
                tareas.append(tarea)
                intento += 1
            
            # Ejecutar las tareas
            resultados = await asyncio.gather(*tareas, return_exceptions=True)
            
            # Verificar si alguna tuvo éxito
            for i, resultado in enumerate(resultados):
                if isinstance(resultado, tuple):
                    status, _ = resultado
                    if status and 200 <= status < 400:
                        print(f"   ✅ Request #{i+1} exitoso: HTTP {status}")
                        return True, status
                    elif status == 503:
                        print(f"   🟡 Request #{i+1}: HTTP 503 (iniciando...)")
                    elif status:
                        print(f"   ⚠️ Request #{i+1}: HTTP {status}")
            
            # Limpiar tareas
            tareas = []
            
            # Esperar antes del siguiente bombardeo
            await asyncio.sleep(2)
        
        return False, None


async def despertar_codespace_real(
    token: str,
    codespace_name: str,
    codespace_url: Optional[str] = None,
    max_intentos: int = 20,
    timeout_inicial: int = 300
) -> Tuple[bool, str]:
    """
    Despierta REALMENTE un Codespace usando bombardeo HTTP agresivo.
    
    Esta versión hace requests CONSTANTES para forzar el despertar.
    """
    try:
        print(f"\n{'='*70}")
        print(f"🚀 DESPERTAR AGRESIVO DE CODESPACE")
        print(f"   Codespace: {codespace_name}")
        print(f"   Estrategia: Bombardeo HTTP constante")
        print(f"{'='*70}\n")
        
        # PASO 1: Iniciar vía API
        print("📡 Paso 1: Iniciando vía API de GitHub...")
        _, error = api_request(
            token,
            f"/user/codespaces/{codespace_name}/start",
            method="POST"
        )
        
        if error and "already" not in error.lower() and "running" not in error.lower():
            print(f"   ❌ Error en API: {error}")
            # Continuar de todos modos, puede estar ya iniciado
        else:
            print("   ✅ API respondió OK")
        
        # Pequeña espera para que la API procese
        await asyncio.sleep(5)
        
        # PASO 2: Obtener web_url
        print("\n📋 Paso 2: Obteniendo web_url...")
        data, error = api_request(token, f"/user/codespaces/{codespace_name}")
        if error:
            print(f"   ❌ Error: {error}")
            return False, f"Error obteniendo info: {error}"
        
        web_url = data.get("web_url")
        if not web_url:
            return False, "No se encontró web_url"
        
        print(f"   🌐 Web URL: {web_url}")
        
        # PASO 3: URLs a bombardear
        urls_bombardear = [web_url]
        
        # Agregar codespace_url si es diferente
        if codespace_url and codespace_url != web_url:
            urls_bombardear.append(codespace_url)
        
        # Agregar puerto 8080
        if "app.github.dev" in web_url:
            base = web_url.replace("https://", "").split(".app.github.dev")[0]
            url_8080 = f"https://{base}-8080.app.github.dev"
            urls_bombardear.append(url_8080)
        
        print(f"\n🎯 Paso 3: Bombardeando {len(urls_bombardear)} URLs...")
        for url in urls_bombardear:
            print(f"   • {url}")
        
        # PASO 4: Bombardeo agresivo en paralelo
        print(f"\n💣 Paso 4: Iniciando bombardeo (máx {timeout_inicial}s)...")
        
        tareas_bombardeo = []
        for url in urls_bombardear:
            tarea = bombardear_url(url, duracion=timeout_inicial)
            tareas_bombardeo.append(tarea)
        
        # Ejecutar bombardeos en paralelo con timeout
        try:
            resultados = await asyncio.wait_for(
                asyncio.gather(*tareas_bombardeo, return_exceptions=True),
                timeout=timeout_inicial + 10
            )
            
            # Verificar si algún bombardeo tuvo éxito
            for i, resultado in enumerate(resultados):
                if isinstance(resultado, tuple):
                    exito, status = resultado
                    if exito:
                        print(f"\n{'='*70}")
                        print(f"🎉 BOMBARDEO EXITOSO EN URL #{i+1}")
                        print(f"   Status: HTTP {status}")
                        print(f"{'='*70}\n")
                        
                        # Verificar estado final
                        await asyncio.sleep(3)
                        estado_data, _ = api_request(token, f"/user/codespaces/{codespace_name}")
                        if estado_data:
                            estado_final = estado_data.get("state")
                            return True, f"Codespace despertado exitosamente (estado: {estado_final})"
                        
                        return True, "Codespace despertado exitosamente"
        
        except asyncio.TimeoutError:
            print(f"\n⏱️ Timeout después de {timeout_inicial}s")
        
        # PASO 5: Verificar estado final de todos modos
        print(f"\n🔍 Paso 5: Verificando estado final...")
        estado_data, _ = api_request(token, f"/user/codespaces/{codespace_name}")
        if estado_data:
            estado_final = estado_data.get("state")
            print(f"   Estado: {estado_final}")
            
            if estado_final == "Available":
                print(f"\n{'='*70}")
                print(f"✅ CODESPACE DISPONIBLE (aunque bombardeo no confirmó)")
                print(f"{'='*70}\n")
                return True, f"Codespace en estado Available (puede estar iniciando servicios)"
            elif estado_final == "Starting":
                return False, "Codespace en estado 'Starting'. Espera 2-3 minutos y usa /status"
        
        print(f"\n{'='*70}")
        print(f"❌ NO SE PUDO DESPERTAR")
        print(f"{'='*70}\n")
        
        return False, (
            f"El Codespace no respondió al bombardeo HTTP. "
            f"Estado actual: {estado_data.get('state') if estado_data else 'Unknown'}. "
            f"Puede requerir inicio manual desde GitHub."
        )
    
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, f"Error inesperado: {str(e)}"


async def verificar_estado_codespace(token: str, codespace_name: str) -> Tuple[str, Optional[str]]:
    """Verifica el estado actual de un Codespace"""
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
    """Espera a que un Codespace esté en estado Available"""
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
    return False, f"Timeout esperando 'Available'. Estado: {estado_final}"