from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from src.application.dtos.account import CreateAccountCommand, AccountDTO
from src.application.ports.inbound.account_service import IAccountService
from src.application.ports.outbound.unit_of_work import IUnitOfWork
from src.domain.entities.account import Account
from src.domain.exceptions.base import ResourceNotFoundError
from src.domain.value_objects.enums import Currency
from src.domain.value_objects.identifiers import AccountId

from src.domain.value_objects.money import Money


class AccountService(IAccountService):
    """
    Implements account use cases — create and retrieve.

    Dependencies injected as Protocol interfaces
    """

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def create(self, command: CreateAccountCommand) -> AccountDTO:
        """
        ICreateAccount — open a new bank account.

        Flow:
            1. Build domain value objects from command primitives
            2. Call Account.create() — emits AccountCreated event
            3. Persist via UoW (atomic)
            4. Return DTO — never the aggregate directly
        """
        currency = Currency(command.currency)
        initial_balance = Money(
            amount=Decimal(str(command.initial_balance)),
            currency=currency,
        )

        account = Account.create(
            owner_id=command.owner_id,
            currency=currency,
            initial_balance=initial_balance,
        )
        async with self._uow as uow:
            await uow.accounts.save(account)
            await uow.commit()

        return AccountDTO.from_aggregate(account)

    async def get(self, account_id: UUID) -> AccountDTO:
        async with self._uow as uow:
            account = await uow.accounts.get(AccountId(account_id))
            if account is None:
                raise ResourceNotFoundError("Account", account_id)
            return AccountDTO.from_aggregate(account)
