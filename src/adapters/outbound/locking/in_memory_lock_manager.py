from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from src.application.ports.outbound.lock_manager import ILockManager
from src.domain.exceptions.base import ConcurrencyConflictError


class InMemoryLockManager(ILockManager):
    """
    In-memory lock implementation for unit tests.

    Uses a simple set to track held locks.
    Raises ConcurrencyConflictError if a lock is already held —
    same behaviour as the Redis implementation.
    """

    def __init__(self) -> None:
        self._held: set[str] = set()

    @asynccontextmanager
    async def acquire(
        self,
        *keys: str,
        ttl_seconds: int = 30,
    ) -> AsyncIterator[None]:
        acquired: list[str] = []

        try:
            for key in keys:
                if key in self._held:
                    raise ConcurrencyConflictError(key)
                self._held.add(key)
                acquired.append(key)

            yield

        finally:
            for key in acquired:
                self._held.discard(key)
