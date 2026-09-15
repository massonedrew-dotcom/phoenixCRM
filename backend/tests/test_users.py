import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditAction, AuditEntity
from app.services import users as users_service
from tests import factories
from tests.factories import Team, TeamHeaders

NEW_USER = {
    "username": "NewAgent",
    "full_name": "Новый Агент",
    "password": "long-enough-1",
    "role": "agent",
}


@pytest.mark.parametrize(
    ("role", "expected"),
    [("admin", 200), ("head", 200), ("agent", 403)],
)
async def test_list_users_permissions(
    client: AsyncClient, headers: TeamHeaders, role: str, expected: int
) -> None:
    response = await client.get("/api/v1/users", headers=headers.for_role(role))

    assert response.status_code == expected
    if expected == 200:
        assert all("password" not in key for item in response.json() for key in item)


@pytest.mark.parametrize(("role", "expected"), [("admin", 201), ("head", 403), ("agent", 403)])
async def test_create_user_permissions(
    client: AsyncClient, headers: TeamHeaders, role: str, expected: int
) -> None:
    response = await client.post("/api/v1/users", json=NEW_USER, headers=headers.for_role(role))

    assert response.status_code == expected


async def test_unauthenticated_requests_are_rejected(client: AsyncClient) -> None:
    for method, url in [
        ("GET", "/api/v1/users"),
        ("POST", "/api/v1/users"),
        ("GET", "/api/v1/realtors"),
        ("GET", "/api/v1/districts"),
        ("GET", "/api/v1/properties"),
        ("GET", "/api/v1/audit"),
    ]:
        response = await client.request(method, url, json={})
        assert response.status_code == 401, url


async def test_created_user_is_audited_and_username_lowercased(
    client: AsyncClient, session: AsyncSession, headers: TeamHeaders, users: Team
) -> None:
    response = await client.post("/api/v1/users", json=NEW_USER, headers=headers.admin)

    body = response.json()
    assert body["username"] == "newagent"
    rows = await factories.audit_rows(session, AuditEntity.USER, body["id"])
    assert {(r.field, r.old_value, r.new_value) for r in rows} == {
        ("username", None, "newagent"),
        ("full_name", None, "Новый Агент"),
        ("role", None, "agent"),
        ("is_active", None, "true"),
    }
    assert all(r.action == AuditAction.CREATE and r.user_id == users.admin.id for r in rows)
    assert all("argon2" not in (r.new_value or "") for r in rows)


async def test_duplicate_username_is_conflict(client: AsyncClient, headers: TeamHeaders) -> None:
    payload = {**NEW_USER, "username": "agent"}

    response = await client.post("/api/v1/users", json=payload, headers=headers.admin)

    assert response.status_code == 409
    assert response.json()["code"] == "USERNAME_TAKEN"


async def test_admin_updates_user_with_audit(
    client: AsyncClient, session: AsyncSession, headers: TeamHeaders, users: Team
) -> None:
    response = await client.patch(
        f"/api/v1/users/{users.agent.id}",
        json={"full_name": "Агент Переименованный", "role": "head"},
        headers=headers.admin,
    )

    assert response.status_code == 200
    rows = await factories.audit_rows(session, AuditEntity.USER, users.agent.id)
    assert {(r.field, r.old_value, r.new_value) for r in rows} == {
        ("full_name", "Агент Первый", "Агент Переименованный"),
        ("role", "agent", "head"),
    }


@pytest.mark.parametrize("patch", [{"role": "agent"}, {"is_active": False}])
async def test_admin_cannot_demote_or_deactivate_self(
    client: AsyncClient, headers: TeamHeaders, users: Team, patch: dict[str, object]
) -> None:
    response = await client.patch(
        f"/api/v1/users/{users.admin.id}", json=patch, headers=headers.admin
    )

    assert response.status_code == 403
    assert response.json()["code"] == "SELF_MODIFICATION"


async def test_reset_password_revokes_sessions_and_allows_new_login(
    client: AsyncClient, headers: TeamHeaders, users: Team
) -> None:
    response = await client.post(
        f"/api/v1/users/{users.agent.id}/reset-password",
        json={"new_password": "brand-new-pass"},
        headers=headers.admin,
    )

    assert response.status_code == 204
    assert (await client.get("/api/v1/auth/me", headers=headers.agent)).status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"username": "agent", "password": "brand-new-pass"}
    )
    assert login.status_code == 200


@pytest.mark.parametrize("role", ["head", "agent"])
async def test_only_admin_resets_passwords(
    client: AsyncClient, headers: TeamHeaders, users: Team, role: str
) -> None:
    response = await client.post(
        f"/api/v1/users/{users.other_agent.id}/reset-password",
        json={"new_password": "brand-new-pass"},
        headers=headers.for_role(role),
    )

    assert response.status_code == 403


async def test_realtors_are_visible_to_agents(client: AsyncClient, headers: TeamHeaders) -> None:
    response = await client.get("/api/v1/realtors", headers=headers.agent)

    assert response.status_code == 200
    assert {item["full_name"] for item in response.json()} >= {"Агент Первый", "Агент Второй"}
    assert set(response.json()[0]) == {"id", "full_name", "is_active"}


async def test_create_first_admin_service(session: AsyncSession) -> None:
    admin = await users_service.create_first_admin(
        session, username="root", full_name="Первый Админ", password="first-admin-pass"
    )

    assert admin.role == "admin"
    rows = await factories.audit_rows(session, AuditEntity.USER, admin.id)
    assert rows and all(row.user_id == admin.id for row in rows)
