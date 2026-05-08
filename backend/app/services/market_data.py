from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssetContextSnapshot, MarketCandle, OrderbookSnapshot, Pattern
from app.services.confluence import ConfluenceResult
from app.services.technical import normalize_candles


async def persist_candles(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    raw_candles: list[dict[str, Any]],
) -> None:
    candles = normalize_candles(raw_candles)
    if not candles:
        return

    rows = [
        {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "open_time": candle.time,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in candles
    ]
    stmt = insert(MarketCandle).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_market_candle_symbol_tf_time",
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
        },
    )
    await session.execute(stmt)
    await session.commit()


async def persist_confluence_snapshots(
    session: AsyncSession,
    pattern: Pattern,
    live_price: float,
    l2_book: dict[str, Any],
    asset_context: dict[str, Any],
    confluence: ConfluenceResult,
) -> None:
    session.add(
        OrderbookSnapshot(
            symbol=pattern.symbol,
            pattern_id=pattern.id,
            mid_price=live_price,
            bid_depth_0_2pct=confluence.bid_depth,
            ask_depth_0_2pct=confluence.ask_depth,
            imbalance_ratio=confluence.imbalance_ratio,
            raw_top_levels=_top_levels(l2_book),
        )
    )
    session.add(
        AssetContextSnapshot(
            symbol=pattern.symbol,
            pattern_id=pattern.id,
            open_interest=confluence.open_interest,
            funding_rate=confluence.funding_rate,
            mark_price=_float_or_none(asset_context.get("markPx") or asset_context.get("markPrice")),
            raw_context=asset_context,
        )
    )


def _top_levels(book: dict[str, Any], limit: int = 10) -> dict[str, Any]:
    levels = book.get("levels", [[], []])
    return {
        "bids": levels[0][:limit] if len(levels) > 0 else [],
        "asks": levels[1][:limit] if len(levels) > 1 else [],
    }


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
