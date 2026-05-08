# Deterministic Harmonic Sentinel: System Overview

This document explains the current implementation of the Deterministic Harmonic Sentinel: what it does, how data moves through the system, how signals are scored, how strategies are saved and monitored, and where the current limitations are.

## 1. Purpose

The system is a single-VPS Hyperliquid scanner, alerting engine, and optional auto-trader. It looks for confirmed harmonic reversal setups, waits for price to enter a projected reversal zone, checks deterministic market context, and then either:

- sends a Telegram alert in `SIGNAL_ONLY` mode, or
- submits a Hyperliquid market order in `AUTO_TRADE` mode.

The current design is intentionally conservative. Harmonic geometry is treated as a setup filter, not as the full trading edge. A signal must also pass volatility, trend, funding/OI, orderbook persistence, and net reward/risk checks before it can fire.

## 2. Runtime Architecture

Docker Compose runs six services:

| Service | Role |
| --- | --- |
| `postgres` | Durable storage for config, patterns, trades, market data, strategy profiles, and replay metrics. |
| `redis` | Short-lived market cache for candles, mids, orderflow history, and alert de-duplication. |
| `collector` | Fetches Hyperliquid public market data and persists replayable candles. |
| `analyzer` | Runs scanner, confluence, risk, and strategy-monitor loops. |
| `api` | FastAPI service used by the React UI and external clients. |
| `frontend` | React/Vite/Tailwind UI with config controls, strategy controls, signals, and chart overlays. |

The system separates collection, analysis, and API serving so the UI does not call Hyperliquid directly and the analysis logic stays backend-only.

## 3. Configuration and Modes

### System config

Stored in `system_config`.

Important fields:

- `operation_mode`
  - `SIGNAL_ONLY`: fire alerts only.
  - `AUTO_TRADE`: execute Hyperliquid orders.
- `asset_pool`
  - list such as `["BTC", "ETH", "SOL"]`
  - or `["ALL"]` to scan all Hyperliquid perps, capped by `max_assets_per_cycle`.
- `risk_per_trade`
  - percentage of account equity used for AUTO_TRADE position sizing.

The UI exposes these fields in the header.

### Strategy config

Stored in `strategy_configs`.

Strategies are saved profiles. One strategy is active at a time and the analyzer uses the active strategy for live scoring. Fired/scored patterns store `strategy_config_id` so later replay can attribute signals to the strategy that produced them.

Important strategy knobs:

- score weights:
  - `base_weight`
  - `oi_weight`
  - `orderbook_weight`
  - `rsi_weight`
  - `trend_weight`
  - `volatility_weight`
  - `funding_weight`
  - `orderflow_persistence_weight`
- gates:
  - `score_threshold`
  - `min_atr_pct`
  - `max_atr_pct`
  - `min_net_reward_risk`
  - `max_abs_funding_rate`
  - `orderbook_imbalance_ratio`
  - `orderflow_window`
  - `orderflow_min_confirmations`
  - `require_quality_gates`
- cost assumptions:
  - `fee_bps`
  - `slippage_bps`
- monitor thresholds:
  - `monitor_window_trades`
  - `min_monitor_trades`
  - `min_win_rate`
  - `min_profit_factor`
  - `max_drawdown_r`
  - `notify_on_degradation`

The default strategy profile is named `rent-and-utilities`, reflecting a preference for fewer, cleaner setups over frequent trading.

## 4. Data Flow

### 4.1 Collector loop

The collector runs roughly once per minute.

For each configured asset:

1. Fetches 15m candles from Hyperliquid public `/info`.
2. Writes the candle payload to Redis under `candles:{symbol}:{timeframe}`.
3. Persists normalized OHLCV candles into `market_candles`.
4. Fetches all mids from Hyperliquid and writes mid prices to Redis.

The persisted candles are the foundation for later replay.

### 4.2 Analyzer scanner loop

The scanner loop runs roughly once per minute.

For each configured asset:

1. Reads candles from Redis, falling back to Hyperliquid if missing.
2. Normalizes candles into internal `Candle` objects.
3. Runs ATR-based ZigZag pivot confirmation.
4. Evaluates recent X/A/B/C chains for Gartley projections.
5. Inserts or updates `PENDING` patterns.

