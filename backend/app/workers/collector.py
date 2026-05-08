import asyncio
import logging

from app.core.config import get_settings
from app.db.init_db import ensure_default_config, init_models
from app.db.session import AsyncSessionLocal
from app.services.config_service import get_system_config
from app.services.hyperliquid_client import HyperliquidPublicClient
from app.services.redis_cache import redis_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("collector")


async def resolve_assets(client: HyperliquidPublicClient) -> list[str]:
    async with AsyncSessionLocal() as session:
        config = await get_system_config(session)
        assets = config.asset_pool
    if assets == ["ALL"]:
        assets = await client.universe_symbols()
        await redis_cache.set_json("symbols", assets, ex=60 * 60)
    return assets[: get_settings().max_assets_per_cycle]


async def collect_once(client: HyperliquidPublicClient) -> None:
    settings = get_settings()
    assets = await resolve_assets(client)
    logger.info("Collecting candles for %s", ", ".join(assets))
    mids = await client.all_mids()
    await redis_cache.set_json("mids", mids, ex=settings.collector_interval_seconds * 3)

    semaphore = asyncio.Semaphore(5)

    async def collect_symbol(symbol: str) -> None:
        async with semaphore:
            candles = await client.candles(symbol, settings.default_timeframe)
            await redis_cache.set_json(
                f"candles:{symbol}:{settings.default_timeframe}",
                candles,
                ex=settings.collector_interval_seconds * 5,
            )
            if symbol in mids:
                await redis_cache.set_json(f"price:{symbol}", float(mids[symbol]), ex=settings.collector_interval_seconds * 3)

    await asyncio.gather(*(collect_symbol(symbol) for symbol in assets), return_exceptions=False)


async def run() -> None:
    await init_models()
    async with AsyncSessionLocal() as session:
        await ensure_default_config(session)
    client = HyperliquidPublicClient()
    try:
        while True:
            try:
                await collect_once(client)
            except Exception:
                logger.exception("Collector cycle failed")
            await asyncio.sleep(get_settings().collector_interval_seconds)
    finally:
        await client.close()
        await redis_cache.close()


if __name__ == "__main__":
    asyncio.run(run())
