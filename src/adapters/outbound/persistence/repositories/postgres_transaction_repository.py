from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.mappers.transaction import TransactionMapper
from src.adapters.outbound.persistence.models import TransactionORM
from src.application.ports.outbound.transaction_repository import ITransactionRepository
from src.domain.entities.transaction import Transaction
from src.domain.value_objects.identifiers import TransactionId, IdempotencyKey


class PostgresTransactionRepository(ITransactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: list[Transaction] = []

    async def get(self, transaction_id: TransactionId) -> Transaction | None:
        stmt = select(TransactionORM).where(TransactionORM.id == transaction_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        tx = TransactionMapper.to_domain(orm)
        self.seen.append(tx)
        return tx

    async def get_by_idempotency_key(self, key: IdempotencyKey) -> Transaction | None:
        """
        O(log n) lookup via the unique index on idempotency_key.
        Called on every transfer request before any lock or UoW.
        """
        stmt = select(TransactionORM).where(TransactionORM.idempotency_key == str(key))
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return TransactionMapper.to_domain(orm)

    async def save(self, transaction: Transaction) -> None:
        orm = TransactionMapper.to_orm(transaction)
        await self._session.merge(orm)
