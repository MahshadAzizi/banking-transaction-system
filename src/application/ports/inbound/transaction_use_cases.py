from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.application.dtos.transaction import TransactionDTO, TransferCommand


@runtime_checkable
class IInitiateTransfer(Protocol):
    """
    Inbound port — initiate a money transfer between two accounts.

    This is the most critical port in the system. The implementation
    (TransferService) orchestrates:
      idempotency check → distributed lock → UoW → domain calls →
      commit → event publish → cache result

    The HTTP router knows nothing about any of that — it only calls
    execute() and gets a TransactionDTO back.
    """

    async def execute(self, command: TransferCommand) -> TransactionDTO: ...


@runtime_checkable
class IGetTransaction(Protocol):
    """
    Inbound port — retrieve transaction details by ID.

    WHY a separate port from IInitiateTransfer:
    These are different use cases with different security requirements.
    In a real system, reading a transaction may be permitted to
    the sender, receiver, or compliance — but not necessarily all three.
    Separate ports allow separate authorisation logic without coupling.
    """

    async def execute(self, transaction_id: UUID) -> TransactionDTO: ...
