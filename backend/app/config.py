from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_PLACEHOLDERS = {"development-only-change-me", "replace-with-a-long-random-secret", "replace-with-a-separate-32-byte-key"}


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "development-only-change-me"
    token_encryption_key: str = "development-only-change-me"
    # Clave que el panel envía en la cabecera X-Admin-Key. Vacía = API administrativa deshabilitada.
    admin_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./inventory.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    # URL pública del panel; el callback OAuth redirige aquí al terminar.
    frontend_url: str = "http://localhost:5173"

    # Tiendanube (https://tiendanube.github.io/api-documentation/authentication)
    tiendanube_app_id: str = ""
    tiendanube_client_secret: str = ""
    tiendanube_auth_base: str = "https://www.tiendanube.com"
    tiendanube_api_base: str = "https://api.tiendanube.com/v1"
    # La API exige un User-Agent que identifique la app y un contacto; sin él responde 400.
    tiendanube_user_agent: str = "Inventory Sync (contacto@example.com)"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
