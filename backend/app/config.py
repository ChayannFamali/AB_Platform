import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
    )

    # Postgres компоненты — из них строим URL
    postgres_user:     str = "abplatform"
    postgres_password: str = "secret"
    postgres_db:       str = "abplatform"
    postgres_host:     str = "localhost"   # Docker переопределит на "postgres"
    postgres_port:     int = 5432

    # Redis
    redis_url: str = "redis://localhost:6379"

    # App
    secret_key:   str = "changeme"
    environment:  str = "development"

    # AI
    ai_provider:    str = "disabled"
    ollama_url:     str = "http://localhost:11434"
    ollama_model:   str = "llama3.2:latest"
    openai_api_key: str = ""
    openai_model:   str = "gpt-4o-mini"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
