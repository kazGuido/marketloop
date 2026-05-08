import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings


class RedisCache:
    def __init__(self) -> None:
        self._client: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            settings = get_settings()
            self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    async def get_json(self, key: str) -> Any | None:
        raw = await self.client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ex: int | None = None) -> None:
        await self.client.set(key, json.dumps(value), ex=ex)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


redis_cache = RedisCache()
