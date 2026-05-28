from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities.account import Account
from src.domain.value_objects.identifiers import AccountId


@runtime_checkable
class IAccountRepository(Protocol):
    """
    Outbound port — persistence contract for Account aggregates.
    """

    async def get(self, account_id: AccountId) -> Account | None:
        """
        Load an account by ID without acquiring a database lock.
        Returns None if the account does not exist.
        Use for read-only operations (GET /accounts/{id}).
        """
        ...

    async def get_with_lock(self, account_id: AccountId) -> Account | None:
        """
        Load an account with SELECT FOR UPDATE — acquires a row-level DB lock.
        Must be called inside an active UoW transaction.
        Use when you intend to modify the account (transfers).
        Returns None if the account does not exist.
        """
        ...

    async def save(self, account: Account) -> None:
        """
        Persist a new or updated account aggregate.
        Uses upsert semantics — works for both create and update.
        Must be called inside an active UoW transaction.
        """
        ...

    async def exists(self, account_id: AccountId) -> bool:
        """
        Check existence without loading the full aggregate.
        Cheaper than get() when you only need to confirm presence.
        """
        ...
