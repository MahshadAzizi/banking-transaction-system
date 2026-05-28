from __future__ import annotations

import json
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.adapters.outbound.persistence.repositories.postgres_account_repository import (
    PostgresAccountRepository,
)
from src.adapters.outbound.persistence.repositories.postgres_transaction_repository import (
    PostgresTransactionRepository,
)

from src.adapters.outbound.persistence.models import OutboxMessageORM
from src.application.ports.outbound.unit_of_work import IUnitOfWork


class SQLAlchemyUnitOfWork(IUnitOfWork):
    """
    SQLAlchemy implementation of IUnitOfWork.

    __aenter__ opens a session and injects it into both repositories.
    Both repositories share the same session — the same DB transaction.
    This is what makes the transfer atomic: account balance changes
    and the transaction record all commit in one COMMIT statement.

    On commit(), domain events are collected from all touched aggregates
    (tracked via the .seen lists on each repository) and the session
    is committed. The outbox relay then picks up these events and
    publishes them to Kafka independently of the HTTP request.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> SQLAlchemyUnitOfWork:
        self._session: AsyncSession = self._session_factory()
        self.accounts = PostgresAccountRepository(self._session)
        self.transactions = PostgresTransactionRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        await self._session.close()

    async def commit(self) -> None:
        """
        Collect domain events from all touched aggregates,
        then commit everything atomically in one DB transaction.
        """
        await self._collect_and_store_events()
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def _collect_and_store_events(self) -> None:
        """
        Gather domain events from all touched aggregates and write
        them to the outbox table in the same transaction as the
        business data. This is the Transactional Outbox pattern.

        If the commit succeeds: both business data and outbox events land.
        If the commit fails: neither lands — no phantom events.
        """
        all_aggregates = [
            *self.accounts.seen,
            *self.transactions.seen,
        ]

        for aggregate in all_aggregates:
            for event in aggregate.collect_events():
                outbox_row = OutboxMessageORM(
                    event_type=type(event).__name__,
                    payload=json.dumps(event.to_dict()),
                    aggregate_id=str(event.event_id),
                )
                self._session.add(outbox_row)
