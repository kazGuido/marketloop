from dataclasses import dataclass
from typing import Any

import numpy as np

from app.models.enums import PatternDirection


@dataclass(frozen=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Pivot:
    index: int
    time: int
    price: float
    kind: str


@dataclass(frozen=True)
class HarmonicProjection:
    symbol: str
    timeframe: str
    pattern_type: str
    direction: PatternDirection
    coords: dict[str, dict[str, float | int | str]]
    prz_lower: float
    prz_upper: float
    source_key: str


def normalize_candles(raw: list[dict[str, Any]]) -> list[Candle]:
    candles: list[Candle] = []
    for item in raw:
        timestamp = int(item.get("t") or item.get("time") or 0)
        if timestamp > 10_000_000_000:
            timestamp = timestamp // 1000
        candles.append(
            Candle(
                time=timestamp,
                open=float(item.get("o") or item.get("open")),
                high=float(item.get("h") or item.get("high")),
                low=float(item.get("l") or item.get("low")),
                close=float(item.get("c") or item.get("close")),
                volume=float(item.get("v") or item.get("volume") or 0),
            )
        )
    return sorted(candles, key=lambda candle: candle.time)


def atr(candles: list[Candle], period: int = 14) -> list[float]:
    if not candles:
        return []
    true_ranges: list[float] = []
    previous_close = candles[0].close
    for candle in candles:
        true_range = max(
            candle.high - candle.low,
            abs(candle.high - previous_close),
            abs(candle.low - previous_close),
        )
        true_ranges.append(true_range)
        previous_close = candle.close

    values: list[float] = []
    for index in range(len(true_ranges)):
        start = max(0, index - period + 1)
        values.append(float(np.mean(true_ranges[start : index + 1])))
    return values


def rsi(candles: list[Candle], period: int = 14) -> list[float]:
    if len(candles) < 2:
        return [50.0 for _ in candles]

    deltas = [candles[index].close - candles[index - 1].close for index in range(1, len(candles))]
    gains = [max(delta, 0) for delta in deltas]
    losses = [abs(min(delta, 0)) for delta in deltas]

    values = [50.0]
    for index in range(len(deltas)):
        start = max(0, index - period + 1)
        avg_gain = float(np.mean(gains[start : index + 1]))
        avg_loss = float(np.mean(losses[start : index + 1]))
        if avg_loss == 0:
            values.append(100.0)
        else:
            relative_strength = avg_gain / avg_loss
            values.append(100 - (100 / (1 + relative_strength)))
    return values


def zigzag_pivots(candles: list[Candle], atr_multiplier: float = 1.5, atr_period: int = 14) -> list[Pivot]:
    """Confirm pivots only after an ATR-sized retrace to avoid repainting XABC points."""
    if len(candles) < atr_period + 5:
        return []

    atr_values = atr(candles, atr_period)
    pivots: list[Pivot] = []
    direction = 0
    candidate_high_index = 0
    candidate_low_index = 0
    candidate_high = candles[0].high
    candidate_low = candles[0].low

    for index, candle in enumerate(candles[1:], start=1):
        threshold = max(atr_values[index] * atr_multiplier, candle.close * 0.0005)

        if candle.high >= candidate_high:
            candidate_high = candle.high
            candidate_high_index = index
        if candle.low <= candidate_low:
            candidate_low = candle.low
            candidate_low_index = index

        if direction >= 0 and candidate_high - candle.low >= threshold:
            pivot_candle = candles[candidate_high_index]
            if not pivots or pivots[-1].index != candidate_high_index:
                pivots.append(Pivot(candidate_high_index, pivot_candle.time, pivot_candle.high, "HIGH"))
            direction = -1
            candidate_low = candle.low
            candidate_low_index = index

        if direction <= 0 and candle.high - candidate_low >= threshold:
            pivot_candle = candles[candidate_low_index]
            if not pivots or pivots[-1].index != candidate_low_index:
                pivots.append(Pivot(candidate_low_index, pivot_candle.time, pivot_candle.low, "LOW"))
            direction = 1
            candidate_high = candle.high
            candidate_high_index = index

    return _dedupe_alternating_pivots(pivots)


def _dedupe_alternating_pivots(pivots: list[Pivot]) -> list[Pivot]:
    if not pivots:
        return []

    result = [pivots[0]]
    for pivot in pivots[1:]:
        last = result[-1]
        if pivot.kind != last.kind:
            result.append(pivot)
            continue

        more_extreme = (pivot.kind == "HIGH" and pivot.price > last.price) or (
            pivot.kind == "LOW" and pivot.price < last.price
        )
        if more_extreme:
            result[-1] = pivot
    return result


def detect_gartley_projections(
    symbol: str,
    timeframe: str,
    raw_candles: list[dict[str, Any]],
) -> list[HarmonicProjection]:
    candles = normalize_candles(raw_candles)
    pivots = zigzag_pivots(candles)
    projections: list[HarmonicProjection] = []
    if len(pivots) < 4 or not candles:
        return projections

    # Evaluate the latest few confirmed XABC chains so a delayed collector cycle can still persist a new signal.
    for offset in range(max(0, len(pivots) - 8), len(pivots) - 3):
        x, a, b, c = pivots[offset : offset + 4]
        projection = _gartley_from_xabc(symbol, timeframe, candles[-1].close, x, a, b, c)
        if projection:
            projections.append(projection)
    return projections


def _gartley_from_xabc(
    symbol: str,
    timeframe: str,
    current_price: float,
    x: Pivot,
    a: Pivot,
    b: Pivot,
    c: Pivot,
) -> HarmonicProjection | None:
    kinds = [x.kind, a.kind, b.kind, c.kind]
    if kinds == ["LOW", "HIGH", "LOW", "HIGH"]:
        direction = PatternDirection.BULLISH
        d1 = x.price + abs(a.price - x.price) * 0.786
        d2 = c.price - abs(b.price - c.price) * 1.272
    elif kinds == ["HIGH", "LOW", "HIGH", "LOW"]:
        direction = PatternDirection.BEARISH
        d1 = x.price - abs(a.price - x.price) * 0.786
        d2 = c.price + abs(b.price - c.price) * 1.272
    else:
        return None

    xa = abs(a.price - x.price)
    ab = abs(a.price - b.price)
    bc = abs(c.price - b.price)
    if min(xa, ab, bc, current_price) <= 0:
        return None

    b_retrace = ab / xa
    c_retrace = bc / ab
    if not 0.55 <= b_retrace <= 0.70:
        return None
    if not 0.382 <= c_retrace <= 0.886:
        return None

    prz_lower = min(d1, d2)
    prz_upper = max(d1, d2)
    if (prz_upper - prz_lower) / current_price >= 0.005:
        return None

    pattern_name = f"{direction.title()} Gartley"
    coords = {
        "X": _pivot_payload(x),
        "A": _pivot_payload(a),
        "B": _pivot_payload(b),
        "C": _pivot_payload(c),
    }
    source_key = f"{symbol}:{timeframe}:gartley:{direction}:{x.time}:{a.time}:{b.time}:{c.time}"
    return HarmonicProjection(
        symbol=symbol,
        timeframe=timeframe,
        pattern_type=pattern_name,
        direction=direction,
        coords=coords,
        prz_lower=prz_lower,
        prz_upper=prz_upper,
        source_key=source_key,
    )


def _pivot_payload(pivot: Pivot) -> dict[str, float | int | str]:
    return {"time": pivot.time, "price": pivot.price, "kind": pivot.kind}


def rsi_divergence(candles: list[Candle], direction: PatternDirection) -> bool:
    values = rsi(candles)
    pivots = zigzag_pivots(candles, atr_multiplier=1.0)
    if direction == PatternDirection.BULLISH:
        lows = [pivot for pivot in pivots if pivot.kind == "LOW"][-2:]
        if len(lows) < 2:
            return False
        first, second = lows
        return second.price < first.price and values[second.index] > values[first.index]

    highs = [pivot for pivot in pivots if pivot.kind == "HIGH"][-2:]
    if len(highs) < 2:
        return False
    first, second = highs
    return second.price > first.price and values[second.index] < values[first.index]


def candle_closed_through_prz(candles: list[Candle], lower: float, upper: float, direction: PatternDirection) -> bool:
    if not candles:
        return False
    close = candles[-1].close
    if direction == PatternDirection.BULLISH:
        return close >= lower
    return close <= upper


def take_profit_1(coords: dict[str, Any], direction: PatternDirection, entry_price: float) -> float:
    c_price = float(coords["C"]["price"])
    if direction == PatternDirection.BULLISH:
        return entry_price + abs(c_price - entry_price) * 0.382
    return entry_price - abs(entry_price - c_price) * 0.382


def stop_loss_from_x(coords: dict[str, Any], direction: PatternDirection) -> float:
    x_price = float(coords["X"]["price"])
    if direction == PatternDirection.BULLISH:
        return x_price * (1 - 0.002)
    return x_price * (1 + 0.002)
