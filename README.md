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
  - Harmonic match: +40
  - OI dropping: +25
  - L2 imbalance within 0.2%: +20
  - RSI divergence: +15
