"""Configuration settings for FinSim API."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Simulation defaults
    default_n_simulations: int = 10_000
    max_n_simulations: int = 100_000

    # CORS — production origins only; localhost is handled via regex in main.py
    cors_origins: list[str] = [
        "https://app.eggnest.co",
        "https://eggnest.co",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
