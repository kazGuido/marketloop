from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketCandle, Pattern, StrategyConfig, StrategyPerformanceSnapshot
from app.models.enums import PatternDirection
from app.services.technical import stop_loss_from_x, take_profit_1


@dataclass(frozen=True)
class PerformanceMetrics:
    strategy_config_id: int
    sample_size: int
    win_rate: float
    profit_factor: float
    expectancy_r: float
    max_drawdown_r: float
    degraded: bool
    metrics: dict[str, Any]
    passed_candidates: int = 0


async def evaluate_strategy_replay(
    session: AsyncSession,
    strategy: StrategyConfig,
    limit: int | None = None,
) -> PerformanceMetrics:
    stmt = select(Pattern).where(Pattern.confluence_details != {}).order_by(Pattern.updated_at.desc())
    if limit:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    outcomes: list[float] = []
    passed_candidates = 0
    for pattern in result.scalars().all():
        details = pattern.confluence_details or {}
        if not _would_fire(strategy, details):
            continue
        passed_candidates += 1
        outcome = await _simulate_pattern_outcome(session, pattern, strategy, details)
        if outcome is not None:
            outcomes.append(outcome)

    metrics = _metrics_from_outcomes(strategy, outcomes)
    return PerformanceMetrics(
        strategy_config_id=strategy.id,
        sample_size=metrics.sample_size,
        win_rate=metrics.win_rate,
        profit_factor=metrics.profit_factor,
        expectancy_r=metrics.expectancy_r,
        max_drawdown_r=metrics.max_drawdown_r,
        degraded=metrics.degraded,
        metrics={**metrics.metrics, "mode": "replay"},
        passed_candidates=passed_candidates,
    )


async def persist_strategy_performance(session: AsyncSession, strategy: StrategyConfig) -> StrategyPerformanceSnapshot:
    metrics = await evaluate_strategy_replay(session, strategy, limit=strategy.monitor_window_trades * 10)
    snapshot = StrategyPerformanceSnapshot(
        strategy_config_id=strategy.id,
        sample_size=metrics.sample_size,
        win_rate=metrics.win_rate,
        profit_factor=metrics.profit_factor,
        expectancy_r=metrics.expectancy_r,
        max_drawdown_r=metrics.max_drawdown_r,
        degraded=metrics.degraded,
        metrics={**metrics.metrics, "passed_candidates": metrics.passed_candidates},
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


async def latest_performance_snapshots(session: AsyncSession) -> list[StrategyPerformanceSnapshot]:
    result = await session.execute(
        select(StrategyPerformanceSnapshot).order_by(StrategyPerformanceSnapshot.created_at.desc()).limit(100)
    )
    return list(result.scalars().all())


def replay_score(strategy: StrategyConfig, details: dict[str, Any]) -> int:
    components = details.get("components") or {}
    score = 0
    if components.get("base", True):
        score += strategy.base_weight
    if components.get("oi"):
        score += strategy.oi_weight
    if components.get("orderbook"):
        score += strategy.orderbook_weight
    if components.get("rsi"):
        score += strategy.rsi_weight
    if components.get("trend"):
        score += strategy.trend_weight
    if components.get("volatility"):
        score += strategy.volatility_weight
    if components.get("funding"):
        score += strategy.funding_weight
    if components.get("orderflow_persistence"):
        score += strategy.orderflow_persistence_weight
    return min(score, 100)


def _would_fire(strategy: StrategyConfig, details: dict[str, Any]) -> bool:
    score = replay_score(strategy, details)
    if score < strategy.score_threshold:
        return False
    if not strategy.require_quality_gates:
        return True

    atr = float(details.get("atr_pct") or 0)
    rr = float(details.get("net_reward_risk") or 0)
    funding = details.get("funding_rate")
    imbalance = float(details.get("imbalance_ratio") or 0)
    components = details.get("components") or {}
    funding_ok = funding is not None and abs(float(funding)) <= strategy.max_abs_funding_rate
    return (
        strategy.min_atr_pct <= atr <= strategy.max_atr_pct
        and rr >= strategy.min_net_reward_risk
        and imbalance >= strategy.orderbook_imbalance_ratio
        and bool(components.get("trend"))
        and funding_ok
        and bool(components.get("orderflow_persistence"))
    )


async def _simulate_pattern_outcome(
    session: AsyncSession,
    pattern: Pattern,
    strategy: StrategyConfig,
    details: dict[str, Any],
) -> float | None:
    entry = details.get("live_price")
    observed_time = int(details.get("observed_time") or 0)
    if entry is None or observed_time <= 0:
        return None
    entry_price = float(entry)
    stop = stop_loss_from_x(pattern.coords, pattern.direction)
    target = take_profit_1(pattern.coords, pattern.direction, entry_price)
    result = await session.execute(
        select(MarketCandle)
        .where(
            MarketCandle.symbol == pattern.symbol,
            MarketCandle.timeframe == pattern.timeframe,
            MarketCandle.open_time >= observed_time,
        )
        .order_by(MarketCandle.open_time.asc())
        .limit(1000)
    )
    for candle in result.scalars().all():
        if pattern.direction == PatternDirection.BULLISH:
            if candle.low <= stop:
                return -1.0
            if candle.high >= target:
                return min(float(details.get("net_reward_risk") or strategy.min_net_reward_risk), 3.0) * 0.5
        else:
            if candle.high >= stop:
                return -1.0
            if candle.low <= target:
                return min(float(details.get("net_reward_risk") or strategy.min_net_reward_risk), 3.0) * 0.5
    return None


def _metrics_from_outcomes(strategy: StrategyConfig, outcomes: list[float]) -> PerformanceMetrics:
    window = outcomes[: strategy.monitor_window_trades]
    sample_size = len(window)
    wins = [value for value in window if value > 0]
    losses = [abs(value) for value in window if value < 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
    expectancy = sum(window) / sample_size if sample_size else 0
    win_rate = len(wins) / sample_size if sample_size else 0
    max_drawdown = _max_drawdown(window)
    degraded = sample_size >= strategy.min_monitor_trades and (
        win_rate < strategy.min_win_rate
        or profit_factor < strategy.min_profit_factor
        or max_drawdown > strategy.max_drawdown_r
    )
    return PerformanceMetrics(
        strategy_config_id=strategy.id,
        sample_size=sample_size,
        win_rate=win_rate,
        profit_factor=profit_factor,
        expectancy_r=expectancy,
        max_drawdown_r=max_drawdown,
        degraded=degraded,
        metrics={
            "wins": len(wins),
            "losses": len(losses),
            "gross_profit_r": gross_profit,
            "gross_loss_r": gross_loss,
            "thresholds": {
                "min_monitor_trades": strategy.min_monitor_trades,
                "min_win_rate": strategy.min_win_rate,
                "min_profit_factor": strategy.min_profit_factor,
                "max_drawdown_r": strategy.max_drawdown_r,
            },
        },
    )


def _max_drawdown(outcomes: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for outcome in outcomes:
        equity += outcome
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown
