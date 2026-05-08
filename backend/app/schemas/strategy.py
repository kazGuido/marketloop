from pydantic import BaseModel, Field, model_validator


class StrategyConfigBase(BaseModel):
    name: str = "rent-and-utilities"
    active: bool = True
    archived: bool = False
    score_threshold: int = Field(default=80, ge=1, le=100)
    base_weight: int = Field(default=25, ge=0, le=100)
    oi_weight: int = Field(default=15, ge=0, le=100)
    orderbook_weight: int = Field(default=15, ge=0, le=100)
    rsi_weight: int = Field(default=10, ge=0, le=100)
    trend_weight: int = Field(default=10, ge=0, le=100)
    volatility_weight: int = Field(default=10, ge=0, le=100)
    funding_weight: int = Field(default=5, ge=0, le=100)
    orderflow_persistence_weight: int = Field(default=10, ge=0, le=100)
    min_atr_pct: float = Field(default=0.0015, ge=0)
    max_atr_pct: float = Field(default=0.035, gt=0)
    min_net_reward_risk: float = Field(default=1.2, ge=0.1, le=10)
    max_abs_funding_rate: float = Field(default=0.0005, ge=0)
    orderbook_imbalance_ratio: float = Field(default=3.0, ge=1.0, le=20)
    orderflow_window: int = Field(default=3, ge=1, le=20)
    orderflow_min_confirmations: int = Field(default=2, ge=1, le=20)
    fee_bps: float = Field(default=4.5, ge=0, le=100)
    slippage_bps: float = Field(default=3.0, ge=0, le=100)
    require_quality_gates: bool = True
    monitor_window_trades: int = Field(default=30, ge=1, le=500)
    min_monitor_trades: int = Field(default=8, ge=1, le=500)
    min_win_rate: float = Field(default=0.42, ge=0, le=1)
    min_profit_factor: float = Field(default=1.15, ge=0, le=20)
    max_drawdown_r: float = Field(default=6.0, ge=0, le=100)
    notify_on_degradation: bool = True

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.max_atr_pct <= self.min_atr_pct:
            raise ValueError("max_atr_pct must be greater than min_atr_pct")
        if self.orderflow_min_confirmations > self.orderflow_window:
            raise ValueError("orderflow_min_confirmations cannot exceed orderflow_window")
        return self


class StrategyConfigUpdate(StrategyConfigBase):
    pass


class StrategyConfigCreate(StrategyConfigBase):
    active: bool = False


class StrategyConfigRead(StrategyConfigBase):
    id: int

    model_config = {"from_attributes": True}


class StrategyPerformanceRead(BaseModel):
    strategy_config_id: int
    sample_size: int
    win_rate: float
    profit_factor: float
    expectancy_r: float
    max_drawdown_r: float
    degraded: bool
    metrics: dict


class StrategyReplayRead(StrategyPerformanceRead):
    passed_candidates: int
