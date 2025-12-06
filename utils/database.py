import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from config import DATABASE_URL

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        try:
            self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            self._init_tables()
            print("✅ Conectado a Supabase")
        except Exception as e:
            print(f"❌ Error conectando a Supabase: {e}")
            raise
    
    def _init_tables(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sesiones (
                    discord_user_id TEXT PRIMARY KEY,
                    github_username TEXT,
                    github_id TEXT,
                    token TEXT,
                    expira_token TIMESTAMP,
                    codespace TEXT,
                    repo_name TEXT,
                    repo_full_name TEXT,
                    tunnel_url TEXT,
                    tunnel_port INTEGER,
                    tunnel_type TEXT,
                    voicechat_address TEXT,
                    tunnel_actualizado TIMESTAMP,
                    auto_configured BOOLEAN DEFAULT FALSE,
                    devcontainer_created BOOLEAN DEFAULT FALSE,
                    startup_created BOOLEAN DEFAULT FALSE,
                    configured_at TIMESTAMP,
                    vinculado_at TIMESTAMP,
                    notification_mode TEXT DEFAULT 'dm',
                    notification_channel_id TEXT,
                    notification_guild_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vinculaciones (
                    discord_user_id TEXT PRIMARY KEY,
                    github_username TEXT,
                    vinculado_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS permisos (
                    discord_user_id TEXT PRIMARY KEY,
                    rol TEXT,
                    asignado_at TIMESTAMP DEFAULT NOW(),
                    asignado_por TEXT
                )
            """)
            
            self.conn.commit()
            print("✅ Tablas inicializadas")
    
    def get_sesion(self, user_id: str) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM sesiones WHERE discord_user_id = %s", (user_id,))
            result = cur.fetchone()
            
            if result:
                data = dict(result)
                for field in ["expira_token", "tunnel_actualizado", "configured_at", "vinculado_at", "created_at", "updated_at"]:
                    if data.get(field):
                        data[field] = data[field].isoformat()
                return data
            return None
    
    def get_all_sesiones(self) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM sesiones")
            results = cur.fetchall()
            
            sesiones = {}
            for row in results:
                user_id = row["discord_user_id"]
                data = dict(row)
                for field in ["expira_token", "tunnel_actualizado", "configured_at", "vinculado_at", "created_at", "updated_at"]:
                    if data.get(field):
                        data[field] = data[field].isoformat()
                sesiones[user_id] = data
            return sesiones
    
    def save_sesion(self, user_id: str, data: dict):
        with self.conn.cursor() as cur:
            def parse_timestamp(value):
                if not value:
                    return None
                try:
                    if isinstance(value, str):
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return value
                except:
                    return None
            
            expira_token = parse_timestamp(data.get("expira_token"))
            tunnel_actualizado = parse_timestamp(data.get("tunnel_actualizado"))
            configured_at = parse_timestamp(data.get("configured_at"))
            vinculado_at = parse_timestamp(data.get("vinculado_at")) or datetime.now()
            
            cur.execute("""
                INSERT INTO sesiones (
                    discord_user_id, github_username, github_id, token,
                    expira_token, codespace, repo_name, repo_full_name,
                    tunnel_url, tunnel_port, tunnel_type, voicechat_address,
                    tunnel_actualizado, auto_configured, devcontainer_created,
                    startup_created, configured_at, vinculado_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (discord_user_id) DO UPDATE SET
                    github_username = EXCLUDED.github_username,
                    github_id = EXCLUDED.github_id,
                    token = EXCLUDED.token,
                    expira_token = EXCLUDED.expira_token,
                    codespace = EXCLUDED.codespace,
                    repo_name = EXCLUDED.repo_name,
                    repo_full_name = EXCLUDED.repo_full_name,
                    tunnel_url = EXCLUDED.tunnel_url,
                    tunnel_port = EXCLUDED.tunnel_port,
                    tunnel_type = EXCLUDED.tunnel_type,
                    voicechat_address = EXCLUDED.voicechat_address,
                    tunnel_actualizado = EXCLUDED.tunnel_actualizado,
                    auto_configured = EXCLUDED.auto_configured,
                    devcontainer_created = EXCLUDED.devcontainer_created,
                    startup_created = EXCLUDED.startup_created,
                    configured_at = EXCLUDED.configured_at,
                    updated_at = NOW()
            """, (
                user_id, data.get("github_username"), data.get("github_id"), data.get("token"),
                expira_token, data.get("codespace"), data.get("repo_name"), data.get("repo_full_name"),
                data.get("tunnel_url"), data.get("tunnel_port"), data.get("tunnel_type"),
                data.get("voicechat_address"), tunnel_actualizado, data.get("auto_configured", False),
                data.get("devcontainer_created", False), data.get("startup_created", False),
                configured_at, vinculado_at
            ))
            self.conn.commit()
    
    def delete_sesion(self, user_id: str):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM sesiones WHERE discord_user_id = %s", (user_id,))
            self.conn.commit()
    
    def get_vinculaciones(self) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM vinculaciones")
            results = cur.fetchall()
            return {row["discord_user_id"]: {"github_username": row["github_username"]} for row in results}
    
    def save_vinculacion(self, user_id: str, github_username: str):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vinculaciones (discord_user_id, github_username)
                VALUES (%s, %s)
                ON CONFLICT (discord_user_id) DO UPDATE SET
                    github_username = EXCLUDED.github_username,
                    vinculado_at = NOW()
            """, (user_id, github_username))
            self.conn.commit()
    
    def delete_vinculacion(self, user_id: str):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM vinculaciones WHERE discord_user_id = %s", (user_id,))
            self.conn.commit()
    
    def get_permisos(self) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM permisos")
            results = cur.fetchall()
            return {row["discord_user_id"]: {"rol": row["rol"]} for row in results}
    
    def get_permiso(self, user_id: str) -> dict:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM permisos WHERE discord_user_id = %s", (user_id,))
            result = cur.fetchone()
            return dict(result) if result else None
    
    def save_permiso(self, user_id: str, rol: str, asignado_por: str = None):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO permisos (discord_user_id, rol, asignado_por)
                VALUES (%s, %s, %s)
                ON CONFLICT (discord_user_id) DO UPDATE SET
                    rol = EXCLUDED.rol,
                    asignado_por = EXCLUDED.asignado_por,
                    asignado_at = NOW()
            """, (user_id, rol, asignado_por))
            self.conn.commit()
    
    def delete_permiso(self, user_id: str):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM permisos WHERE discord_user_id = %s", (user_id,))
            self.conn.commit()
    
    def close(self):
        if self.conn:
            self.conn.close()

_db_instance = None

def get_db() -> Database:
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance