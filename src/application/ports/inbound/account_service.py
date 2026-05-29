from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.application.dtos.account import AccountDTO, CreateAccountCommand


@runtime_checkable
class IAccountService(Protocol):
    """
    Inbound port — create a new bank account and get bank account details by ID.
    """

    async def create(self, command: CreateAccountCommand) -> AccountDTO: ...

    async def get(self, account_id: UUID) -> AccountDTO: ...
