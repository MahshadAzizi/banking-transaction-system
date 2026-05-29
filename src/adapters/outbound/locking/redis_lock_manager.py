from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis

from src.application.ports.outbound.lock_manager import ILockManager
from src.domain.exceptions.base import ConcurrencyConflictError

_LOCK_PREFIX = "banking:transfer:lock"


class RedisLockManager(ILockManager):
    """
    Redis-based distributed lock using SETNX + TTL.
    Transfer A locks [account-1, account-2].
    Transfer B locks [account-2, account-1] simultaneously.
    Without sorting: A holds account-1 waiting for account-2,
    B holds account-2 waiting for account-1 — deadlock.
    Sorting ensures both always acquire in the same order.

    SETNX (SET if Not eXists):
    Atomic check-and-set in Redis. Either we own the lock or we don't.
    No race condition between checking and setting.
    """

    _RETRY_INTERVAL_SECONDS: float = 0.05  # 50ms between retries

    def __init__(self, redis: Redis, wait_timeout: float = 5.0) -> None:
        self._redis = redis
        self._wait_timeout = wait_timeout

    @asynccontextmanager
    async def acquire(
        self,
        *keys: str,
        ttl_seconds: int = 30,
    ) -> AsyncIterator[None]:
        acquired: list[str] = []
        try:
            for key in keys:
                lock_key = f"{_LOCK_PREFIX}:{key}"
                await self._acquire_single(lock_key, ttl_seconds)
                acquired.append(lock_key)

            yield
        finally:
            for lock_key in reversed(acquired):
                await self._safe_release(lock_key)

    async def _acquire_single(self, lock_key: str, ttl_seconds: int) -> None:
        """
        Retry acquiring a single lock until wait_timeout is exhausted.
        asyncio.sleep and not a busy loop:
        Busy loop burns CPU and starves other coroutines.
        asyncio.sleep yields control to the event loop between retries —
        other transfers (and the one holding the lock) can make progress.
        """
        deadline = asyncio.get_event_loop().time() + self._wait_timeout

        while True:
            ok = await self._redis.set(lock_key, "1", nx=True, ex=ttl_seconds)
            if ok:
                return

            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise ConcurrencyConflictError(
                    f"Could not acquire lock '{lock_key}' "
                    f"within {self._wait_timeout}s — "
                    f"another transfer is processing the same account."
                )
            await asyncio.sleep(min(self._RETRY_INTERVAL_SECONDS, remaining))

    async def _safe_release(self, lock_key: str) -> None:
        """
        Release a lock, swallowing errors.
        """
        try:
            await self._redis.delete(lock_key)
        except Exception:
            pass
