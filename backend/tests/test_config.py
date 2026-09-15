from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://user:pass@db:5432/crm",
    "JWT_SECRET": "secret",
    "ACCESS_TOKEN_MINUTES": "30",
    "REFRESH_TOKEN_DAYS": "14",
    "STORAGE_BACKEND": "local",
    "MEDIA_ROOT": "/data/media",
    "MAX_PHOTO_MB": "15",
    "MAX_VIDEO_MB": "200",
    "CORS_ORIGINS": "http://localhost, https://crm.example.uz",
    "UZS_PER_UE": "12000",
    "TZ": "Asia/Tashkent",
}


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_settings_are_read_from_environment(environment: pytest.MonkeyPatch) -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.cors_origins == ["http://localhost", "https://crm.example.uz"]
    assert settings.max_video_mb == 200
    assert settings.uzs_per_ue == Decimal(12000)
    assert settings.zone.key == "Asia/Tashkent"


@pytest.mark.parametrize("missing", ["JWT_SECRET", "UZS_PER_UE", "DATABASE_URL"])
def test_missing_required_variable_is_rejected(
    environment: pytest.MonkeyPatch, missing: str
) -> None:
    environment.delenv(missing)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_unknown_time_zone_is_rejected(environment: pytest.MonkeyPatch) -> None:
    environment.setenv("TZ", "Mars/Olympus")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
