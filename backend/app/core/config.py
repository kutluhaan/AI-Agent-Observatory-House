from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    app_secret_key: str = "changeme"
    frontend_url: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://observatory:changeme@postgres:5432/observatory"

    # Redis
    redis_url: str = "redis://redis:6379"

    # ClickHouse
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 9000  # native protocol (compose CLICKHOUSE_PORT)
    clickhouse_http_port: int = 8123  # clickhouse-connect HTTP arabirimi (M8)
    clickhouse_db: str = "observatory"
    clickhouse_user: str = "observatory"
    clickhouse_password: str = "changeme"

    # Tracing (M8)
    trace_retention_days: int = 30

    # JWT
    jwt_private_key: str = ""
    jwt_public_key: str = ""
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Email
    resend_api_key: str = ""
    email_from: str = "noreply@yourdomain.com"

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://host.docker.internal:11434"

    # F3: Self-hosted / OpenAI-uyumlu custom model (env > Providers UI override)
    #   CUSTOM_BASE_URL: OpenAI-uyumlu kök (ör. http://host.docker.internal:8000/v1)
    #   CUSTOM_API_KEY:  endpoint istiyorsa; istemiyorsa boş bırak
    custom_base_url: str = ""
    custom_api_key: str = ""

    # M12: Research tools
    tavily_api_key: str = ""

    # G1: Gmail entegrasyonu — Google OAuth (kullanıcı kendi Gmail'ini bağlar)
    #   Google Cloud Console > OAuth client (Web app)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/connections/google/callback"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
