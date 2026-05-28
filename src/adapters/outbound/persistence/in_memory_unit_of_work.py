from __future__ import annotations

from types import TracebackType

from src.adapters.outbound.persistence.repositories.in_memory_account_repository import (
    InMemoryAccountRepository,
)
from src.adapters.outbound.persistence.repositories.in_memory_transaction_repository import (
    InMemoryTransactionRepository,
)
from src.application.ports.outbound.unit_of_work import IUnitOfWork


class InMemoryUnitOfWork(IUnitOfWork):
    """
    In-memory UoW for unit tests.

    No real transactions — commit() and rollback() are no-ops.
    Tests that need real atomicity must use the Postgres UoW
    with a test database (integration tests).
    """

    def __init__(
        self,
        accounts: InMemoryAccountRepository | None = None,
        transactions: InMemoryTransactionRepository | None = None,
    ) -> None:
        self.accounts = accounts or InMemoryAccountRepository()
        self.transactions = transactions or InMemoryTransactionRepository()
        self._committed = False

    async def __aenter__(self) -> InMemoryUnitOfWork:
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        self._committed = True

    async def rollback(self) -> None:
        pass

    @property
    def was_committed(self) -> bool:
        """Test helper — assert the UoW was committed."""
        return self._committed
