from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import API_PREFIX, Settings, get_settings
from app.core.context import RequestContextMiddleware
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import register_error_handlers
from app.core.rate_limit import SlidingWindowRateLimiter
from app.storage import create_storage

LOGIN_ATTEMPTS_PER_WINDOW = 10
LOGIN_WINDOW_SECONDS = 60


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application. Run with `uvicorn app.main:create_app --factory`."""
    settings = settings or get_settings()
    engine = create_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(
        title="CRM Phoenix API",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.storage = create_storage(settings)
    app.state.login_rate_limiter = SlidingWindowRateLimiter(
        LOGIN_ATTEMPTS_PER_WINDOW, LOGIN_WINDOW_SECONDS
    )

    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(api_router, prefix=API_PREFIX)
    return app
