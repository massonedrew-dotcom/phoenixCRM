from datetime import UTC, datetime, timedelta

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import AuditAction, AuditEntity, Role
from app.core.security import create_token
from app.models import AuditLog, AuthSession
from tests import factories
from tests.factories import PASSWORD, Team, TeamHeaders


async def login(client: AsyncClient, username: str, password: str = PASSWORD) -> Response:
    return await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


async def test_login_returns_tokens_and_user(
    client: AsyncClient, session: AsyncSession, users: Team
) -> None:
    response = await login(client, "agent")

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": str(users.agent.id),
        "username": "agent",
        "full_name": "Агент Первый",
        "role": "agent",
        "is_active": True,
        "created_at": body["user"]["created_at"],
    }
    assert "password" not in str(body["user"])
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "agent"

    rows = await factories.audit_rows(session, AuditEntity.USER, users.agent.id)
    assert [(row.action, row.user_id, str(row.ip)) for row in rows] == [
        (AuditAction.LOGIN, users.agent.id, "127.0.0.1")
    ]


async def test_login_username_is_case_insensitive(client: AsyncClient, users: Team) -> None:
    response = await login(client, "  AGENT ")

    assert response.status_code == 200


async def test_wrong_password_is_rejected_and_audited(
    client: AsyncClient, session: AsyncSession, users: Team
) -> None:
    response = await login(client, "agent", "wrong-password")

    assert response.status_code == 401
    assert response.json() == {"detail": "Неверный логин или пароль", "code": "INVALID_CREDENTIALS"}
    rows = await factories.audit_rows(session, AuditEntity.USER, users.agent.id)
    assert len(rows) == 1
    assert rows[0].action == AuditAction.LOGIN_FAILED
    assert rows[0].user_id is None
    assert (rows[0].field, rows[0].new_value) == ("username", "agent")


async def test_unknown_username_is_audited_without_entity(
    client: AsyncClient, session: AsyncSession, users: Team
) -> None:
    response = await login(client, "ghost")

    assert response.status_code == 401
    row = await session.scalar(
        select(AuditLog).where(
            AuditLog.action == AuditAction.LOGIN_FAILED, AuditLog.new_value == "ghost"
        )
    )
    assert row is not None
    assert row.entity_id is None


async def test_inactive_user_cannot_log_in(client: AsyncClient, session: AsyncSession) -> None:
    await factories.create_user(session, Role.AGENT, "retired", "Бывший Агент", is_active=False)

    response = await login(client, "retired")

    assert response.status_code == 401


async def test_expired_access_token_is_rejected(
    client: AsyncClient, session: AsyncSession, settings: Settings, users: Team
) -> None:
    auth_session = AuthSession(
        user_id=users.agent.id, expires_at=datetime.now(UTC) + timedelta(days=1)
    )
    session.add(auth_session)
    await session.flush()
    issued = datetime.now(UTC) - timedelta(minutes=settings.access_token_minutes + 1)
    token = create_token(
        settings,
        user_id=users.agent.id,
        session_id=auth_session.id,
        token_type="access",
        now=issued,
    )

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_missing_or_garbage_token_is_rejected(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    garbage = {"Authorization": "Bearer not-a-jwt"}
    assert (await client.get("/api/v1/auth/me", headers=garbage)).status_code == 401


async def test_refresh_issues_new_access_token(client: AsyncClient, users: Team) -> None:
    tokens = (await login(client, "head")).json()

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    new_access = response.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.json()["username"] == "head"


async def test_access_token_cannot_be_used_as_refresh_token(
    client: AsyncClient, users: Team
) -> None:
    tokens = (await login(client, "head")).json()

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert response.status_code == 401


async def test_logout_revokes_session(
    client: AsyncClient, session: AsyncSession, users: Team
) -> None:
    tokens = (await login(client, "agent")).json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}

    assert (await client.post("/api/v1/auth/logout", headers=auth)).status_code == 204

    assert (await client.get("/api/v1/auth/me", headers=auth)).status_code == 401
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401
    actions = [
        r.action for r in await factories.audit_rows(session, AuditEntity.USER, users.agent.id)
    ]
    assert actions == [AuditAction.LOGIN, AuditAction.LOGOUT]


async def test_deactivation_invalidates_existing_tokens(
    client: AsyncClient, users: Team, headers: TeamHeaders
) -> None:
    response = await client.patch(
        f"/api/v1/users/{users.agent.id}", json={"is_active": False}, headers=headers.admin
    )
    assert response.status_code == 200

    assert (await client.get("/api/v1/auth/me", headers=headers.agent)).status_code == 401


async def test_change_password_keeps_current_session_and_revokes_others(
    client: AsyncClient, session: AsyncSession, users: Team
) -> None:
    first = (await login(client, "agent")).json()
    second = (await login(client, "agent")).json()
    current = {"Authorization": f"Bearer {first['access_token']}"}

    response = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": PASSWORD, "new_password": "new-password-123"},
        headers=current,
    )

    assert response.status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=current)).status_code == 200
    other = {"Authorization": f"Bearer {second['access_token']}"}
    assert (await client.get("/api/v1/auth/me", headers=other)).status_code == 401
    assert (await login(client, "agent", "new-password-123")).status_code == 200

    rows = await factories.audit_rows(session, AuditEntity.USER, users.agent.id)
    password_rows = [row for row in rows if row.field == "password"]
    assert [(r.action, r.old_value, r.new_value) for r in password_rows] == [
        (AuditAction.UPDATE, None, None)
    ]


async def test_change_password_requires_old_password(
    client: AsyncClient, headers: TeamHeaders
) -> None:
    response = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "wrong-one", "new_password": "new-password-123"},
        headers=headers.agent,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PASSWORD"


async def test_short_new_password_is_rejected(client: AsyncClient, headers: TeamHeaders) -> None:
    response = await client.post(
        "/api/v1/auth/change-password",
        json={"old_password": PASSWORD, "new_password": "short"},
        headers=headers.agent,
    )

    assert response.status_code == 422


async def test_login_is_rate_limited_per_ip(client: AsyncClient, users: Team) -> None:
    for _ in range(10):
        assert (await login(client, "agent", "wrong-password")).status_code == 401

    response = await login(client, "agent")

    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"
