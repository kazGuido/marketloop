from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import engine
from app.models import Pattern, SystemConfig, Trade


async def init_models() -> None:
    # Importing mapped classes above registers all tables with SQLAlchemy metadata.
    _ = (Pattern, SystemConfig, Trade)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_default_config(session: AsyncSession) -> SystemConfig:
    result = await session.execute(select(SystemConfig).where(SystemConfig.id == 1))
    config = result.scalar_one_or_none()
    if config is None:
        config = SystemConfig(id=1)
        session.add(config)
        await session.commit()
        await session.refresh(config)
    return config
