from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.init_db import ensure_default_strategy_config
from app.models import StrategyConfig
from app.schemas.strategy import StrategyConfigCreate, StrategyConfigUpdate


async def get_strategy_config(session: AsyncSession) -> StrategyConfig:
    result = await session.execute(
        select(StrategyConfig).where(StrategyConfig.active.is_(True), StrategyConfig.archived.is_(False)).limit(1)
    )
    strategy = result.scalar_one_or_none()
    if strategy is None:
        strategy = await ensure_default_strategy_config(session)
    return strategy


async def update_strategy_config(session: AsyncSession, payload: StrategyConfigUpdate) -> StrategyConfig:
    strategy = await get_strategy_config(session)
    for field, value in payload.model_dump().items():
        setattr(strategy, field, value)
    if strategy.active:
        await session.execute(
            update(StrategyConfig).where(StrategyConfig.id != strategy.id).values(active=False)
        )
    await session.commit()
    await session.refresh(strategy)
    return strategy


async def list_strategy_configs(session: AsyncSession, include_archived: bool = False) -> list[StrategyConfig]:
    stmt = select(StrategyConfig).order_by(StrategyConfig.active.desc(), StrategyConfig.updated_at.desc())
    if not include_archived:
        stmt = stmt.where(StrategyConfig.archived.is_(False))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_strategy_config(session: AsyncSession, payload: StrategyConfigCreate) -> StrategyConfig:
    data = payload.model_dump()
    if data.get("active"):
        await session.execute(update(StrategyConfig).values(active=False))
    strategy = StrategyConfig(**data)
    session.add(strategy)
    await session.commit()
    await session.refresh(strategy)
    return strategy


async def activate_strategy_config(session: AsyncSession, strategy_id: int) -> StrategyConfig:
    strategy = await session.get(StrategyConfig, strategy_id)
    if strategy is None or strategy.archived:
        raise ValueError("Strategy not found")
    await session.execute(update(StrategyConfig).values(active=False))
    strategy.active = True
    await session.commit()
    await session.refresh(strategy)
    return strategy
