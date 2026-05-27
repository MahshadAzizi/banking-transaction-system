from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.transaction import Transaction
from src.domain.value_objects.identifiers import IdempotencyKey, TransactionId


@runtime_checkable
class ITransactionRepository(Protocol):
    """
    Outbound port — persistence contract for Transaction aggregates.

    WHY get_by_idempotency_key is a first-class method here:
    Idempotency lookup is on the hot path of every transfer request.
    Making it explicit on the repository (not a generic filter) means:
    1. Implementations can index on idempotency_key efficiently.
    2. The service code reads as intent: "get by idempotency key",
       not "filter by field equals value".
    3. The in-memory implementation can use a dict keyed by
       idempotency_key for O(1) lookup without scanning all transactions.
    """

    async def get(self, transaction_id: TransactionId) -> Transaction | None:
        """
        Load a transaction by its ID.
        Returns None if not found.
        """
        ...

    async def get_by_idempotency_key(self, key: IdempotencyKey) -> Transaction | None:
        """
        Load a transaction by its idempotency key.
        Returns None if no transaction with this key exists.

        WHY used by the service rather than checking a cache only:
        Redis can evict keys (TTL or memory pressure). The DB is the
        source of truth for idempotency — Redis is only the fast path.
        If Redis misses, the service falls back to this method.
        """
        ...

    async def save(self, transaction: Transaction) -> None:
        """
        Persist a new or updated transaction aggregate.
        Must be called inside an active UoW transaction.
        """
        ...
