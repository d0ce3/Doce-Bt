# 🤖 Doce-Bt

**Bot de Discord para gestión avanzada de GitHub Codespaces y servidores Minecraft**

Doce-Bt es un bot de Discord diseñado para facilitar la gestión y control de GitHub Codespaces, con funcionalidades especiales para servidores de Minecraft. Incluye integración con el sistema de colas y notificaciones de [d0ce3-Addons](https://github.com/d0ce3/d0ce3-Addons).

---

## ✨ Características Principales

### 🖥️ **Control de Codespaces**
- **Vinculación de cuentas**: Conecta tu cuenta de GitHub con Discord
- **Gestión remota**: Inicia, detén y reinicia Codespaces desde Discord
- **Monitoreo en tiempo real**: Recibe notificaciones sobre el estado de tus Codespaces
- **Detección automática**: El bot detecta automáticamente tus Codespaces disponibles
- **Historial de vinculaciones**: Mantiene registro de todos los Codespaces que has usado
- **Cambio rápido**: Cambia entre diferentes Codespaces fácilmente

### 🎮 **Gestión de Minecraft**
- **Control del servidor**: Inicia, detén y reinicia servidores de Minecraft
- **Estado en tiempo real**: Consulta jugadores conectados, versión y estado del servidor
- **Ejecución de comandos**: Ejecuta comandos de consola directamente desde Discord
- **Gestión de jugadores**: Whitelist, kick, ban y op directamente desde el bot

### 📊 **Sistema de Eventos (Integración con d0ce3-Addons)**
- **Notificaciones de backups**: Recibe alertas cuando se completen o fallen backups automáticos
- **Monitoreo de Minecraft**: Notificaciones cuando el servidor cambie de estado
- **Sistema de colas**: Gestión automática de operaciones asíncronas
- **Polling inteligente**: Consulta periódica de eventos sin sobrecargar el sistema
- **Integración transparente**: Se activa automáticamente al vincular tu Codespace

### 🔐 **Sistema de Permisos**
- **Roles configurables**: Define quién puede usar cada función
- **Control granular**: Permisos específicos por servidor de Discord
- **Gestión fácil**: Comandos simples para administrar permisos

---

## 🚀 Instalación

### Requisitos Previos
- Python 3.9 o superior
- Cuenta de GitHub con acceso a Codespaces
- Bot de Discord creado en el [Portal de Desarrolladores](https://discord.com/developers/applications)

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/d0ce3/Doce-Bt.git
cd Doce-Bt
```

### Paso 2: Instalar Dependencias
```bash
pip install -r requirements.txt
```

### Paso 3: Configurar Variables de Entorno
Crea un archivo `.env` en la raíz del proyecto:

```env
# Token del bot de Discord
DISCORD_BOT_TOKEN=tu_token_aqui

# ID del servidor de Discord para pruebas (opcional)
DISCORD_GUILD_ID=123456789

# Puerto para el servidor web interno
PORT=10000

# URL externa si usas servicios como Render
RENDER_EXTERNAL_URL=https://tu-app.onrender.com
```

### Paso 4: Ejecutar el Bot
```bash
python main.py
```

---

## 📖 Comandos Disponibles

### 🔗 Vinculación y Setup
- `/setup` - Configura tu token personal de GitHub
- `/vincular` - Vincula un Codespace (muestra lista si no especificas nombre)
- `/refrescar` - Verifica el estado de tu token y vinculación
- `/historial` - Ver historial de Codespaces vinculados

### 🖥️ Control de Codespaces
- `/status` - Ver estado del Codespace
- `/start` - Iniciar Codespace
- `/stop` - Detener Codespace

### 🎮 Gestión de Minecraft
- `/mc_start` - Iniciar servidor de Minecraft
- `/mc_stop` - Detener servidor de Minecraft
- `/mc_restart` - Reiniciar servidor de Minecraft
- `/mc_status` - Ver estado del servidor y jugadores
- `/mc_cmd` - Ejecutar comando en la consola
- `/mc_whitelist` - Gestionar whitelist (add/remove/list)
- `/mc_op` - Dar permisos de operador
- `/mc_kick` - Expulsar jugador
- `/mc_ban` - Banear/desbanear jugador

### 📊 Sistema de Eventos
- `/addon_stats` - Ver estadísticas del sistema de eventos

### 🔐 Permisos
- `/permisos_agregar` - Agregar rol con permisos
- `/permisos_quitar` - Quitar rol de permisos
- `/permisos_ver` - Ver roles con permisos

### ℹ️ Información
- `/info` - Información sobre el bot
- `/ayuda` - Ver comandos disponibles

---

## 🔧 Integración con d0ce3-Addons

El bot incluye integración automática con el sistema de colas y eventos de [d0ce3-Addons](https://github.com/d0ce3/d0ce3-Addons).

### Cómo Funciona
1. **Polling automático**: El bot consulta cada 30 segundos los eventos desde tus Codespaces
2. **Notificaciones inteligentes**: Recibe mensajes directos cuando ocurran eventos importantes
3. **Sin configuración adicional**: La integración se activa automáticamente al vincular tu Codespace

### Tipos de Eventos Soportados
- ✅ **Backup exitoso**: Notificación con tamaño y duración
- ❌ **Error en backup**: Detalles del error y sugerencias
- 🎮 **Estado de Minecraft**: Cambios en el servidor (online/offline)
- 🖥️ **Estado de Codespace**: Inicio, detención o errores

### Requisitos
- Tener instalado el addon `d0ce3tools` en tu Codespace con Minecraft
- Codespace ejecutándose con el servidor web activo (puerto 8080)
- Haber vinculado tu Codespace con `/vincular`

---

## 🌐 Despliegue

### Render (Recomendado)
1. Crea una cuenta en [Render](https://render.com)
2. Crea un nuevo "Web Service" desde tu repositorio
3. Configura las variables de entorno
4. Deploy automático en cada push

### Railway
1. Conecta tu repositorio con [Railway](https://railway.app)
2. Configura las variables de entorno
3. Deploy automático

### Hosting Local
Puedes ejecutar el bot en tu máquina local o servidor:
```bash
python main.py
```

---

## 📁 Estructura del Proyecto

```
Doce-Bt/
├── cogs/                          # Módulos del bot (comandos)
│   ├── addon_integration.py       # Integración con d0ce3-Addons
│   ├── codespace_control.py       # Control de Codespaces
│   ├── codespace_minecraft.py     # Gestión de Minecraft
│   ├── info.py                    # Comandos de información
│   ├── permisos.py                # Sistema de permisos
│   └── setup_cog.py               # Vinculación de cuentas
├── data/                          # Datos persistentes (JSON)
├── utils/                         # Utilidades
│   ├── jsondb.py                  # Manejo de archivos JSON
│   ├── permissions.py             # Sistema de permisos
│   └── github_api.py              # Interacción con GitHub API
├── web/                           # Servidor web interno
│   ├── server.py                  # Flask server
│   └── auto_ping.py               # Keep-alive
├── config.py                      # Configuración
├── main.py                        # Punto de entrada
├── requirements.txt               # Dependencias
└── README.md                      # Este archivo
```

---

## 🛠️ Tecnologías Utilizadas

- **discord.py**: Librería para interactuar con Discord
- **Flask**: Servidor web para OAuth y webhooks
- **aiohttp**: Cliente HTTP asíncrono para polling
- **GitHub API**: Gestión de Codespaces
- **Python 3.9+**: Lenguaje base

---

## 🐛 Solución de Problemas

### El bot no responde
- Verifica que el token en `.env` sea correcto
- Asegúrate de que el bot tenga los permisos necesarios en Discord
- Revisa los logs en la consola

### Los comandos no aparecen
- Espera hasta 1 hora para la propagación global
- Si tienes `DISCORD_GUILD_ID` configurado, los comandos aparecen instantáneamente en ese servidor
- Ejecuta `/` en Discord para forzar la actualización de comandos

### Error "Sesión Expirada" al usar `/stop`
- Verifica que tu token de GitHub sea válido con `/refrescar`
- Actualiza tu token con `/setup` si es necesario
- Asegúrate de haber vinculado un Codespace con `/vincular`

### El polling de eventos no funciona
- Verifica que tu Codespace esté ejecutándose
- Asegúrate de que el puerto 8080 esté expuesto
- Confirma que el addon `d0ce3tools` esté instalado
- Usa `/addon_stats` para ver el estado del sistema

### No detecta mis Codespaces
- Verifica que tu token tenga el scope `codespace`
- Usa `/vincular` sin parámetros para ver la lista actualizada
- Asegúrate de que tus Codespaces existan en GitHub

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📝 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

---

## 📧 Contacto

- **GitHub**: [@d0ce3](https://github.com/d0ce3)
- **Repositorio**: [Doce-Bt](https://github.com/d0ce3/Doce-Bt)
- **Addons**: [d0ce3-Addons](https://github.com/d0ce3/d0ce3-Addons)

---

## 🙏 Agradecimientos

Gracias a todos los que han contribuido y dado feedback para mejorar este proyecto.

---

**⚡ Hecho con ❤️ por d0ce3**
