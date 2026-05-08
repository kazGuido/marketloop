from dataclasses import dataclass
from typing import Any

from app.models import Pattern
from app.models.enums import PatternDirection
from app.services.redis_cache import redis_cache
from app.services.technical import normalize_candles, rsi_divergence


@dataclass(frozen=True)
class ConfluenceResult:
    score: int
    reasons: list[str]
    bid_depth: float
    ask_depth: float
    open_interest: float | None
    funding_rate: float | None


async def score_pattern(
    pattern: Pattern,
    live_price: float,
    l2_book: dict[str, Any],
    asset_context: dict[str, Any],
    raw_candles: list[dict[str, Any]],
) -> ConfluenceResult:
    score = 40
    reasons = ["Base harmonic match: +40"]

    open_interest = _float_or_none(asset_context.get("openInterest") or asset_context.get("oi"))
    funding_rate = _float_or_none(asset_context.get("funding") or asset_context.get("fundingRate"))
    oi_key = f"oi:{pattern.symbol}"
    previous_oi_raw = await redis_cache.get_json(oi_key)
    if open_interest is not None:
        await redis_cache.set_json(oi_key, open_interest, ex=60 * 60 * 6)
    if open_interest is not None and previous_oi_raw is not None and open_interest < float(previous_oi_raw):
        score += 25
        reasons.append("Open interest dropping into reversal zone: +25")

    bid_depth, ask_depth = _depth_within_band(l2_book, live_price, band=0.002)
    if pattern.direction == PatternDirection.BULLISH:
        book_confirms = ask_depth > 0 and bid_depth > ask_depth * 3
    else:
        book_confirms = bid_depth > 0 and ask_depth > bid_depth * 3
    if book_confirms:
        score += 20
        reasons.append("Orderbook imbalance confirms reversal side: +20")

    candles = normalize_candles(raw_candles)
    if rsi_divergence(candles, pattern.direction):
        score += 15
        reasons.append("15m RSI divergence confirms reversal: +15")

    return ConfluenceResult(
        score=min(score, 100),
        reasons=reasons,
        bid_depth=bid_depth,
        ask_depth=ask_depth,
        open_interest=open_interest,
        funding_rate=funding_rate,
    )


def _depth_within_band(book: dict[str, Any], price: float, band: float) -> tuple[float, float]:
    levels = book.get("levels", [[], []])
    bids = levels[0] if len(levels) > 0 else []
    asks = levels[1] if len(levels) > 1 else []
    lower = price * (1 - band)
    upper = price * (1 + band)
    bid_depth = sum(_level_size(level) for level in bids if lower <= _level_price(level) <= price)
    ask_depth = sum(_level_size(level) for level in asks if price <= _level_price(level) <= upper)
    return bid_depth, ask_depth


def _level_price(level: dict[str, Any] | list[Any]) -> float:
    if isinstance(level, dict):
        return float(level.get("px") or level.get("price") or 0)
    return float(level[0])


def _level_size(level: dict[str, Any] | list[Any]) -> float:
    if isinstance(level, dict):
        return float(level.get("sz") or level.get("size") or 0)
    return float(level[1])


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
