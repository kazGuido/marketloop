from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.init_db import ensure_default_config, init_models
from app.db.session import AsyncSessionLocal
from app.services.redis_cache import redis_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    async with AsyncSessionLocal() as session:
        await ensure_default_config(session)
    yield
    await redis_cache.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
