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
    # Plantilla de la URL de clonado ({org} y {repo}). El modo demo la apunta a
    # orígenes git locales (file://). Ver docs/06-datos-de-prueba.md.
    git_clone_url_template: str = "https://github.com/{org}/{repo}.git"

    # Agente de feedback (análisis local)
    llm_provider: str = "mock"  # mock | openai | anthropic | local
    llm_api_key: SecretStr | None = None
    agent_max_diff_chars: int = 20_000

    # Agente tutor (RAG). Proveedor remoto por API de pago; al proveedor solo llega
    # texto ya seudonimizado y limpio. Sin clave o si falla, responde el mock.
    tutor_provider: str = "mock"  # mock | anthropic | openai_compatible
    tutor_model: str = "claude-opus-5-5"  # p. ej. claude-haiku-5-5 (más barato) o el del proveedor
    tutor_api_key: SecretStr | None = None
    tutor_base_url: str | None = None  # obligatorio en openai_compatible (…/v1)
    tutor_effort: str = "low"  # solo anthropic: low | medium | high ("" = no enviarlo)
    tutor_max_tokens: int = 4000
    tutor_timeout: float = 60.0
    tutor_max_questions_per_hour: int = 30  # por usuario; 0 = sin límite

    # Atajo de desarrollo: aceptar ZUZENAA_GITHUB_TOKEN si no hay sesión.
    allow_env_token: bool = False
    github_token: SecretStr | None = None

    # --- Datos de prueba (modo demo) ---
    # Emula Classroom 50 con un dataset ficticio (org ikastola-demo). NUNCA en
    # producción: ver docs/06-datos-de-prueba.md.
    demo_mode: bool = False

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
