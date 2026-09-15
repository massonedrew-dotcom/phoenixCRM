import uuid

from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Property, PropertyMedia


async def list_for_property(session: AsyncSession, property_id: uuid.UUID) -> list[PropertyMedia]:
    result = await session.scalars(
        select(PropertyMedia)
        .where(PropertyMedia.property_id == property_id, PropertyMedia.is_deleted == false())
        .order_by(PropertyMedia.sort_order, PropertyMedia.uploaded_at, PropertyMedia.id)
    )
    return list(result)


async def next_sort_order(session: AsyncSession, property_id: uuid.UUID) -> int:
    current = await session.scalar(
        select(func.max(PropertyMedia.sort_order)).where(
            PropertyMedia.property_id == property_id, PropertyMedia.is_deleted == false()
        )
    )
    return 0 if current is None else current + 1


async def get_with_property(
    session: AsyncSession, media_id: uuid.UUID, *, for_update: bool = False
) -> tuple[PropertyMedia, Property] | None:
    statement = (
        select(PropertyMedia, Property)
        .join(Property, Property.id == PropertyMedia.property_id)
        .where(PropertyMedia.id == media_id)
    )
    if for_update:
        statement = statement.with_for_update(of=PropertyMedia)
    row = (await session.execute(statement)).one_or_none()
    return None if row is None else (row[0], row[1])


def add_all(session: AsyncSession, records: list[PropertyMedia]) -> None:
    session.add_all(records)
