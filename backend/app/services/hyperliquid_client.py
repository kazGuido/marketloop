import asyncio
import time
from typing import Any

import httpx

from app.core.config import get_settings


class HyperliquidPublicClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(20.0))

    async def post_info(self, payload: dict[str, Any]) -> Any:
        response = await self._client.post(self.settings.hyperliquid_info_url, json=payload)
        response.raise_for_status()
        return response.json()

    async def candles(
        self,
        coin: str,
        interval: str = "15m",
        lookback_minutes: int | None = None,
    ) -> list[dict[str, Any]]:
        lookback = lookback_minutes or self.settings.candle_lookback_minutes
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - lookback * 60 * 1000
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin.upper(),
                "interval": interval,
                "startTime": start_ms,
                "endTime": now_ms,
            },
        }
        return await self.post_info(payload)

    async def l2_book(self, coin: str) -> dict[str, Any]:
        return await self.post_info({"type": "l2Book", "coin": coin.upper()})

    async def meta_and_asset_ctxs(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        response = await self.post_info({"type": "metaAndAssetCtxs"})
        if not isinstance(response, list) or len(response) != 2:
            raise ValueError("Unexpected metaAndAssetCtxs response")
        return response[0], response[1]

    async def all_mids(self) -> dict[str, str]:
        return await self.post_info({"type": "allMids"})

    async def universe_symbols(self) -> list[str]:
        meta, _ = await self.meta_and_asset_ctxs()
        return [asset["name"].upper() for asset in meta.get("universe", []) if not asset.get("isDelisted")]

    async def asset_context(self, coin: str) -> dict[str, Any]:
        coin = coin.upper()
        meta, contexts = await self.meta_and_asset_ctxs()
        universe = meta.get("universe", [])
        for index, asset in enumerate(universe):
            if asset.get("name", "").upper() == coin and index < len(contexts):
                return contexts[index]
        raise KeyError(f"Asset context not found for {coin}")

    async def live_price(self, coin: str) -> float:
        mids = await self.all_mids()
        value = mids.get(coin.upper())
        if value is None:
            raise KeyError(f"Mid price not found for {coin}")
        return float(value)

    async def close(self) -> None:
        await self._client.aclose()


class HyperliquidPrivateClient:
    """Lazy authenticated SDK wrapper used only when AUTO_TRADE is enabled."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.hyperliquid_private_key or not settings.hyperliquid_wallet_address:
            raise RuntimeError("Hyperliquid private key and wallet address are required for AUTO_TRADE")

        from eth_account import Account
        from hyperliquid.exchange import Exchange
        from hyperliquid.info import Info

        account = Account.from_key(settings.hyperliquid_private_key)
        self.info = Info(settings.hyperliquid_api_url, skip_ws=True)
        self.exchange = Exchange(account, settings.hyperliquid_api_url, account_address=settings.hyperliquid_wallet_address)
        self.wallet_address = settings.hyperliquid_wallet_address

    async def account_equity(self) -> float:
        state = await asyncio.to_thread(self.info.user_state, self.wallet_address)
        margin_summary = state.get("marginSummary", {})
        return float(margin_summary.get("accountValue", 0) or 0)

    async def market_open(self, coin: str, is_buy: bool, size: float) -> dict[str, Any]:
        return await asyncio.to_thread(self.exchange.market_open, coin.upper(), is_buy, size)

    async def market_close(self, coin: str, size: float | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self.exchange.market_close, coin.upper(), size)

    async def close_all_positions(self) -> list[dict[str, Any]]:
        state = await asyncio.to_thread(self.info.user_state, self.wallet_address)
        results: list[dict[str, Any]] = []
        for position in state.get("assetPositions", []):
            item = position.get("position", {})
            size = abs(float(item.get("szi", 0) or 0))
            coin = item.get("coin")
            if coin and size > 0:
                results.append(await self.market_close(coin, size))
        return results
