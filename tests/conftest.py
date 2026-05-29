from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.adapters.outbound.locking.in_memory_lock_manager import InMemoryLockManager
from src.adapters.outbound.messaging.in_memory_event_bus import InMemoryEventBus
from src.adapters.outbound.persistence.in_memory_unit_of_work import InMemoryUnitOfWork
from src.adapters.outbound.persistence.repositories.in_memory_account_repository import (
    InMemoryAccountRepository,
)
from src.adapters.outbound.persistence.repositories.in_memory_transaction_repository import (
    InMemoryTransactionRepository,
)
from src.application.services.transfer import TransferService
from src.domain.entities.account import Account
from src.domain.value_objects.enums import Currency
from src.domain.value_objects.identifiers import AccountId, OwnerId
from src.domain.value_objects.money import Money


@pytest.fixture
def account_repo() -> InMemoryAccountRepository:
    return InMemoryAccountRepository()


@pytest.fixture
def transaction_repo() -> InMemoryTransactionRepository:
    return InMemoryTransactionRepository()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
def lock_manager() -> InMemoryLockManager:
    return InMemoryLockManager()


@pytest.fixture
def uow(
    account_repo: InMemoryAccountRepository,
    transaction_repo: InMemoryTransactionRepository,
) -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork(accounts=account_repo, transactions=transaction_repo)


@pytest.fixture
def transfer_service(
    uow: InMemoryUnitOfWork,
    lock_manager: InMemoryLockManager,
    event_bus: InMemoryEventBus,
) -> TransferService:
    return TransferService(uow=uow, lock_manager=lock_manager, event_bus=event_bus)


def make_account(
    balance: Decimal = Decimal("500"),
    currency: Currency = Currency.EUR,
) -> Account:
    """Test helper — create an account with a given balance."""
    account = Account.create(
        owner_id=OwnerId(uuid4()),
        currency=currency,
        initial_balance=Money(amount=balance, currency=currency),
    )
    account.collect_events()  # clear AccountCreated so tests start clean
    return account


def make_transfer_command(
    from_account_id: AccountId,
    to_account_id: AccountId,
    amount: Decimal = Decimal("100"),
    currency: Currency = Currency.EUR,
    idempotency_key: str | None = None,
):
    from src.application.dtos.transaction import TransferCommand

    return TransferCommand(
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amount,
        currency=currency.value,
        idempotency_key=idempotency_key or str(uuid4()),
    )
