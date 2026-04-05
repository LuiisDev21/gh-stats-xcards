"""Cache adapter based on cachetools.TTLCache."""

from __future__ import annotations

import asyncio
from typing import Generic, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


class StatsCache(Generic[T]):
    """Async-safe wrapper around :class:`cachetools.TTLCache`."""

    def __init__(self, *, max_size: int, ttl_seconds: int) -> None:
        """Initialize in-memory cache.

        Args:
            max_size: Maximum number of entries.
            ttl_seconds: Time-to-live in seconds.
        """

        self._cache: TTLCache[str, T] = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        """Fetch an item from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value if present and not expired.
        """

        async with self._lock:
            return self._cache.get(key)

    async def set(self, key: str, value: T) -> None:
        """Store an item in cache.

        Args:
            key: Cache key.
            value: Value to cache.
        """

        async with self._lock:
            self._cache[key] = value

