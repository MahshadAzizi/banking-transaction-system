from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol, runtime_checkable


@runtime_checkable
class ILockManager(Protocol):
    """
    Outbound port — distributed locking across multiple application instances.

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

    keys are always sorted before acquisition:
    Transfer A: locks [account-1, account-2]
    Transfer B: locks [account-2, account-1] ← reverse order

    Without sorting, A holds account-1 and waits for account-2,
    while B holds account-2 and waits for account-1 — deadlock.
    Sorting ensures both always acquire in the same order.

    The service is responsible for sorting:
        keys = sorted([str(from_id), str(to_id)])
        async with self._lock.acquire(*keys):

     ── Retry semantics ──────────────────────────────────────────────────
    Implementations MUST retry on contention up to wait_timeout seconds.
    A transfer that fails immediately on lock contention is not acceptable —
    locks are held for milliseconds and contention resolves quickly.
    Only raise ConcurrencyConflictError after the wait_timeout is exhausted.
    """

    def acquire(
        self,
        *keys: str,
        ttl_seconds: int = 30,
    ) -> AbstractAsyncContextManager[None]: ...
