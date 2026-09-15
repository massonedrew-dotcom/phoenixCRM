from fastapi import APIRouter

from app.api import audit, auth, config, districts, health, media, properties, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(config.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(districts.router)
api_router.include_router(properties.router)
api_router.include_router(media.router)
api_router.include_router(audit.router)