Patterns only use confirmed pivots, not raw noisy OHLC movements.

### 4.3 Analyzer confluence loop

The confluence loop runs more frequently.

For every `PENDING` pattern:

1. Reads live price.
2. Invalidates the pattern if price crosses Point X.
3. Invalidates the pattern if price passes through the wrong side of the PRZ.
4. If price is inside the PRZ:
   - fetches L2 book
   - fetches OI/funding asset context
   - scores the pattern against the active strategy
   - persists orderbook and asset-context snapshots
   - stores the confluence detail payload on the pattern
5. Fires only if:
   - score is above strategy threshold,
   - quality gates pass,
   - 15m candle close confirmation passes.

If fired:

- `SIGNAL_ONLY`: send Telegram alert and mark pattern `ACTIVE`.
- `AUTO_TRADE`: open Hyperliquid market order, insert `Trade`, mark pattern `ACTIVE`.

### 4.4 Analyzer risk loop

Runs every 15 seconds.

For open trades:

1. Checks live price.
2. If price crosses Point X, immediately market-closes the position and marks:
   - pattern: `INVALIDATED`
   - trade: `CLOSED_LOSS`
3. If price hits TP1:
   - closes 50% of the position,
   - moves stop to breakeven,
   - marks the pattern `WON`.

### 4.5 Strategy monitor loop

Runs periodically, default every 300 seconds.

For each saved, non-archived strategy:

1. Replays the strategy against persisted pattern evidence.
2. Simulates deterministic TP/SL outcomes from saved candles.
3. Writes a row to `strategy_performance_snapshots`.
4. If degradation thresholds are breached, sends a Telegram warning.

This is intended to catch a strategy whose edge is decaying before continuing to trust it.

## 5. Harmonic Detection

The system currently implements deterministic Gartley projection logic.

### Pivot detection

Raw candles are not directly used as X/A/B/C points. Pivots are confirmed using an ATR ZigZag:

```text
deviation = ATR(14) * 1.5
```

A move smaller than this dynamic threshold is treated as noise.

### Gartley X/A/B/C validation

The system evaluates recent confirmed pivot chains.

Bullish structure:

```text
X = LOW
A = HIGH
B = LOW
C = HIGH
```

Bearish structure:

```text
X = HIGH
A = LOW
B = HIGH
C = LOW
```

Retracement checks:

- B retracement of XA must be roughly `0.55 <= AB/XA <= 0.70`.
- C retracement of AB must be `0.382 <= BC/AB <= 0.886`.

### PRZ projection

The D projection uses two Fibonacci targets.

For bullish:

```text
D1 = X + abs(A - X) * 0.786
D2 = C - abs(B - C) * 1.272
```

For bearish:

```text
D1 = X - abs(A - X) * 0.786
D2 = C + abs(B - C) * 1.272
```

The PRZ is:

```text
prz_lower = min(D1, D2)
prz_upper = max(D1, D2)
```

The PRZ is rejected if its width is at least 0.5% of the current asset price.

## 6. Confluence and Quality Gates

The confluence scorer produces a `ConfluenceResult` and stores its serialized details on the pattern. These details are important because replay reuses them to evaluate alternate strategy weights later.

### Score components

Each component is deterministic:

- base harmonic match
- OI positioning
- L2 orderbook imbalance
- RSI divergence
- ATR volatility regime
- EMA trend filter
- funding sanity
- persistent orderflow imbalance

The active strategy decides how many points each component is worth.

### Quality gates

Even if the score is high, the trade can be rejected by gates:

| Gate | Purpose |
| --- | --- |
| ATR regime | Avoid dead markets and extremely chaotic markets. |
| EMA trend filter | Avoid reversal trades fighting a steep EMA50/EMA200 trend. |
| Funding gate | Avoid entering when funding is too adverse/crowded. |
| Orderflow persistence | Avoid trusting a single spoofable L2 snapshot. |
| Net reward/risk | Require expected reward to justify stop distance plus fee/slippage assumptions. |

