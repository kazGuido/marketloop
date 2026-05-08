from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import engine
from app.models import (
    AssetContextSnapshot,
    MarketCandle,
    OrderbookSnapshot,
    Pattern,
    StrategyConfig,
    StrategyPerformanceSnapshot,
    SystemConfig,
    Trade,
)


async def init_models() -> None:
    # Importing mapped classes above registers all tables with SQLAlchemy metadata.
    _ = (
        AssetContextSnapshot,
        MarketCandle,
        OrderbookSnapshot,
        Pattern,
        StrategyConfig,
        StrategyPerformanceSnapshot,
        SystemConfig,
        Trade,
    )
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


async def ensure_default_strategy_config(session: AsyncSession) -> StrategyConfig:
    result = await session.execute(select(StrategyConfig).where(StrategyConfig.id == 1))
    strategy = result.scalar_one_or_none()
    if strategy is None:
        strategy = StrategyConfig(id=1)
        session.add(strategy)
        await session.commit()
        await session.refresh(strategy)
    elif not strategy.active or strategy.archived:
        strategy.active = True
        strategy.archived = False
        await session.commit()
        await session.refresh(strategy)
    return strategy
