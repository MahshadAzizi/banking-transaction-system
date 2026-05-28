from __future__ import annotations

from src.application.ports.outbound.transaction_repository import ITransactionRepository
from src.domain.entities.transaction import Transaction
from src.domain.value_objects.identifiers import IdempotencyKey, TransactionId


class InMemoryTransactionRepository(ITransactionRepository):
    def __init__(self) -> None:
        self._store: dict[TransactionId, Transaction] = {}
        self._by_idempotency: dict[str, TransactionId] = {}
        self.seen: list[Transaction] = []

    async def get(self, transaction_id: TransactionId) -> Transaction | None:
        return self._store.get(transaction_id)

    async def get_by_idempotency_key(self, key: IdempotencyKey) -> Transaction | None:
        tx_id = self._by_idempotency.get(str(key))
        if tx_id is None:
            return None
        return self._store.get(tx_id)

    async def save(self, transaction: Transaction) -> None:
        self._store[TransactionId(transaction.id)] = transaction
        self._by_idempotency[str(transaction.idempotency_key)] = TransactionId(
            transaction.id
        )
