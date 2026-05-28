from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.application.dtos.transaction import TransactionDTO, TransferCommand


@runtime_checkable
class ITransferService(Protocol):
    """
    Inbound port — initiate a money transfer between two accounts and get money transfer details by id
    """

    async def initiate(self, command: TransferCommand) -> TransactionDTO: ...

    async def get(self, transaction_id: UUID) -> TransactionDTO: ...
