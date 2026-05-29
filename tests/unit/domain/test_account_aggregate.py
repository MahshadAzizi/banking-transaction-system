from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.domain.entities.account import Account
from src.domain.events.account import (
    AccountClosed,
    AccountCreated,
    AccountFrozen,
    AccountUnfrozen,
    BalanceCredited,
    BalanceDebited,
)
from src.domain.exceptions.account import (
    AccountClosedError,
    AccountFrozenError,
    AccountNotEmptyError,
    InsufficientFundsError,
)
from src.domain.value_objects.enums import AccountStatus, Currency
from src.domain.value_objects.identifiers import OwnerId
from src.domain.value_objects.money import Money
from tests.conftest import make_account


class TestAccountCreate:
    def test_create_emits_account_created_event(self):
        account = Account.create(owner_id=OwnerId(uuid4()), currency=Currency.EUR)
        events = account.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], AccountCreated)

    def test_create_sets_active_status(self):
        account = Account.create(owner_id=OwnerId(uuid4()), currency=Currency.EUR)
        assert account.status == AccountStatus.ACTIVE

    def test_create_with_zero_balance_by_default(self):
        account = Account.create(owner_id=OwnerId(uuid4()), currency=Currency.EUR)
        assert account.balance.is_zero()

    def test_create_with_initial_balance(self):
        account = Account.create(
            owner_id=OwnerId(uuid4()),
            currency=Currency.EUR,
            initial_balance=Money(Decimal("250"), Currency.EUR),
        )
        assert account.balance.amount == Decimal("250.00")

    def test_reconstitute_emits_no_events(self):
        original = Account.create(owner_id=OwnerId(uuid4()), currency=Currency.EUR)
        original.collect_events()
        rebuilt = Account.reconstitute(
            id=original.id,
            owner_id=original.owner_id,
            account_number=original.account_number,
            balance=original.balance,
            status=original.status,
            created_at=original.created_at,
            updated_at=original.updated_at,
        )
        assert rebuilt.collect_events() == []


class TestDebit:
    def test_debit_reduces_balance(self):
        account = make_account(balance=Decimal("500"))
        account.debit(Money(Decimal("100"), Currency.EUR), uuid4())
        assert account.balance.amount == Decimal("400.00")

    def test_debit_emits_balance_debited_event(self):
        account = make_account(balance=Decimal("500"))
        account.debit(Money(Decimal("100"), Currency.EUR), uuid4())
        events = account.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], BalanceDebited)
        assert events[0].balance_after == Decimal("400.00")

    def test_debit_raises_on_insufficient_funds(self):
        account = make_account(balance=Decimal("50"))
        with pytest.raises(InsufficientFundsError) as exc_info:
            account.debit(Money(Decimal("100"), Currency.EUR), uuid4())
        assert exc_info.value.available.amount == Decimal("50.00")
        assert exc_info.value.requested.amount == Decimal("100.00")

    def test_debit_raises_on_frozen_account(self):
        account = make_account(balance=Decimal("500"))
        account.freeze("compliance hold")
        account.collect_events()
        with pytest.raises(AccountFrozenError):
            account.debit(Money(Decimal("100"), Currency.EUR), uuid4())

    def test_debit_raises_on_closed_account(self):
        account = make_account(balance=Decimal("0"))
        account.close()
        account.collect_events()
        with pytest.raises(AccountClosedError):
            account.debit(Money(Decimal("0"), Currency.EUR), uuid4())


class TestCredit:
    def test_credit_increases_balance(self):
        account = make_account(balance=Decimal("100"))
        account.credit(Money(Decimal("50"), Currency.EUR), uuid4())
        assert account.balance.amount == Decimal("150.00")

    def test_credit_emits_balance_credited_event(self):
        account = make_account(balance=Decimal("100"))
        account.credit(Money(Decimal("50"), Currency.EUR), uuid4())
        events = account.collect_events()
        assert isinstance(events[0], BalanceCredited)
        assert events[0].balance_after == Decimal("150.00")

    def test_credit_raises_on_frozen_account(self):
        account = make_account()
        account.freeze("test")
        account.collect_events()
        with pytest.raises(AccountFrozenError):
            account.credit(Money(Decimal("10"), Currency.EUR), uuid4())


class TestFreezeUnfreeze:
    def test_freeze_changes_status(self):
        account = make_account()
        account.freeze("suspicious activity")
        assert account.status == AccountStatus.FROZEN

    def test_freeze_emits_account_frozen_event(self):
        account = make_account()
        account.freeze("suspicious activity")
        events = account.collect_events()
        assert isinstance(events[0], AccountFrozen)
        assert events[0].reason == "suspicious activity"

    def test_freeze_is_idempotent(self):
        account = make_account()
        account.freeze("reason")
        account.freeze("reason again")  # should not raise
        events = account.collect_events()
        frozen_events = [e for e in events if isinstance(e, AccountFrozen)]
        assert len(frozen_events) == 1  # only emitted once

    def test_unfreeze_restores_active_status(self):
        account = make_account()
        account.freeze("test")
        account.collect_events()
        account.unfreeze()
        assert account.status == AccountStatus.ACTIVE

    def test_unfreeze_emits_account_unfrozen_event(self):
        account = make_account()
        account.freeze("test")
        account.collect_events()
        account.unfreeze()
        events = account.collect_events()
        assert isinstance(events[0], AccountUnfrozen)

    def test_unfreeze_is_idempotent(self):
        account = make_account()
        account.unfreeze()  # already active — should not raise


class TestClose:
    def test_close_changes_status(self):
        account = make_account(balance=Decimal("0"))
        account.close()
        assert account.status == AccountStatus.CLOSED

    def test_close_emits_account_closed_event(self):
        account = make_account(balance=Decimal("0"))
        account.close()
        events = account.collect_events()
        assert isinstance(events[0], AccountClosed)

    def test_close_raises_when_balance_not_zero(self):
        account = make_account(balance=Decimal("100"))
        with pytest.raises(AccountNotEmptyError):
            account.close()

    def test_closed_account_blocks_all_operations(self):
        account = make_account(balance=Decimal("0"))
        account.close()
        account.collect_events()
        with pytest.raises(AccountClosedError):
            account.debit(Money(Decimal("0"), Currency.EUR), uuid4())
        with pytest.raises(AccountClosedError):
            account.credit(Money(Decimal("0"), Currency.EUR), uuid4())
        with pytest.raises(AccountClosedError):
            account.freeze("test")
