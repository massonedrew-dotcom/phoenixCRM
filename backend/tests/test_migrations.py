import pytest
from sqlalchemy import delete, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditAction
from app.models import AuditLog, District, Property
from tests import factories
from tests.factories import Team


async def test_pg_trgm_extension_is_installed(session: AsyncSession) -> None:
    installed = await session.scalar(
        text("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'")
    )
    # Cyrillic must produce trigrams, otherwise landmark search cannot work.
    score = await session.scalar(
        text("SELECT similarity(:left, :right)"), {"left": "Чиланзар", "right": "Чилнзар"}
    )

    assert installed == 1
    assert score is not None and score > 0.3


async def test_word_similarity_threshold_is_set_per_connection(session: AsyncSession) -> None:
    threshold = await session.scalar(text("SHOW pg_trgm.word_similarity_threshold"))

    assert threshold == "0.5"


async def test_owner_phone_digits_is_generated(
    session: AsyncSession, users: Team, district: District
) -> None:
    record = await factories.create_property(
        session, users.agent, district, owner_phone="+998 (90) 123-45-67"
    )

    assert record.owner_phone_digits == "998901234567"


async def test_database_rejects_hard_delete_of_properties(
    session: AsyncSession, users: Team, district: District
) -> None:
    record = await factories.create_property(session, users.agent, district)

    with pytest.raises(DBAPIError, match="soft-deleted only"):
        async with session.begin_nested():
            await session.execute(delete(Property).where(Property.id == record.id))


async def test_database_rejects_changes_to_audit_log(session: AsyncSession, users: Team) -> None:
    row = AuditLog(entity="user", entity_id=users.admin.id, action=AuditAction.LOGIN)
    session.add(row)
    await session.flush()

    with pytest.raises(DBAPIError, match="append-only"):
        async with session.begin_nested():
            await session.execute(
                update(AuditLog).where(AuditLog.id == row.id).values(field="tampered")
            )
    with pytest.raises(DBAPIError, match="append-only"):
        async with session.begin_nested():
            await session.execute(delete(AuditLog).where(AuditLog.id == row.id))
