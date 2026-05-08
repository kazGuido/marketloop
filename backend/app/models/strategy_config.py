from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StrategyConfig(Base):
    __tablename__ = "strategy_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="rent-and-utilities")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    score_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    base_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    oi_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    orderbook_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    rsi_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    trend_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    volatility_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    funding_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    orderflow_persistence_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    min_atr_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0015)
    max_atr_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.035)
    min_net_reward_risk: Mapped[float] = mapped_column(Float, nullable=False, default=1.2)
    max_abs_funding_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0005)
    orderbook_imbalance_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    orderflow_window: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    orderflow_min_confirmations: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    fee_bps: Mapped[float] = mapped_column(Float, nullable=False, default=4.5)
    slippage_bps: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    require_quality_gates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    monitor_window_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    min_monitor_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    min_win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.42)
    min_profit_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.15)
    max_drawdown_r: Mapped[float] = mapped_column(Float, nullable=False, default=6.0)
    notify_on_degradation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
