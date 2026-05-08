import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.init_db import ensure_default_config, ensure_default_strategy_config, init_models
from app.db.session import AsyncSessionLocal
from app.models import Pattern, Trade
from app.models.enums import OperationMode, PatternDirection, PatternStatus, TradeStatus
from app.services.config_service import get_system_config
from app.services.confluence import score_pattern
from app.services.execution import close_trade_loss, close_trade_take_profit, open_trade_for_pattern
from app.services.hyperliquid_client import HyperliquidPrivateClient, HyperliquidPublicClient
from app.services.market_data import persist_confluence_snapshots
from app.services.notifications import send_pattern_alert, send_strategy_degradation_alert
from app.services.pattern_service import pending_patterns, upsert_pending_pattern
from app.services.redis_cache import redis_cache
from app.services.technical import (
    candle_closed_through_prz,
    detect_gartley_projections,
    normalize_candles,
)
from app.services.strategy_performance import persist_strategy_performance
from app.services.strategy_service import get_strategy_config, list_strategy_configs

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("analyzer")


async def resolve_assets(client: HyperliquidPublicClient) -> list[str]:
    async with AsyncSessionLocal() as session:
        config = await get_system_config(session)
        assets = config.asset_pool
    if assets == ["ALL"]:
        assets = await client.universe_symbols()
        await redis_cache.set_json("symbols", assets, ex=60 * 60)
    return assets[: get_settings().max_assets_per_cycle]


async def scanner_loop(client: HyperliquidPublicClient) -> None:
    settings = get_settings()
    while True:
        try:
            assets = await resolve_assets(client)
            async with AsyncSessionLocal() as session:
                for symbol in assets:
                    raw = await redis_cache.get_json(f"candles:{symbol}:{settings.default_timeframe}")
                    if raw is None:
                        raw = await client.candles(symbol, settings.default_timeframe)
                    for projection in detect_gartley_projections(symbol, settings.default_timeframe, raw):
                        pattern = await upsert_pending_pattern(session, projection)
                        logger.info("Pending pattern %s %s %s", pattern.symbol, pattern.pattern_type, pattern.id)
        except Exception:
            logger.exception("Scanner cycle failed")
        await asyncio.sleep(settings.scanner_interval_seconds)


async def confluence_loop(client: HyperliquidPublicClient) -> None:
    settings = get_settings()
    while True:
        try:
            async with AsyncSessionLocal() as session:
                config = await get_system_config(session)
                strategy = await get_strategy_config(session)
                private_client = HyperliquidPrivateClient() if config.operation_mode == OperationMode.AUTO_TRADE else None
                for pattern in await pending_patterns(session):
                    live_price = await _live_price(client, pattern.symbol)
                    if _hard_invalidated_pending(pattern, live_price):
                        pattern.status = PatternStatus.INVALIDATED
                        await session.commit()
                        continue
                    if _crossed_prz_failure(pattern, live_price):
                        pattern.status = PatternStatus.INVALIDATED
                        await session.commit()
                        continue
                    if not pattern.prz_lower <= live_price <= pattern.prz_upper:
                        continue

                    raw_candles = await redis_cache.get_json(f"candles:{pattern.symbol}:{pattern.timeframe}")
                    if raw_candles is None:
                        raw_candles = await client.candles(pattern.symbol, pattern.timeframe)
                    book, context = await asyncio.gather(
                        client.l2_book(pattern.symbol),
                        client.asset_context(pattern.symbol),
                    )
                    confluence = await score_pattern(pattern, live_price, book, context, raw_candles, strategy)
                    await persist_confluence_snapshots(session, pattern, live_price, book, context, confluence)
                    pattern.strategy_config_id = strategy.id
                    pattern.confluence_score = confluence.score
                    pattern.confluence_details = confluence.as_details()
                    await session.commit()

                    candles = normalize_candles(raw_candles)
                    if confluence.score < strategy.score_threshold or not confluence.gates_passed or not candle_closed_through_prz(
                        candles, pattern.prz_lower, pattern.prz_upper, pattern.direction
                    ):
                        continue

                    if config.operation_mode == OperationMode.SIGNAL_ONLY:
                        await send_pattern_alert(config, pattern, confluence)
                        pattern.status = PatternStatus.ACTIVE
                        await session.commit()
                        logger.info("Signal fired for %s %s score=%s", pattern.symbol, pattern.id, confluence.score)
                    elif private_client is not None:
                        await open_trade_for_pattern(
                            session,
                            private_client,
                            pattern,
                            entry_price=live_price,
                            risk_per_trade=config.risk_per_trade,
                        )
                        logger.info("Auto-trade opened for %s %s score=%s", pattern.symbol, pattern.id, confluence.score)
        except Exception:
            logger.exception("Confluence cycle failed")
        await asyncio.sleep(settings.confluence_interval_seconds)


async def risk_manager_loop(client: HyperliquidPublicClient) -> None:
    settings = get_settings()
    while True:
        try:
            async with AsyncSessionLocal() as session:
                config = await get_system_config(session)
                if config.operation_mode != OperationMode.AUTO_TRADE:
                    await asyncio.sleep(settings.risk_interval_seconds)
                    continue
                private_client = HyperliquidPrivateClient()
                result = await session.execute(
                    select(Trade, Pattern)
                    .join(Pattern, Trade.pattern_id == Pattern.id)
                    .where(Trade.status == TradeStatus.OPEN)
                )
                for trade, pattern in result.all():
                    price = await _live_price(client, pattern.symbol)
                    x_price = float(pattern.coords["X"]["price"])
                    if _crossed_invalidation(pattern.direction, price, x_price):
                        await close_trade_loss(session, private_client, trade, pattern)
                        logger.warning("Trade invalidated at X for %s %s", pattern.symbol, trade.id)
                        continue
                    if not trade.stop_moved_to_breakeven and _hit_take_profit(pattern.direction, price, trade.take_profit_1):
                        await close_trade_take_profit(session, private_client, trade, pattern)
                        logger.info("TP1 hit for %s %s", pattern.symbol, trade.id)
        except Exception:
            logger.exception("Risk manager cycle failed")
        await asyncio.sleep(settings.risk_interval_seconds)


async def strategy_monitor_loop() -> None:
    settings = get_settings()
    while True:
        try:
            async with AsyncSessionLocal() as session:
                config = await get_system_config(session)
                for strategy in await list_strategy_configs(session):
                    snapshot = await persist_strategy_performance(session, strategy)
                    logger.info(
                        "Strategy %s performance sample=%s pf=%.2f exp=%.2f degraded=%s",
                        strategy.name,
                        snapshot.sample_size,
                        snapshot.profit_factor,
                        snapshot.expectancy_r,
                        snapshot.degraded,
                    )
                    alert_key = f"strategy_degraded_alert:{strategy.id}:{snapshot.sample_size}:{round(snapshot.expectancy_r, 2)}"
                    if strategy.notify_on_degradation and snapshot.degraded and not await redis_cache.get_json(alert_key):
                        await send_strategy_degradation_alert(config, strategy, snapshot)
                        await redis_cache.set_json(alert_key, True, ex=60 * 60 * 12)
        except Exception:
            logger.exception("Strategy monitor cycle failed")
        await asyncio.sleep(settings.strategy_monitor_interval_seconds)


async def _live_price(client: HyperliquidPublicClient, symbol: str) -> float:
    cached = await redis_cache.get_json(f"price:{symbol}")
    if cached is not None:
        return float(cached)
    price = await client.live_price(symbol)
    await redis_cache.set_json(f"price:{symbol}", price, ex=60)
    return price


def _hard_invalidated_pending(pattern: Pattern, price: float) -> bool:
    x_price = float(pattern.coords["X"]["price"])
    return _crossed_invalidation(pattern.direction, price, x_price)


def _crossed_prz_failure(pattern: Pattern, price: float) -> bool:
    if pattern.direction == PatternDirection.BULLISH:
        return price < pattern.prz_lower
    return price > pattern.prz_upper


def _crossed_invalidation(direction: PatternDirection, price: float, x_price: float) -> bool:
    if direction == PatternDirection.BULLISH:
        return price <= x_price
    return price >= x_price


def _hit_take_profit(direction: PatternDirection, price: float, take_profit: float) -> bool:
    if direction == PatternDirection.BULLISH:
        return price >= take_profit
    return price <= take_profit


async def run() -> None:
    await init_models()
    async with AsyncSessionLocal() as session:
        await ensure_default_config(session)
        await ensure_default_strategy_config(session)
    client = HyperliquidPublicClient()
    try:
        await asyncio.gather(scanner_loop(client), confluence_loop(client), risk_manager_loop(client), strategy_monitor_loop())
    finally:
        await client.close()
        await redis_cache.close()


if __name__ == "__main__":
    asyncio.run(run())
