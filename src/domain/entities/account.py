from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from src.domain.entities.base import AggregateRoot, _now
from src.domain.events.account import (
    AccountClosed,
    AccountCreated,
    AccountFrozen,
    AccountUnfrozen,
    BalanceCredited,
    BalanceDebited,
)
from src.domain.exceptions.base import CurrencyMismatchError

from src.domain.exceptions.account import (
    AccountClosedError,
    AccountFrozenError,
    AccountNotEmptyError,
)
from src.domain.value_objects.enums import AccountStatus, Currency
from src.domain.value_objects.identifiers import AccountId
from src.domain.value_objects.money import Money


def _generate_account_number() -> str:
    import random

    digits = "".join(str(random.randint(0, 9)) for _ in range(16))
    return f"DE{digits}"


@dataclass
class Account(AggregateRoot):
    """
    Account aggregate root.
    """

    owner_id: UUID = field(default_factory=UUID)
    account_number: str = field(default="")
    status: AccountStatus = field(default=AccountStatus.ACTIVE)
    _balance: Money = field(default=None, init=False, repr=False)

    @classmethod
    def create(
        cls,
        owner_id: UUID,
        currency: Currency,
        initial_balance: Money | None = None,
    ) -> Account:
        """
        Open a new account.
        """
        balance = initial_balance or Money(amount=Decimal("0"), currency=currency)

        if balance.currency != currency:
            raise CurrencyMismatchError(balance.currency, currency)

        account = cls(
            owner_id=owner_id,
            account_number=_generate_account_number(),
            status=AccountStatus.ACTIVE,
        )
        object.__setattr__(account, "_balance", balance)

        account._record_event(
            AccountCreated(
                account_id=account.id,
                owner_id=owner_id,
                currency=balance.currency.value,
                initial_balance=balance.amount,
            )
        )
        return account

    @classmethod
    def reconstitute(
        cls,
        id: UUID,
        owner_id: UUID,
        account_number: str,
        balance: Money,
        status: AccountStatus,
        created_at: datetime,
        updated_at: datetime,
    ) -> Account:
        """
        Rebuild from persistence — no events emitted.
        """
        account = cls(
            owner_id=owner_id,
            account_number=account_number,
            status=status,
        )
        object.__setattr__(account, "id", id)
        object.__setattr__(account, "_balance", balance)
        object.__setattr__(account, "created_at", created_at)
        object.__setattr__(account, "updated_at", updated_at)
        return account

    @property
    def balance(self) -> Money:
        return self._balance

    @property
    def currency(self) -> Currency:
        """Derived — always consistent with balance. Never stored separately."""
        return self._balance.currency

    def debit(self, amount: Money, transaction_id: UUID) -> None:
        self._assert_not_closed()
        self._assert_not_frozen()
        self._balance = self._balance - amount
        self.updated_at = _now()
        self._record_event(
            BalanceDebited(
                account_id=self.id,
                transaction_id=transaction_id,
                amount=amount.amount,
                currency=amount.currency.value,
                balance_after=self._balance.amount,
            )
        )

    def credit(self, amount: Money, transaction_id: UUID) -> None:
        self._assert_not_closed()
        self._assert_not_frozen()
        self._balance = self._balance + amount
        self.updated_at = _now()
        self._record_event(
            BalanceCredited(
                account_id=self.id,
                transaction_id=transaction_id,
                amount=amount.amount,
                currency=amount.currency.value,
                balance_after=self._balance.amount,
            )
        )

    def freeze(self, reason: str) -> None:
        self._assert_not_closed()
        if self.status == AccountStatus.FROZEN:
            return
        self.status = AccountStatus.FROZEN
        self.updated_at = _now()
        self._record_event(
            AccountFrozen(
                account_id=self.id,
                owner_id=self.owner_id,
                reason=reason,
            )
        )

    def unfreeze(self) -> None:
        self._assert_not_closed()
        if self.status == AccountStatus.ACTIVE:
            return
        self.status = AccountStatus.ACTIVE
        self.updated_at = _now()
        self._record_event(
            AccountUnfrozen(
                account_id=self.id,
                owner_id=self.owner_id,
            )
        )

    def close(self) -> None:
        self._assert_not_closed()
        if not self._balance.is_zero():
            raise AccountNotEmptyError(AccountId(self.id), self._balance)
        self.status = AccountStatus.CLOSED
        self.updated_at = _now()
        self._record_event(
            AccountClosed(
                account_id=self.id,
                owner_id=self.owner_id,
            )
        )

    def _assert_not_closed(self) -> None:
        if self.status == AccountStatus.CLOSED:
            raise AccountClosedError(AccountId(self.id))

    def _assert_not_frozen(self) -> None:
        if self.status == AccountStatus.FROZEN:
            raise AccountFrozenError(AccountId(self.id))
