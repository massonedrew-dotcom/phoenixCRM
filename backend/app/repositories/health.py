from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ping(session: AsyncSession) -> None:
    """Run a trivial query; raises if the database is unreachable."""
    await session.execute(text("SELECT 1"))
