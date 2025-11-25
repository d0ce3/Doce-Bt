import requests

def api_request(token, endpoint, method="GET"):
    """Realiza una petición a la API de GitHub"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    url = f"https://api.github.com{endpoint}"

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=15)
        elif method == "POST":
            response = requests.post(url, headers=headers, timeout=15)
        else:
            return None, f"Método HTTP no soportado: {method}"

        if response.status_code in [200, 201, 202]:
            try:
                return response.json(), None
            except:
                return True, None  # Éxito sin contenido JSON
        else:
            return None, f"Error {response.status_code}: {response.text[:200]}"
    except Exception as e:
        return None, f"Error de conexión: {str(e)}"

def listar_codespaces(token):
    """Lista los codespaces del usuario"""
    data, error = api_request(token, "/user/codespaces")
    if error:
        return [], error
    return data.get("codespaces", []), None

def iniciar_codespace(token, codespace_name):
    """Inicia un codespace"""
    _, error = api_request(token, f"/user/codespaces/{codespace_name}/start", method="POST")
    return error is None, error or "Iniciado correctamente"

def detener_codespace(token, codespace_name):
    """Detiene un codespace"""
    _, error = api_request(token, f"/user/codespaces/{codespace_name}/stop", method="POST")
    return error is None, error or "Detenido correctamente"

def estado_codespace(token, codespace_name):
    """Obtiene el estado de un codespace"""
    data, error = api_request(token, f"/user/codespaces/{codespace_name}")
    if error:
        return "Unknown", error
    return data.get("state", "Unknown"), None

def validar_token(token):
    """Valida que un token de GitHub sea válido"""
    data, error = api_request(token, "/user")
    if error:
        return False, error
    return True, data.get("login", "Usuario")
