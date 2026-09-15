import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import District


async def get_by_id(session: AsyncSession, district_id: uuid.UUID) -> District | None:
    return await session.get(District, district_id)


async def get_by_name(session: AsyncSession, name: str) -> District | None:
    return await session.scalar(select(District).where(District.name == name))


async def list_all(session: AsyncSession) -> list[District]:
    result = await session.scalars(select(District).order_by(District.name))
    return list(result)


def add(session: AsyncSession, district: District) -> None:
    session.add(district)