If `require_quality_gates` is true, all gates must pass.

### Orderflow persistence

The system stores recent imbalance ratios in Redis:

```text
orderflow:{symbol}:{direction}
```

The strategy controls:

- `orderflow_window`
- `orderflow_min_confirmations`
- `orderbook_imbalance_ratio`

This means the system requires repeated L2 confirmation instead of firing from one orderbook snapshot.

### Net reward/risk

The system estimates TP1 and stop:

- stop is 0.2% beyond Point X.
- TP1 is 0.382 retracement from entry toward Point C.

Then it subtracts assumed round-trip fee and slippage cost.

The result must be at least `min_net_reward_risk`.

## 7. Persistence Model

### `system_config`

Global runtime settings.

### `strategy_configs`

Saved strategy profiles and monitoring thresholds.

Only one active profile should be used by the analyzer at a time.

### `patterns`

Detected harmonic opportunities.

Important fields:

- `source_key`: deterministic uniqueness key for the X/A/B/C chain.
- `symbol`
- `pattern_type`
- `direction`
- `timeframe`
- `strategy_config_id`
- `coords`
- `prz_upper`
- `prz_lower`
- `confluence_score`
- `confluence_details`
- `status`

### `trades`

AUTO_TRADE executions.

Important fields:

- `pattern_id`
- `strategy_config_id`
- `entry_price`
- `stop_loss`
- `take_profit_1`
- `quantity`
- `remaining_quantity`
- `status`

### `market_candles`

Replayable OHLCV history.

Uniqueness:

```text
symbol + timeframe + open_time
```

### `orderbook_snapshots`

Captured when a pending pattern enters PRZ.

Stores:

- pattern id
- mid price
- bid depth within 0.2%
- ask depth within 0.2%
- imbalance ratio
- top raw levels

### `asset_context_snapshots`

Captured alongside confluence checks.

Stores:

- OI
- funding
- mark price
- raw asset context

### `strategy_performance_snapshots`

Rolling replay/monitor output.

Stores:

- sample size
- win rate
- profit factor
- expectancy in R
- max drawdown in R
- degraded flag
- extra metrics

## 8. Replay and Strategy Monitoring

Replay is designed to answer:

> If this saved strategy profile had been used against the persisted evidence, how would it have performed?

The replay process:

1. Reads historical patterns with `confluence_details`.
2. Recomputes the score using the candidate strategy's weights.
3. Applies that strategy's gates.
4. For candidates that would have fired, simulates outcome from stored candles.
5. Produces:
   - win rate
   - profit factor
   - expectancy R
   - max drawdown R
   - passed candidate count

The monitor loop runs the same evaluation periodically for each saved strategy.

### Important replay caveat

Replay is deterministic but approximate.

It simulates TP/SL from candles, not true exchange fills. If a candle contains both stop and target, the current simulator effectively assumes stop-first by checking stop before target. This is intentionally conservative but not a replacement for full tick/fill simulation.

Replay is good for:

- comparing knob profiles,
- detecting performance degradation,
- rejecting obviously bad configurations,
- monitoring whether a strategy is losing edge.

Replay is not yet good for:

- precise fill modeling,
- queue position,
- intra-candle path,
- latency,
- partial fills beyond the current TP1 logic,
- funding PnL accounting.

## 9. API Surface

### Health/runtime

- `GET /health`
- `GET /api/runtime`

### System config

- `GET /api/config`
- `PUT /api/config`

### Strategy profiles

- `GET /api/strategy`
  - active strategy.
- `PUT /api/strategy`
  - update active strategy.
- `GET /api/strategies`
  - list saved strategies.
- `POST /api/strategies`
  - create saved strategy.
- `POST /api/strategies/{strategy_id}/activate`
  - make a strategy active.
- `POST /api/strategies/{strategy_id}/replay`
  - replay saved strategy against persisted evidence.
- `GET /api/strategy-performance`
  - latest saved performance snapshots.

### Patterns/trades

- `GET /api/patterns`
- `GET /api/patterns/{pattern_id}`
- `GET /api/trades`

### Market data

