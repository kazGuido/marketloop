from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.init_db import ensure_default_strategy_config
from app.models import StrategyConfig
from app.schemas.strategy import StrategyConfigUpdate


async def get_strategy_config(session: AsyncSession) -> StrategyConfig:
    result = await session.execute(select(StrategyConfig).where(StrategyConfig.id == 1))
    strategy = result.scalar_one_or_none()
    if strategy is None:
        strategy = await ensure_default_strategy_config(session)
    return strategy


async def update_strategy_config(session: AsyncSession, payload: StrategyConfigUpdate) -> StrategyConfig:
    strategy = await get_strategy_config(session)
    for field, value in payload.model_dump().items():
        setattr(strategy, field, value)
    await session.commit()
    await session.refresh(strategy)
    return strategy
