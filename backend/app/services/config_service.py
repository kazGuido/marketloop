from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.init_db import ensure_default_config
from app.models import SystemConfig
from app.schemas.config import SystemConfigUpdate


async def get_system_config(session: AsyncSession) -> SystemConfig:
    result = await session.execute(select(SystemConfig).where(SystemConfig.id == 1))
    config = result.scalar_one_or_none()
    if config is None:
        config = await ensure_default_config(session)
    return config


async def update_system_config(session: AsyncSession, payload: SystemConfigUpdate) -> SystemConfig:
    config = await get_system_config(session)
    config.operation_mode = payload.operation_mode
    config.asset_pool = payload.asset_pool
    config.risk_per_trade = payload.risk_per_trade
    config.extra = {
        **(config.extra or {}),
        "notification_config": payload.notification_config.model_dump(),
    }
    await session.commit()
    await session.refresh(config)
    return config
