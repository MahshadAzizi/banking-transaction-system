from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.application.ports.outbound.account_repository import IAccountRepository
    from src.application.ports.outbound.transaction_repository import (
        ITransactionRepository,
    )


@runtime_checkable
class IUnitOfWork(Protocol):
    """
    Outbound port — atomic transaction boundary.

    The UoW is the most important outbound port in the system.
    It answers the question: "how do I make multiple repository operations
    atomic without the service knowing about database sessions?"

    Usage in TransferService:
        async with self._uow as uow:
            sender  = await uow.accounts.get_with_lock(from_id)
            receiver = await uow.accounts.get_with_lock(to_id)
            sender.debit(amount)
            receiver.credit(amount)
            await uow.transactions.save(tx)
            await uow.commit()
            # exception here → auto rollback via __aexit__

    WHY the repositories are on the UoW and not injected separately:
    The sender and receiver accounts must be loaded, modified, and saved
    within the SAME database session for the changes to be atomic.
    If AccountRepository had its own session, the debit on sender and
    credit on receiver would be in separate transactions — no atomicity.

    The UoW owns the session and injects it into the repositories it
    exposes. This is the only way to guarantee they share the same
    transaction boundary.

    WHY commit() is explicit (not automatic on __aexit__):
    Explicit commit makes the intent clear at the call site. The service
    author knows exactly where the transaction commits — there is no
    implicit "if no exception, commit" magic that can fire unexpectedly.
    __aexit__ always rolls back if commit() was not called.
    """

    accounts: IAccountRepository
    transactions: ITransactionRepository

    async def commit(self) -> None:
        """
        Commit the current transaction.
        Also flushes all domain events from touched aggregates
        to the outbox table in the same atomic operation.
        """
        ...

    async def rollback(self) -> None:
        """
        Roll back the current transaction.
        Called automatically by __aexit__ if commit() was not called
        or if an exception propagates out of the async with block.
        """
        ...

    async def __aenter__(self) -> IUnitOfWork:
        """
        Open a new database session and start a transaction (BEGIN).
        Initialises self.accounts and self.transactions with repositories
        that share this session.
        """
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """
        If commit() was called: close the session cleanly.
        If commit() was NOT called (exception or forgotten): rollback.
        """
        ...
