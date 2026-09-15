import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.db import create_engine
from app.core.dependencies import get_session
from app.core.enums import Role
from app.main import create_app
from app.models import District
from tests import factories
from tests.factories import Team, TeamHeaders

BACKEND_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "postgres:16"


def make_settings(database_url: str, media_root: Path | None = None) -> Settings:
    return Settings(
        database_url=database_url,
        jwt_secret=SecretStr("test-secret-key-with-enough-length-for-hs256"),
        access_token_minutes=30,
        refresh_token_days=14,
        storage_backend="local",
        media_root=media_root or Path("media-not-configured"),
        max_photo_mb=15,
        max_video_mb=200,
        cors_origins=["http://test"],
        uzs_per_ue=Decimal(12000),
        tz="Asia/Tashkent",
    )


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _admin_database_url() -> str | None:
    """A PostgreSQL server for tests when Docker is not available (DECISIONS.md D25)."""
    if url := os.environ.get("TEST_DATABASE_ADMIN_URL"):
        return url
    return dotenv_values(BACKEND_DIR / ".env.test").get("TEST_DATABASE_ADMIN_URL")


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """URL of a fresh, empty database that exists only for this test session."""
    admin_url = _admin_database_url()
    if admin_url is None:
        from testcontainers.community.postgres import PostgresContainer

        with PostgresContainer(POSTGRES_IMAGE, driver="asyncpg") as postgres:
            yield postgres.get_connection_url()
        return

    name = f"crm_test_{uuid.uuid4().hex}"

    async def execute(statement: str) -> None:
        engine = create_async_engine(admin_url, poolclass=NullPool)
        async with engine.connect() as connection:
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            await connection.execute(text(statement))
        await engine.dispose()

    # The database name is generated above, never taken from input.
    asyncio.run(execute(f"CREATE DATABASE \"{name}\" ENCODING 'UTF8' TEMPLATE template0"))
    try:
        yield make_url(admin_url).set(database=name).render_as_string(hide_password=False)
    finally:
        asyncio.run(execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@pytest.fixture(scope="session")
def database_url(postgres_url: str) -> str:
    """The session database migrated to the latest revision."""
    command.upgrade(alembic_config(postgres_url), "head")
    return postgres_url


@pytest.fixture
async def db_connection(database_url: str) -> AsyncIterator[AsyncConnection]:
    """A connection whose outer transaction is rolled back after each test."""
    engine = create_engine(make_settings(database_url))
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()
    await engine.dispose()


def _bound_session(connection: AsyncConnection) -> AsyncSession:
    # Commits inside services release a savepoint; the outer transaction still rolls back.
    return AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest.fixture
async def session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with _bound_session(db_connection) as db_session:
        yield db_session


@pytest.fixture
def media_root(tmp_path: Path) -> Path:
    root = tmp_path / "media"
    root.mkdir()
    return root


@pytest.fixture
def app(database_url: str, db_connection: AsyncConnection, media_root: Path) -> FastAPI:
    application = create_app(make_settings(database_url, media_root))

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with _bound_session(db_connection) as db_session:
            yield db_session

    application.dependency_overrides[get_session] = override_session
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    await app.state.engine.dispose()


@pytest.fixture
def settings(app: FastAPI) -> Settings:
    app_settings: Settings = app.state.settings
    return app_settings


@pytest.fixture
async def users(session: AsyncSession) -> Team:
    return Team(
        admin=await factories.create_user(session, Role.ADMIN, "admin", "Админ Админов"),
        head=await factories.create_user(session, Role.HEAD, "head", "Руководитель Отдела"),
        agent=await factories.create_user(session, Role.AGENT, "agent", "Агент Первый"),
        other_agent=await factories.create_user(session, Role.AGENT, "agent2", "Агент Второй"),
    )


@pytest.fixture
async def headers(session: AsyncSession, settings: Settings, users: Team) -> TeamHeaders:
    return TeamHeaders(
        admin=await factories.auth_headers(session, settings, users.admin),
        head=await factories.auth_headers(session, settings, users.head),
        agent=await factories.auth_headers(session, settings, users.agent),
        other_agent=await factories.auth_headers(session, settings, users.other_agent),
    )


@pytest.fixture
async def district(session: AsyncSession) -> District:
    return await factories.create_district(session, "Чиланзарский")
