"""
Nexo Analytics - Módulo de Configuración Unificada por Entorno
Gestiona variables de entorno, rutas de almacenamiento, endpoints y políticas de sistema.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _load_env_file(env_path: Path) -> None:
    """Carga variables desde un archivo .env si existe, sin sobreescribir las ya definidas."""
    if not env_path.is_file():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


import secrets

def _ensure_secrets_exist(env_path: Path) -> None:
    """
    Verifica que las claves criptográficas indispensables existan.
    Si faltan en el entorno local, genera claves CSPRNG de alta entropía (256 bits)
    y las persiste en .env para garantizar que nunca se utilicen valores predeterminados conocidos.
    """
    keys_needed = [
        ("APP_SECRET_KEY", 32),
        ("APP_ENCRYPTION_KEY", 32),
        ("BLIND_INDEX_KEY", 32),
        ("BACKUP_ENCRYPTION_KEY", 32),
        ("WHATSAPP_BRIDGE_TOKEN", 32),
    ]

    new_entries = []
    for key, length in keys_needed:
        val = os.getenv(key, "").strip()
        if not val or "insecure" in val.lower() or "change_in_prod" in val.lower() or "default" in val.lower():
            generated_key = secrets.token_urlsafe(length)
            os.environ[key] = generated_key
            new_entries.append(f"{key}={generated_key}")

    if new_entries and env_path.parent.exists():
        try:
            with open(env_path, "a", encoding="utf-8") as f:
                f.write("\n# Claves Criptográficas Generadas Automáticamente (CSPRNG 256-bit)\n")
                for entry in new_entries:
                    f.write(f"{entry}\n")
        except Exception:
            pass


# Cargar .env desde la raíz del proyecto si existe
_BASE_DIR = Path(__file__).resolve().parent.parent
_ENV_PATH = _BASE_DIR / ".env"
_load_env_file(_ENV_PATH)
_ensure_secrets_exist(_ENV_PATH)



@dataclass
class AppConfig:
    """Configuración principal de la aplicación."""
    
    # Raíz del proyecto
    base_dir: Path = field(default_factory=lambda: _BASE_DIR)
    
    # Entorno
    app_env: str = field(
        default_factory=lambda: os.getenv("APP_ENV", "development").lower()
    )
    
    # Rutas de Bases de Datos y Motor Relacional
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/consultora_crm.db")
    )
    leads_excel_path: Path = field(
        default_factory=lambda: Path(os.getenv("LEADS_EXCEL_PATH", "Leeds orden.xlsx"))
    )
    commercial_excel_path: Path = field(
        default_factory=lambda: Path(os.getenv("COMMERCIAL_EXCEL_PATH", "Comercial.xlsx"))
    )
    
    # Seguridad Criptográfica y Secretos
    app_secret_key: str = field(
        default_factory=lambda: os.getenv("APP_SECRET_KEY", "insecure_dev_secret_key_change_in_prod")
    )
    app_encryption_key: str = field(
        default_factory=lambda: os.getenv("APP_ENCRYPTION_KEY", "")
    )
    blind_index_key: str = field(
        default_factory=lambda: os.getenv("BLIND_INDEX_KEY", "")
    )
    backup_encryption_key: str = field(
        default_factory=lambda: os.getenv("BACKUP_ENCRYPTION_KEY", "")
    )
    backup_encryption_enabled: bool = field(
        default_factory=lambda: os.getenv("BACKUP_ENCRYPTION_ENABLED", "true").lower() in ("1", "true", "yes")
    )
    
    # Control de Autenticación y Sembrado
    auth_enabled: bool = field(
        default_factory=lambda: os.getenv("AUTH_ENABLED", "false").lower() in ("1", "true", "yes")
    )
    auto_seed_default_users: bool = field(
        default_factory=lambda: os.getenv("AUTO_SEED_DEFAULT_USERS", "false").lower() in ("1", "true", "yes")
    )
    
    # Airtable Autenticación Cloud & 2FA
    airtable_api_key: str = field(
        default_factory=lambda: os.getenv("AIRTABLE_API_KEY", "").strip()
    )
    airtable_base_id: str = field(
        default_factory=lambda: os.getenv("AIRTABLE_BASE_ID", "appF1ytqDgJAN0yE8").strip()
    )
    airtable_table_name: str = field(
        default_factory=lambda: os.getenv("AIRTABLE_TABLE_NAME", "Table 1").strip()
    )
    airtable_generic_password: str = field(
        default_factory=lambda: os.getenv("AIRTABLE_GENERIC_PASSWORD", "Consultora2026!").strip()
    )
    airtable_auth_enabled: bool = field(
        default_factory=lambda: os.getenv("AIRTABLE_AUTH_ENABLED", "true").lower() in ("1", "true", "yes")
    )

    # WhatsApp & Integración
    whatsapp_bridge_url: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:3001")
    )
    whatsapp_bridge_token: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_BRIDGE_TOKEN", "")
    )
    whatsapp_config_path: Path = field(
        default_factory=lambda: Path(os.getenv("WHATSAPP_CONFIG_PATH", "whatsapp_config.json"))
    )
    whatsapp_inbox_dir: Path = field(
        default_factory=lambda: Path(os.getenv("WHATSAPP_INBOX_DIR", "whatsapp_inbox"))
    )
    whatsapp_sync_state_path: Path = field(
        default_factory=lambda: Path(os.getenv("WHATSAPP_SYNC_STATE_PATH", "whatsapp_sync_state.json"))
    )
    
    # Meta / WhatsApp Gateway Tokens
    whatsapp_meta_access_token: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_META_ACCESS_TOKEN", "")
    )
    meta_phone_number_id: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_META_PHONE_NUMBER_ID", "")
    )
    meta_verify_token: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_META_VERIFY_TOKEN", "")
    )
    gateway_api_key: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_GATEWAY_API_KEY", "")
    )
    
    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    log_dir: Path = field(
        default_factory=lambda: Path(os.getenv("LOG_DIR", "logs"))
    )
    log_file_name: str = field(
        default_factory=lambda: os.getenv("LOG_FILE_NAME", "app.log")
    )
    log_max_bytes: int = field(
        default_factory=lambda: int(os.getenv("LOG_MAX_BYTES", "5242880"))
    )
    log_backup_count: int = field(
        default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", "5"))
    )
    
    # Backups y Recuperación
    backup_dir: Path = field(
        default_factory=lambda: Path(os.getenv("BACKUP_DIR", "backups"))
    )
    auto_backup_enabled: bool = field(
        default_factory=lambda: os.getenv("AUTO_BACKUP_ENABLED", "true").lower() in ("1", "true", "yes")
    )
    max_backups_retained: int = field(
        default_factory=lambda: int(os.getenv("MAX_BACKUPS_RETAINED", "20"))
    )

    # Inteligencia Artificial (API LLM compatible OpenAI / REST)
    llm_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", os.getenv("LLM_API_KEY", "")).strip()
    )
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")).strip()
    )
    llm_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    )
    llm_enabled: bool = field(
        default_factory=lambda: os.getenv("LLM_ENABLED", "true").lower() in ("1", "true", "yes")
    )

    # Meta Ads Marketing API (Read-Only)
    meta_ads_enabled: bool = field(
        default_factory=lambda: os.getenv("META_ADS_ENABLED", "true").lower() in ("1", "true", "yes")
    )
    meta_ad_account_id: str = field(
        default_factory=lambda: os.getenv("META_AD_ACCOUNT_ID", "").strip()
    )
    meta_access_token: str = field(
        default_factory=lambda: os.getenv("META_ACCESS_TOKEN", "").strip()
    )
    meta_api_version: str = field(
        default_factory=lambda: os.getenv("META_API_VERSION", "v21.0").strip()
    )

    @property
    def llm_provider_name(self) -> str:
        url_low = (self.llm_base_url or "").lower()
        key_low = (self.llm_api_key or "").lower()
        if "groq.com" in url_low or key_low.startswith("gsk_"):
            return "Groq Cloud (LPU)"
        elif "openrouter.ai" in url_low:
            return "OpenRouter"
        elif "deepseek" in url_low:
            return "DeepSeek API"
        elif "anthropic" in url_low:
            return "Anthropic"
        elif "openai.com" in url_low:
            return "OpenAI"
        elif "localhost" in url_low or "127.0.0.1" in url_low:
            return "Local LLM (Ollama)"
        return "API OpenAI Compatible"

    # Propiedades de compatibilidad con código anterior
    @property
    def ollama_base_url(self) -> str:
        return self.llm_base_url


    @property
    def ollama_model(self) -> str:
        return self.llm_model

    @property
    def ollama_fallback_model(self) -> str:
        return self.llm_model

    @property
    def ollama_timeout_seconds(self) -> int:
        return self.llm_timeout_seconds

    @property
    def ollama_enabled(self) -> bool:
        return self.llm_enabled

    @property
    def is_production(self) -> bool:
        return self.app_env in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return self.app_env in ("development", "dev", "local")

    @property
    def is_testing(self) -> bool:
        return self.app_env in ("testing", "test")

    def get_absolute_path(self, path: Path | str) -> Path:
        """Devuelve la ruta absoluta relativa al directorio base del proyecto."""
        p = Path(path)
        return p if p.is_absolute() else self.base_dir / p

    def resolve_leads_path(self, custom_path: Optional[Path | str] = None) -> Path:
        """Resuelve la ruta efectiva para la base de Leads con fallback seguro."""
        if custom_path:
            p = Path(custom_path)
            if p.exists():
                return p
        
        # 1. Ruta configurada
        cfg_path = self.get_absolute_path(self.leads_excel_path)
        if cfg_path.exists():
            return cfg_path
            
        # 2. data/Leeds orden.xlsx
        data_path = self.base_dir / "data" / "Leeds orden.xlsx"
        if data_path.exists():
            return data_path
            
        # 3. data/sample_leads.xlsx
        sample_path = self.base_dir / "data" / "sample_leads.xlsx"
        if sample_path.exists():
            return sample_path

        return cfg_path

    def resolve_commercial_path(self, custom_path: Optional[Path | str] = None) -> Path:
        """Resuelve la ruta efectiva para la base Comercial con fallback seguro."""
        if custom_path:
            p = Path(custom_path)
            if p.exists():
                return p

        cfg_path = self.get_absolute_path(self.commercial_excel_path)
        if cfg_path.exists():
            return cfg_path

        data_path = self.base_dir / "data" / "Comercial.xlsx"
        if data_path.exists():
            return data_path

        sample_path = self.base_dir / "data" / "sample_comercial.xlsx"
        if sample_path.exists():
            return sample_path

        return cfg_path

    def validate_production_readiness(self) -> None:
        """
        Valida rigurosamente que todas las claves criptográficas y políticas de seguridad
        estén correctamente configuradas para producción. Aborta con RuntimeError si encuentra vulnerabilidades.
        """
        if not self.is_production:
            return

        required_secrets = {
            "APP_SECRET_KEY": self.app_secret_key,
            "APP_ENCRYPTION_KEY": self.app_encryption_key,
            "BLIND_INDEX_KEY": self.blind_index_key,
            "BACKUP_ENCRYPTION_KEY": self.backup_encryption_key,
            "WHATSAPP_BRIDGE_TOKEN": self.whatsapp_bridge_token,
        }

        seen_values = set()
        for name, val in required_secrets.items():
            if not val or not isinstance(val, str):
                raise RuntimeError(f"SEGURIDAD CRÍTICA: '{name}' no está configurada en producción.")
            val_clean = val.strip()
            if len(val_clean) < 32:
                raise RuntimeError(f"SEGURIDAD CRÍTICA: '{name}' es demasiado corta ({len(val_clean)} caracteres, mínimo 32).")
            if any(bad in val_clean.lower() for bad in ("insecure", "change_in_prod", "default_key")):
                raise RuntimeError(f"SEGURIDAD CRÍTICA: '{name}' contiene valores de desarrollo predeterminados conocidos.")
            if val_clean in seen_values:
                raise RuntimeError(f"SEGURIDAD CRÍTICA: Reutilización de clave detectada en '{name}'. Cada secreto debe ser único.")
            seen_values.add(val_clean)



# Instancia singleton accesible globalmente
_config_instance: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """Obtiene o recarga la configuración global de la aplicación."""
    global _config_instance
    if _config_instance is None or reload:
        _load_env_file(_BASE_DIR / ".env")
        _config_instance = AppConfig()
    return _config_instance
