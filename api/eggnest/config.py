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
    # Comparison endpoints run one full simulation per state/age/allocation,
    # so they cap paths-per-run to bound a single request's CPU cost.
    comparison_max_simulations: int = 5_000
    simulation_job_workers: int = 2
    simulation_job_ttl_seconds: int = 3_600
    simulation_job_max_records: int = 100

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
