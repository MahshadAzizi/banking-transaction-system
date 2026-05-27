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
from src.domain.exceptions.account import (
    AccountClosedError,
    AccountFrozenError,
    AccountNotEmptyError,
)
from src.domain.value_objects.enums import AccountStatus, Currency
from src.domain.value_objects.identifiers import AccountId
from src.domain.value_objects.money import Money


def _generate_account_number() -> str:
    """
    Generates a simple internal account number.
    In production this would call a sequence or external IBAN generator.
    """
    import random

    digits = "".join(str(random.randint(0, 9)) for _ in range(16))
    return f"DE{digits}"


@dataclass
class Account(AggregateRoot):
    """
    Account aggregate root.

    Responsible for balance mutations and account state transitions.

    All balance changes must go through debit() and credit()
    to enforce domain invariants such as:
    - no overdraft
    - no transactions on closed accounts
    - controlled behavior for frozen accounts
    """

    owner_id: UUID = field(default_factory=UUID)
    account_number: str = field(default="")
    _balance: Money = field(default=None, init=False, repr=False)
    currency: Currency = field(default=Currency.EUR)
    status: AccountStatus = field(default=AccountStatus.ACTIVE)

    @classmethod
    def create(
        cls,
        owner_id: UUID,
        currency: Currency,
        initial_balance: Money | None = None,
    ) -> Account:
        """
        Open a new account.

        WHY initial_balance defaults to zero:
        Most accounts open with zero balance. A deposit is then made as a
        separate DEPOSIT transaction. This keeps the audit trail clean —
        the initial funding is a traceable transaction, not a magic value
        baked into the account creation.

        WHY account_number is generated here (not by the caller):
        Account numbers are domain-generated identifiers. Callers should
        not supply them — that would allow duplicates or invalid formats.
        In production, this calls an IBAN generation service.
        """
        zero = Money(amount=Decimal("0"), currency=currency)
        balance = initial_balance or zero

        if balance.currency != currency:
            from src.domain.exceptions.base import CurrencyMismatchError

            raise CurrencyMismatchError(balance.currency, currency)

        account = cls(
            owner_id=owner_id,
            account_number=_generate_account_number(),
            currency=currency,
            status=AccountStatus.ACTIVE,
        )
        object.__setattr__(account, "_balance", balance)

        account._record_event(
            AccountCreated(
                account_id=account.id,
                owner_id=owner_id,
                currency=currency.value,
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
        currency: Currency,
        status: AccountStatus,
        created_at: datetime,
        updated_at: datetime,
    ) -> Account:
        """Rebuild from persistence — no events emitted."""
        account = cls(
            owner_id=owner_id,
            account_number=account_number,
            currency=currency,
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

    def debit(self, amount: Money, transaction_id: UUID) -> None:
        """
        Remove money from this account.

        WHY CLOSED is checked before FROZEN:
        CLOSED is the stronger constraint. Checking FROZEN first would
        give a misleading error message for closed accounts that were
        also frozen at some point.

        WHY the insufficient-funds check lives in Money.__sub__:
        The invariant 'you cannot spend what you don't have' belongs in
        the domain, enforced by the Money value object. This makes it
        impossible to bypass regardless of which method does the subtraction.
        """
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
        """
        Add money to this account.

        WHY credit also checks FROZEN:
        A frozen account cannot receive money. This prevents a workaround
        where an attacker credits a frozen account and then immediately
        closes it to extract funds during the brief unfrozen window.
        """
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
        """
        Suspend the account.

        WHY freezing an already-frozen account is idempotent (no error):
        If the compliance service retries a freeze command after a timeout,
        the second call should not raise — the account is already in the
        desired state. Idempotency is a correctness requirement in
        distributed systems, not an edge case.
        """
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
        """Reinstate a frozen account to active status."""
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
        """
        Permanently close the account.

        WHY zero balance is required:
        Closing an account with funds makes those funds unreachable.
        The application service must transfer or withdraw the balance
        before calling close(). This invariant is enforced here — the
        service layer cannot accidentally close a funded account.

        WHY CLOSED is terminal with no exit:
        Regulatory requirement. Reopening blurs the audit trail.
        A returning customer gets a new account with a new ID.
        """
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
