from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from bgw.field import DEFAULT_PRIME


class CoordinatorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COORDINATOR_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+psycopg://precision:precision@localhost:5432/precision_mpc"
    )
    jwt_secret: str = "change-this-development-secret"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480
    mpc_service_token: str = "change-me-in-production"
    hospital_timeout_seconds: float = 15.0
    hospital_public_urls: dict[int, str] = {
        1: "http://localhost:8101",
        2: "http://localhost:8102",
        3: "http://localhost:8103",
        4: "http://localhost:8104",
        5: "http://localhost:8105",
        6: "http://localhost:8106",
    }
    threshold: int = 1
    prime: int = DEFAULT_PRIME
    minimum_cohort_size: int = 10
    auto_create_schema: bool = True
    auto_seed: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> CoordinatorSettings:
    return CoordinatorSettings()
