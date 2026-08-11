from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bgw.field import DEFAULT_PRIME


class HospitalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOSPITAL_",
        env_file=".env",
        extra="ignore",
    )

    participant_id: int = 1
    organization_name: str = "Hospital A"
    participant_ids: list[int] = [1, 2, 3]
    threshold: int = 1
    prime: int = DEFAULT_PRIME

    database_url: str = (
        "postgresql+psycopg://precision:precision@localhost:5432/hospital"
    )
    service_token: str = "change-me-in-production"
    local_access_secret: str = "change-this-development-secret"
    local_access_algorithm: str = "HS256"
    cors_origins: list[str] = ["http://localhost:5174"]
    peer_urls: dict[int, str] = {
        1: "http://localhost:8101",
        2: "http://localhost:8102",
        3: "http://localhost:8103",
    }
    http_timeout_seconds: float = 10.0

    auto_create_schema: bool = True
    auto_seed: bool = False
    synthetic_patient_count: int = 500
    synthetic_seed: int = 101

    @field_validator("participant_ids")
    @classmethod
    def validate_ids(cls, value: list[int]) -> list[int]:
        if not value or len(value) != len(set(value)):
            raise ValueError("participant_ids must be non-empty and unique")
        if any(pid <= 0 for pid in value):
            raise ValueError("participant ids must be positive Shamir x-coordinates")
        return value

    @model_validator(mode="after")
    def validate_bgw_configuration(self) -> "HospitalSettings":
        if self.participant_id not in self.participant_ids:
            raise ValueError("participant_id must be present in participant_ids")
        if len(self.participant_ids) < 2 * self.threshold + 1:
            raise ValueError("BGW multiplication requires n >= 2t + 1")
        missing = set(self.participant_ids) - set(self.peer_urls)
        if missing:
            raise ValueError(f"peer_urls is missing participants: {sorted(missing)}")
        return self


@lru_cache
def get_settings() -> HospitalSettings:
    return HospitalSettings()
