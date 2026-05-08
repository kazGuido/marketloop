# Deterministic Harmonic Sentinel: System Overview

This document explains the current implementation of the Deterministic Harmonic Sentinel: what it does, how data moves through the system, how signals are scored, how strategies are saved and monitored, and where the current limitations are.

## 1. Purpose

The system is a single-VPS Hyperliquid scanner, alerting engine, and optional auto-trader. It looks for confirmed harmonic reversal setups, waits for price to enter a projected reversal zone, checks deterministic market context, and then either:

- sends a Telegram alert in `SIGNAL_ONLY` mode, or
- submits a Hyperliquid market order in `AUTO_TRADE` mode.

The current design is intentionally conservative. Harmonic geometry is treated as a setup filter, not as the full trading edge. A signal must also pass volatility, trend, funding/OI, orderbook persistence, and net reward/risk checks before it can fire.

## 2. Runtime Architecture

Docker Compose runs seven services:

| Service | Role |
| --- | --- |
| `postgres` | Durable storage for config, patterns, trades, market data, strategy profiles, and replay metrics. |
| `redis` | Short-lived market cache for candles, mids, orderflow history, and alert de-duplication. |
| `collector` | Fetches Hyperliquid public market data and persists replayable candles. |
| `analyzer` | Runs scanner, confluence, risk, and strategy-monitor loops. |
| `api` | FastAPI service used by the React UI and external clients. |
| `whatsapp` | Baileys bridge service for WhatsApp alert delivery. |
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

### API key security

All `/api/*` routes can be protected with a shared API key:

- backend env: `API_AUTH_TOKEN`
- frontend env: `VITE_API_KEY`

When `API_AUTH_TOKEN` is set, the backend requires clients to send:

```text
x-api-key: <token>
```

`/health`, `/docs`, `/openapi.json`, and CORS preflight requests remain public. This is intentionally simple and VPS-friendly, but production deployments should still place the UI/API behind HTTPS and preferably a VPN, reverse-proxy auth layer, or private network.

### Notification config

Notification preferences are stored under `system_config.extra.notification_config` and edited from the UI. The backend fans out signal and strategy-degradation alerts to every enabled channel.

Supported channels:

- Telegram
  - enable/disable in UI
  - optional chat id override in UI
  - bot token should remain in `TELEGRAM_BOT_TOKEN`
- WhatsApp through Baileys
  - enable/disable in UI
  - recipient phone number or WhatsApp JID in UI
  - sent through the internal `whatsapp` Docker service
- Email
  - enable/disable in UI
  - recipient and optional SMTP host override in UI
  - SMTP credentials should usually remain in env

Sensitive credentials can be provided through `.env`; non-secret routing toggles and destinations can be managed in the UI.

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
- `requested_quantity`
- `entry_price`
- `average_fill_price`
- `stop_loss`
- `take_profit_1`
- `quantity`
- `remaining_quantity`
- `exchange_position_size`
- `last_reconciled_at`
- `reconciliation_notes`
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

Alerts are multi-channel. The backend builds one deterministic alert payload and delivers it through each enabled channel.

### Telegram

Telegram is optional.

Environment variables:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Used for:

- fired pattern alerts,
- strategy degradation alerts.

If Telegram credentials are absent, notifications are skipped without failing the engine.

### WhatsApp / Baileys

WhatsApp delivery uses the `whatsapp` Docker service. It runs a small Node/Express bridge around Baileys.

Endpoints:

- `GET /health`
- `GET /status`
- `POST /send`

The backend calls `POST /send` with:

```json
{
  "to": "15551234567",
  "message": "..."
}
```

The Baileys auth state is persisted in the `whatsapp_auth` Docker volume. On first startup, read the WhatsApp service logs or call `/status` to retrieve the pairing QR. After pairing, the same auth volume is reused.

Optional environment variables:

- `BAILEYS_API_KEY`
  - protects the bridge.
- `WHATSAPP_BRIDGE_API_KEY`
  - used by the Python backend when calling the bridge.
- `WHATSAPP_BRIDGE_URL`
  - defaults to `http://whatsapp:3000` in Compose.

If the bridge is disconnected or unpaired, WhatsApp delivery is skipped/fails independently of the other channels.

### Email

Email delivery uses SMTP.

Environment variables:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

The UI can enable email, set the recipient, and optionally override the SMTP host. Credentials should usually stay in environment variables rather than being typed into the UI.

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

### Fill reconciliation

AUTO_TRADE no longer assumes the requested market-order size is the actual position size.

On entry:

1. The requested position size is stored as `requested_quantity`.
2. The Hyperliquid market-order response is parsed for filled size and average fill price.
3. `quantity`, `remaining_quantity`, `average_fill_price`, and TP1 are based on the reported fill, not the requested size.
4. If no fill is reported, the trade is rejected instead of creating a ghost position record.

During every risk-manager cycle:

1. The private client fetches Hyperliquid `user_state`.
2. Open exchange positions are mapped by coin.
3. Each open DB trade is reconciled against the actual exchange position.
4. If exchange size is lower than DB remaining size, DB remaining size is reduced.
5. If no exchange position exists, the trade is closed in DB and the pattern is invalidated.
6. Stop-loss and TP close sizes are capped to the reconciled exchange position.

This does not replace a full order/fill event stream, but it materially reduces partial-fill, manual-close, and ghost-dust risk.

## 13. Database Migrations

The backend uses Alembic migrations.

Docker startup runs:

```bash
alembic upgrade head
```

through `backend/entrypoint.sh` before starting the API or worker process. The initial migration creates the current SQLAlchemy metadata. Future schema changes should be added as explicit Alembic revisions instead of relying on `Base.metadata.create_all`.

## 14. Safety Design

The system tries to avoid common failure modes:

- no private SDK initialization unless AUTO_TRADE is active,
- default mode is SIGNAL_ONLY,
- API key middleware for `/api/*` routes when `API_AUTH_TOKEN` is set,
- Alembic migration path instead of metadata-only schema creation,
- trade fill parsing and exchange-position reconciliation,
- hard invalidation at Point X,
- PRZ failure invalidation before entry,
- quality gates in addition to score,
- orderflow persistence instead of one L2 snapshot,
- fee/slippage-aware reward/risk,
- strategy degradation monitoring,
- kill switch endpoint.

## 15. Current Limitations

Important limitations:

1. Replay is candle-based.
   - It is conservative and deterministic, but not tick-accurate.

2. Liquidation clusters are not implemented.
   - There is no reliable free liquidation-cluster feed wired in.
   - OI/funding plus persistent L2 imbalance are used as deterministic proxies.

3. Harmonic coverage is limited.
   - Current deterministic logic focuses on Gartley-style X/A/B/C projections.
   - Other harmonic families can be added later.

4. No portfolio-level exposure cap yet.
   - AUTO_TRADE position sizing uses per-trade risk, but broader portfolio constraints should be added before serious live deployment.

5. Reconciliation is polling-based.
   - The risk loop reconciles against Hyperliquid user state, but there is not yet a dedicated WebSocket fill/order event journal.

6. API auth is shared-key based.
   - This is much better than unauthenticated VPS ports, but HTTPS, reverse-proxy hardening, and/or VPN access are still recommended.

## 16. Recommended Operating Process

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
