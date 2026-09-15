from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

API_PREFIX = "/api/v1"


class Settings(BaseSettings):
    """Application settings. Every field maps to a required environment variable."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str
    jwt_secret: SecretStr
    access_token_minutes: int
    refresh_token_days: int
    storage_backend: Literal["local", "s3"]
    media_root: Path
    max_photo_mb: int
    max_video_mb: int
    cors_origins: Annotated[list[str], NoDecode]
    uzs_per_ue: Decimal
    tz: str

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("tz")
    @classmethod
    def validate_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown time zone: {value}") from exc
        return value

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
