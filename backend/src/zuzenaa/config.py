"""Application settings, loaded from the environment / .env.

All variables use the ``ZUZENAA_`` prefix, e.g. ``ZUZENAA_DEBUG=true``.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ZUZENAA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ZuzenAA"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./zuzenaa.db"

    # URLs de la app (para OAuth y redirecciones)
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8080"

    # Web de Classroom 50 (para enlaces profundos; configurable si es self-hosted)
    classroom50_url: str = "https://classroom50.org"

    # Clave de servidor: deriva la clave de cifrado de tokens y firma de estado.
    # En producción, definir por entorno.
    secret_key: SecretStr = SecretStr("dev-insecure-change-me")

    # Sesiones
    session_cookie_name: str = "zuzenaa_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 14  # 14 días
    cookie_secure: bool = False

    # GitHub OAuth App
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: SecretStr | None = None
    github_oauth_scopes: str = "repo workflow read:org admin:org"

    # GitHub CLI (gh) — solo lectura de Classroom 50
    gh_binary: str = "gh"
    gh_timeout: float = 60.0

    # Almacenamiento local de repos y snapshots (volumen del servidor)
    data_root: str = "/data"
    git_clone_depth: int = 0  # 0 = historia completa; >0 = clon superficial
    git_timeout: float = 300.0

    # Agente de feedback (análisis local)
    llm_provider: str = "mock"  # mock | openai | anthropic | local
    llm_api_key: SecretStr | None = None
    agent_max_diff_chars: int = 20_000

    # Atajo de desarrollo: aceptar ZUZENAA_GITHUB_TOKEN si no hay sesión.
    allow_env_token: bool = False
    github_token: SecretStr | None = None

    @property
    def oauth_redirect_uri(self) -> str:
        return f"{self.backend_url.rstrip('/')}/auth/callback"

    @property
    def oauth_configured(self) -> bool:
        return (
            self.github_oauth_client_id is not None
            and self.github_oauth_client_secret is not None
        )


settings = Settings()
