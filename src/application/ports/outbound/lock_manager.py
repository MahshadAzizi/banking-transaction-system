from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Protocol, runtime_checkable, AsyncIterator


@runtime_checkable
class ILockManager(Protocol):
    """
    Outbound port — distributed locking across multiple application instances.

    WHY distributed locking is needed alongside SELECT FOR UPDATE:
    SELECT FOR UPDATE locks at the DB level but only within a single
    DB transaction. Between the moment we check the idempotency key
    and the moment we open the UoW, another pod could start processing
    the same transfer. The distributed lock closes this window.

    Two-layer locking strategy:
        Layer 1 — Redis Redlock (this port): prevents two pods from
                  entering the transfer logic for the same accounts
                  simultaneously. Fast, cross-process.
        Layer 2 — SELECT FOR UPDATE (repository): prevents race conditions
                  at the DB level even if the Redis lock is lost (Redis
                  crash, network partition). Slow but guaranteed.

    Both layers together make double-spend structurally impossible.

    WHY keys are always sorted before acquisition:
    Transfer A: locks [account-1, account-2]
    Transfer B: locks [account-2, account-1] ← reverse order

    Without sorting, A holds account-1 and waits for account-2,
    while B holds account-2 and waits for account-1 — deadlock.
    Sorting ensures both always acquire in the same order.

    The service is responsible for sorting:
        keys = sorted([str(from_id), str(to_id)])
        async with self._lock.acquire(*keys):
    """

    @asynccontextmanager
    async def acquire(
        self,
        *keys: str,
        ttl_seconds: int = 30,
    ) -> AsyncIterator[None]:
        """
        Acquire distributed locks on all given keys atomically.
        Releases all locks on context manager exit (success or exception).

        WHY ttl_seconds default is 30 and not shorter:
        The transfer flow includes two DB operations (debit + credit)
        plus network round trips to Redis and Postgres. Under load,
        this can take several seconds. A TTL that's too short causes
        the lock to expire mid-transfer, allowing a concurrent worker
        to start — exactly the race we're preventing.

        Raises:
            ConcurrencyConflictError: if any lock cannot be acquired
                                      within the wait timeout.
                                      Maps to HTTP 409 — client should retry.
        """
        yield
