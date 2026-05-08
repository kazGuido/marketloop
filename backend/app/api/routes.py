from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.models import Pattern, Trade
from app.models.enums import OperationMode, PatternStatus, TradeStatus
from app.schemas.config import SystemConfigRead, SystemConfigUpdate
from app.schemas.pattern import CandleRead, PatternRead
from app.schemas.strategy import StrategyConfigRead, StrategyConfigUpdate
from app.schemas.trade import TradeRead
from app.services.config_service import get_system_config, update_system_config
from app.services.hyperliquid_client import HyperliquidPrivateClient, HyperliquidPublicClient
from app.services.redis_cache import redis_cache
from app.services.strategy_service import get_strategy_config, update_strategy_config
from app.services.technical import normalize_candles

router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/config", response_model=SystemConfigRead)
async def read_config(session: SessionDep):
    return await get_system_config(session)


@router.put("/api/config", response_model=SystemConfigRead)
async def write_config(payload: SystemConfigUpdate, session: SessionDep):
    return await update_system_config(session, payload)


@router.get("/api/strategy", response_model=StrategyConfigRead)
async def read_strategy(session: SessionDep):
    return await get_strategy_config(session)


@router.put("/api/strategy", response_model=StrategyConfigRead)
async def write_strategy(payload: StrategyConfigUpdate, session: SessionDep):
    return await update_strategy_config(session, payload)


@router.get("/api/patterns", response_model=list[PatternRead])
async def list_patterns(
    session: SessionDep,
    status: PatternStatus | None = Query(default=None),
    symbol: str | None = Query(default=None),
):
    stmt = select(Pattern).order_by(Pattern.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(Pattern.status == status)
    if symbol:
        stmt = stmt.where(Pattern.symbol == symbol.upper())
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/api/patterns/{pattern_id}", response_model=PatternRead)
async def read_pattern(pattern_id: UUID, session: SessionDep):
    pattern = await session.get(Pattern, pattern_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


@router.get("/api/trades", response_model=list[TradeRead])
async def list_trades(session: SessionDep, status: TradeStatus | None = Query(default=None)):
    stmt = select(Trade).order_by(Trade.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(Trade.status == status)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/api/candles/{symbol}", response_model=list[CandleRead])
async def read_candles(symbol: str, timeframe: str = Query(default="15m")):
    key = f"candles:{symbol.upper()}:{timeframe}"
    raw = await redis_cache.get_json(key)
    if raw is None:
        client = HyperliquidPublicClient()
        try:
            raw = await client.candles(symbol.upper(), timeframe)
        finally:
            await client.close()
    candles = normalize_candles(raw)
    return [
        CandleRead(
            time=candle.time,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
        )
        for candle in candles
    ]


@router.get("/api/symbols", response_model=list[str])
async def list_symbols():
    cached = await redis_cache.get_json("symbols")
    if cached:
        return cached
    client = HyperliquidPublicClient()
    try:
        symbols = await client.universe_symbols()
        await redis_cache.set_json("symbols", symbols, ex=60 * 60)
        return symbols
    finally:
        await client.close()


@router.post("/api/panic")
async def panic_close_all(session: SessionDep):
    config = await get_system_config(session)
    closed_positions = []
    if config.operation_mode == OperationMode.AUTO_TRADE:
        private_client = HyperliquidPrivateClient()
        closed_positions = await private_client.close_all_positions()

    result = await session.execute(select(Trade).where(Trade.status == TradeStatus.OPEN))
    for trade in result.scalars().all():
        trade.status = TradeStatus.CLOSED_LOSS
        trade.remaining_quantity = 0
    pattern_result = await session.execute(select(Pattern).where(Pattern.status == PatternStatus.ACTIVE))
    for pattern in pattern_result.scalars().all():
        pattern.status = PatternStatus.INVALIDATED
    await session.commit()
    return {"status": "panic_executed", "closed_positions": closed_positions}


@router.get("/api/runtime")
async def runtime():
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "timeframe": settings.default_timeframe,
    }
