from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ShramRakshak API"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    # SQLite keeps local development and automated tests self-contained. Set this
    # to the Supabase PostgreSQL connection string outside local development.
    database_url: str = "sqlite:///./shramrakshak.db"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    # Expo Go uses a runtime host, so this is an explicit pattern rather than
    # a fixed per-device URL. The backend further restricts this to local hosts.
    supabase_email_redirect_url: str = "exp://**/--/auth/callback"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8081",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def normalized_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
