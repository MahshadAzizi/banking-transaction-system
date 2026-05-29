from __future__ import annotations

from src.application.ports.outbound.account_repository import IAccountRepository
from src.domain.entities.account import Account
from src.domain.value_objects.identifiers import AccountId


class InMemoryAccountRepository(IAccountRepository):
    """
    In-memory implementation of IAccountRepository for unit tests.

    Unit tests for TransferService should not require a running Postgres.
    With this implementation, tests run in milliseconds and work anywhere —
    no Docker, no migrations, no network.

    The DI container swaps this in for the test environment in one line.
    The service is completely unaware of which implementation it gets.
    """

    def __init__(self) -> None:
        self._store: dict[AccountId, Account] = {}
        self.seen: list[Account] = []

    async def get(self, account_id: AccountId) -> Account | None:
        account = self._store.get(account_id)
        if account:
            self.seen.append(account)
        return account

    async def get_with_lock(self, account_id: AccountId) -> Account | None:
        """
        No actual locking in-memory — lock semantics are a DB concept.
        For tests, get_with_lock behaves identically to get.
        Concurrency tests use real Postgres.
        """
        return await self.get(account_id)

    async def save(self, account: Account) -> None:
        self._store[AccountId(account.id)] = account

    async def exists(self, account_id: AccountId) -> bool:
        return account_id in self._store

    def add(self, account: Account) -> None:
        """Test helper — seed the store directly without going through save()."""
        self._store[AccountId(account.id)] = account
