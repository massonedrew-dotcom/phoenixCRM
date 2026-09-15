import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import health as health_repository
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

DB_CHECK_TIMEOUT_SECONDS = 3.0


async def check_health(session: AsyncSession) -> HealthResponse:
    try:
        async with asyncio.timeout(DB_CHECK_TIMEOUT_SECONDS):
            await health_repository.ping(session)
    except Exception:
        # A health check must report any failure, whatever the driver raises.
        logger.warning("Database health check failed", exc_info=True)
        return HealthResponse(status="error", db="error")
    return HealthResponse(status="ok", db="ok")
