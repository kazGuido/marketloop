# Deterministic Harmonic Sentinel

Single-VPS Hyperliquid harmonic pattern scanner and alerting/trading engine.

## Architecture

- **PostgreSQL** stores dynamic system configuration, detected patterns, and trades.
- **Redis** holds short-lived market snapshots so the UI and analyzer do not hammer Hyperliquid.
- **Collector** fetches Hyperliquid candles/mids every minute and writes Redis.
- **Analyzer** runs deterministic ATR ZigZag pivot detection, Gartley PRZ projection, confluence scoring, execution, and risk loops.
- **FastAPI API** serves config, patterns, candles, trades, and `/api/panic`.
- **React/Vite UI** provides signal/auto-trade controls, asset pool settings, kill switch, active signals, and lightweight chart overlays.

## Run locally

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000
- Frontend: http://localhost:5173

## Safety defaults

The default operation mode is `SIGNAL_ONLY`. The authenticated Hyperliquid SDK is only initialized when the database-backed mode is switched to `AUTO_TRADE`, and then `HYPERLIQUID_WALLET_ADDRESS` plus `HYPERLIQUID_PRIVATE_KEY` must be present.

## Deterministic pattern rules

- ATR(14) x 1.5 ZigZag deviation confirms pivots before using X/A/B/C.
- Gartley D projection uses:
  - `D1 = X +/- abs(X - A) * 0.786`
  - `D2 = C +/- abs(B - C) * 1.272`
- PRZ width must be less than 0.5% of current asset price.
- Confluence score fires at 80+ after candle close confirmation:
  - Harmonic match
  - OI/funding positioning
  - L2 imbalance within 0.2%
  - RSI divergence
  - ATR volatility regime
  - EMA50/EMA200 trend filter
  - persistent orderflow imbalance
  - net reward/risk after fee and slippage assumptions

## Replay/research data

The collector/analyzer persist replayable evidence:

- `market_candles`: OHLCV by symbol/timeframe/open time.
- `orderbook_snapshots`: mid price, 0.2% bid/ask depth, imbalance ratio, and top levels captured when patterns enter PRZ.
- `asset_context_snapshots`: OI, funding, mark price, and raw Hyperliquid context captured with confluence checks.
- `strategy_configs`: deterministic weights and gates used to score/fail signals.

The default profile is intentionally conservative: fewer tools, higher evidence quality, and explicit cost assumptions. Liquidation-cluster data is not added yet because there is no reliable free Hyperliquid endpoint in this implementation; use OI/funding plus orderflow persistence as the deterministic positioning proxy until a real liquidation feed is available.