- `GET /api/candles/{symbol}`
- `GET /api/symbols`

### Emergency

- `POST /api/panic`
  - in AUTO_TRADE mode, calls the private Hyperliquid client to close all open positions.
  - marks tracked open trades closed/lost and active patterns invalidated.

## 10. Frontend

The frontend is a React/Vite/Tailwind app.

### Header

Includes:

- Signal/Auto-Trade mode toggle.
- Strategy dropdown.
- Strategy name.
- Asset pool input.
- Risk % input.
- Score threshold.
- Minimum net reward/risk.
- Max ATR %.
- L2 imbalance ratio.
- Save current settings.
- Save strategy as a new profile.
- Replay active strategy.
- Kill switch.
- Latest replay/monitor health summary.

### Signal sidebar

Shows active patterns:

- symbol
- timeframe
- pattern type
- confluence score
- net R:R
- ATR %
- top score reasons

### Chart

Uses `lightweight-charts`.

When a pattern is selected:

- shows candles,
- draws triangle X-A-B,
- draws triangle A-B-C,
- draws PRZ rectangle extended to the right.

## 11. Telegram Notifications

Telegram is optional.

Environment variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Used for:

- fired pattern alerts,
- strategy degradation alerts.

If Telegram credentials are absent, notifications are skipped without failing the engine.

## 12. Hyperliquid Integration

### Public data

Uses Hyperliquid `/info` endpoint for:

- candles via `candleSnapshot`,
- L2 book via `l2Book`,
- universe/context via `metaAndAssetCtxs`,
- mids via `allMids`.

### Private trading

The authenticated Hyperliquid SDK is initialized only in AUTO_TRADE mode.

Required environment variables:

- `HYPERLIQUID_WALLET_ADDRESS`
- `HYPERLIQUID_PRIVATE_KEY`

This is deliberate: SIGNAL_ONLY mode should not require private keys.

## 13. Safety Design

The system tries to avoid common failure modes:

- no private SDK initialization unless AUTO_TRADE is active,
- default mode is SIGNAL_ONLY,
- hard invalidation at Point X,
- PRZ failure invalidation before entry,
- quality gates in addition to score,
- orderflow persistence instead of one L2 snapshot,
- fee/slippage-aware reward/risk,
- strategy degradation monitoring,
- kill switch endpoint.

## 14. Current Limitations

Important limitations:

1. No full migration framework yet.
   - Tables are created with SQLAlchemy metadata at startup.
   - Production should eventually use Alembic migrations.

2. Replay is candle-based.
   - It is conservative and deterministic, but not tick-accurate.

3. Liquidation clusters are not implemented.
   - There is no reliable free liquidation-cluster feed wired in.
   - OI/funding plus persistent L2 imbalance are used as deterministic proxies.

4. Harmonic coverage is limited.
   - Current deterministic logic focuses on Gartley-style X/A/B/C projections.
   - Other harmonic families can be added later.

5. No portfolio-level exposure cap yet.
   - AUTO_TRADE position sizing uses per-trade risk, but broader portfolio constraints should be added before serious live deployment.

6. No exchange-grade fill reconciliation yet.
   - Trade state assumes the SDK operation succeeded and does not continuously reconcile all Hyperliquid fills/orders.

7. No auth on the API/UI yet.
   - A real VPS deployment should put this behind authentication, a VPN, or a private network.

## 15. Recommended Operating Process

Use this sequence before trusting AUTO_TRADE:

1. Run in `SIGNAL_ONLY`.
2. Let collector/analyzer accumulate enough data.
3. Save a small number of strategy variants.
4. Replay each strategy.
5. Watch monitor snapshots over time.
6. Reject strategies that degrade or have too few samples.
7. Only consider AUTO_TRADE after performance remains acceptable after fees/slippage.
8. Start with very small risk.
9. Keep Telegram degradation alerts enabled.
10. Use the kill switch aggressively if behavior diverges from expectations.

The goal is not to be a top 0.1% trader. The realistic goal is to avoid low-quality trades, measure whether the remaining signals actually have positive expectancy, and stop or retune when the measured edge degrades.
