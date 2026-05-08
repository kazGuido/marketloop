export type OperationMode = "SIGNAL_ONLY" | "AUTO_TRADE";
export type PatternStatus = "PENDING" | "ACTIVE" | "INVALIDATED" | "WON" | "LOST";
export type PatternDirection = "BULLISH" | "BEARISH";

export interface SystemConfig {
  id: number;
  operation_mode: OperationMode;
  asset_pool: string[];
  risk_per_trade: number;
}

export interface StrategyConfig {
  id: number;
  name: string;
  active: boolean;
  archived: boolean;
  score_threshold: number;
  base_weight: number;
  oi_weight: number;
  orderbook_weight: number;
  rsi_weight: number;
  trend_weight: number;
  volatility_weight: number;
  funding_weight: number;
  orderflow_persistence_weight: number;
  min_atr_pct: number;
  max_atr_pct: number;
  min_net_reward_risk: number;
  max_abs_funding_rate: number;
  orderbook_imbalance_ratio: number;
  orderflow_window: number;
  orderflow_min_confirmations: number;
  fee_bps: number;
  slippage_bps: number;
  require_quality_gates: boolean;
  monitor_window_trades: number;
  min_monitor_trades: number;
  min_win_rate: number;
  min_profit_factor: number;
  max_drawdown_r: number;
  notify_on_degradation: boolean;
}

export interface StrategyPerformance {
  strategy_config_id: number;
  sample_size: number;
  win_rate: number;
  profit_factor: number;
  expectancy_r: number;
  max_drawdown_r: number;
  degraded: boolean;
  metrics: Record<string, unknown>;
  passed_candidates?: number;
}

export interface PivotCoord {
  time: number;
  price: number;
  kind: "HIGH" | "LOW";
}

export interface Pattern {
  id: string;
  symbol: string;
  pattern_type: string;
  direction: PatternDirection;
  timeframe: string;
  strategy_config_id: number | null;
  coords: Record<"X" | "A" | "B" | "C", PivotCoord>;
  prz_upper: number;
  prz_lower: number;
  confluence_score: number;
  confluence_details: {
    reasons?: string[];
    reject_reasons?: string[];
    gates_passed?: boolean;
    net_reward_risk?: number;
    atr_pct?: number;
    imbalance_ratio?: number;
    funding_rate?: number | null;
  };
  status: PatternStatus;
  created_at: string;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
