export type OperationMode = "SIGNAL_ONLY" | "AUTO_TRADE";
export type PatternStatus = "PENDING" | "ACTIVE" | "INVALIDATED" | "WON" | "LOST";
export type PatternDirection = "BULLISH" | "BEARISH";

export interface SystemConfig {
  id: number;
  operation_mode: OperationMode;
  asset_pool: string[];
  risk_per_trade: number;
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
  coords: Record<"X" | "A" | "B" | "C", PivotCoord>;
  prz_upper: number;
  prz_lower: number;
  confluence_score: number;
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
