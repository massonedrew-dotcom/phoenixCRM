import logging

from httpx import ASGITransport, AsyncClient

from app.core.logging import JsonFormatter
from app.main import create_app
from tests.conftest import make_settings
from tests.factories import TeamHeaders

UNREACHABLE_DATABASE_URL = "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/missing"


async def test_health_reports_ok_when_database_is_reachable(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


async def test_health_returns_503_when_database_is_unreachable() -> None:
    app = create_app(make_settings(UNREACHABLE_DATABASE_URL))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.get("/api/v1/health")
    await app.state.engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error"}


async def test_unknown_route_uses_error_format(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nowhere")

    assert response.status_code == 404
    assert response.json() == {"detail": "Не найдено", "code": "NOT_FOUND"}


async def test_client_config_requires_auth_and_exposes_rate(
    client: AsyncClient, headers: TeamHeaders
) -> None:
    assert (await client.get("/api/v1/config")).status_code == 401

    response = await client.get("/api/v1/config", headers=headers.agent)

    assert response.json() == {
        "uzs_per_ue": "12000",
        "max_photo_mb": 15,
        "max_video_mb": 200,
        "time_zone": "Asia/Tashkent",
    }


def test_json_log_formatter_writes_one_object_per_record() -> None:
    record = logging.makeLogRecord(
        {"name": "app", "levelname": "ERROR", "msg": "сбой %s", "args": ("x",), "path": "/api"}
    )

    line = JsonFormatter().format(record)

    assert '"message": "сбой x"' in line
    assert '"extra": {"path": "/api"}' in line
