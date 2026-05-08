from dataclasses import dataclass
from typing import Any

from app.models import Pattern, StrategyConfig
from app.models.enums import PatternDirection
from app.services.redis_cache import redis_cache
from app.services.technical import (
    atr_pct,
    avoids_hard_countertrend,
    net_reward_risk,
    normalize_candles,
    rsi_divergence,
)


@dataclass(frozen=True)
class ConfluenceResult:
    score: int
    reasons: list[str]
    reject_reasons: list[str]
    gates_passed: bool
    bid_depth: float
    ask_depth: float
    imbalance_ratio: float
    open_interest: float | None
    funding_rate: float | None
    atr_pct: float
    net_reward_risk: float

    def as_details(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "reasons": self.reasons,
            "reject_reasons": self.reject_reasons,
            "gates_passed": self.gates_passed,
            "bid_depth": self.bid_depth,
            "ask_depth": self.ask_depth,
            "imbalance_ratio": self.imbalance_ratio,
            "open_interest": self.open_interest,
            "funding_rate": self.funding_rate,
            "atr_pct": self.atr_pct,
            "net_reward_risk": self.net_reward_risk,
        }


async def score_pattern(
    pattern: Pattern,
    live_price: float,
    l2_book: dict[str, Any],
    asset_context: dict[str, Any],
    raw_candles: list[dict[str, Any]],
    strategy: StrategyConfig,
) -> ConfluenceResult:
    score = strategy.base_weight
    reasons = [f"Base harmonic match: +{strategy.base_weight}"]
    reject_reasons: list[str] = []

    open_interest = _float_or_none(asset_context.get("openInterest") or asset_context.get("oi"))
    funding_rate = _float_or_none(asset_context.get("funding") or asset_context.get("fundingRate"))
    oi_key = f"oi:{pattern.symbol}"
    previous_oi_raw = await redis_cache.get_json(oi_key)
    if open_interest is not None:
        await redis_cache.set_json(oi_key, open_interest, ex=60 * 60 * 6)
    if _oi_confirms(pattern.direction, open_interest, previous_oi_raw):
        score += strategy.oi_weight
        reasons.append(f"Open interest positioning confirms reversal: +{strategy.oi_weight}")

    bid_depth, ask_depth = _depth_within_band(l2_book, live_price, band=0.002)
    imbalance_ratio = _imbalance_ratio(pattern.direction, bid_depth, ask_depth)
    if pattern.direction == PatternDirection.BULLISH:
        book_confirms = ask_depth > 0 and bid_depth > ask_depth * strategy.orderbook_imbalance_ratio
    else:
        book_confirms = bid_depth > 0 and ask_depth > bid_depth * strategy.orderbook_imbalance_ratio
    if book_confirms:
        score += strategy.orderbook_weight
        reasons.append(f"Orderbook imbalance confirms reversal side: +{strategy.orderbook_weight}")

    candles = normalize_candles(raw_candles)
    if rsi_divergence(candles, pattern.direction):
        score += strategy.rsi_weight
        reasons.append(f"15m RSI divergence confirms reversal: +{strategy.rsi_weight}")

    current_atr_pct = atr_pct(candles)
    volatility_ok = strategy.min_atr_pct <= current_atr_pct <= strategy.max_atr_pct
    if volatility_ok:
        score += strategy.volatility_weight
        reasons.append(f"ATR regime tradable ({current_atr_pct:.3%}): +{strategy.volatility_weight}")
    else:
        reject_reasons.append(
            f"ATR regime outside band ({current_atr_pct:.3%}; allowed {strategy.min_atr_pct:.3%}-{strategy.max_atr_pct:.3%})"
        )

    trend_ok = avoids_hard_countertrend(candles, pattern.direction)
    if trend_ok:
        score += strategy.trend_weight
        reasons.append(f"Not fighting a hard EMA trend: +{strategy.trend_weight}")
    else:
        reject_reasons.append("EMA50/EMA200 trend filter is against this reversal")

    funding_ok = _funding_ok(pattern.direction, funding_rate, strategy.max_abs_funding_rate)
    if funding_ok:
        score += strategy.funding_weight
        reasons.append(f"Funding is not meaningfully adverse: +{strategy.funding_weight}")
    else:
        reject_reasons.append("Funding is too adverse/crowded for this direction")

    persistent = await _orderflow_persistent(pattern, imbalance_ratio, strategy)
    if persistent:
        score += strategy.orderflow_persistence_weight
        reasons.append(f"Orderflow imbalance persisted across snapshots: +{strategy.orderflow_persistence_weight}")
    else:
        reject_reasons.append("Orderflow imbalance has not persisted long enough")

    rr = net_reward_risk(pattern.coords, pattern.direction, live_price, strategy.fee_bps, strategy.slippage_bps)
    if rr < strategy.min_net_reward_risk:
        reject_reasons.append(f"Net reward/risk {rr:.2f} below minimum {strategy.min_net_reward_risk:.2f}")

    gates_passed = not strategy.require_quality_gates or (
        volatility_ok and trend_ok and funding_ok and persistent and rr >= strategy.min_net_reward_risk
    )

    return ConfluenceResult(
        score=min(score, 100),
        reasons=reasons,
        reject_reasons=reject_reasons,
        gates_passed=gates_passed,
        bid_depth=bid_depth,
        ask_depth=ask_depth,
        imbalance_ratio=imbalance_ratio,
        open_interest=open_interest,
        funding_rate=funding_rate,
        atr_pct=current_atr_pct,
        net_reward_risk=rr,
    )


def _oi_confirms(direction: PatternDirection, open_interest: float | None, previous_oi_raw: Any) -> bool:
    if open_interest is None or previous_oi_raw is None:
        return False
    previous = float(previous_oi_raw)
    # For reversals we want leverage unwinding, not fresh leverage chasing through the PRZ.
    return open_interest < previous


def _funding_ok(direction: PatternDirection, funding_rate: float | None, max_abs_funding_rate: float) -> bool:
    if funding_rate is None:
        return False
    if abs(funding_rate) > max_abs_funding_rate:
        return False
    if direction == PatternDirection.BULLISH:
        return funding_rate <= max_abs_funding_rate
    return funding_rate >= -max_abs_funding_rate


async def _orderflow_persistent(pattern: Pattern, imbalance_ratio: float, strategy: StrategyConfig) -> bool:
    key = f"orderflow:{pattern.symbol}:{pattern.direction}"
    history = await redis_cache.get_json(key) or []
    history.append(imbalance_ratio)
    history = history[-strategy.orderflow_window :]
    await redis_cache.set_json(key, history, ex=60 * 10)
    confirmations = sum(1 for value in history if value >= strategy.orderbook_imbalance_ratio)
    return confirmations >= strategy.orderflow_min_confirmations


def _imbalance_ratio(direction: PatternDirection, bid_depth: float, ask_depth: float) -> float:
    if direction == PatternDirection.BULLISH:
        return bid_depth / ask_depth if ask_depth > 0 else 0
    return ask_depth / bid_depth if bid_depth > 0 else 0


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
