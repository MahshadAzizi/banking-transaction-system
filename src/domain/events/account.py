from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class AccountCreated(DomainEvent):
    """
    Emitted once when an account is opened via Account.create().
    Never emitted by Account.reconstitute() — that rebuilds from DB silently.
    Consumers: audit log, notification service.
    """

    account_id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)
    currency: str = field(default="")
    initial_balance: Decimal = field(default=Decimal("0"))


@dataclass(frozen=True)
class BalanceDebited(DomainEvent):
    """
    Emitted every time money leaves an account via debit().

    WHY include balance_after:
    The ledger needs the running balance at each point in time.
    balance_after makes each event self-contained — no need to
    replay all prior events to know the state after this one.

    Consumers: ledger service, fraud detection, notification, statement generator.
    """

    account_id: UUID = field(default_factory=uuid4)
    transaction_id: UUID = field(default_factory=uuid4)
    amount: Decimal = field(default=Decimal("0"))
    currency: str = field(default="")
    balance_after: Decimal = field(default=Decimal("0"))


@dataclass(frozen=True)
class BalanceCredited(DomainEvent):
    """
    Emitted every time money enters an account via credit().
    Consumers: notification service, ledger service, statement generator.
    """

    account_id: UUID = field(default_factory=uuid4)
    transaction_id: UUID = field(default_factory=uuid4)
    amount: Decimal = field(default=Decimal("0"))
    currency: str = field(default="")
    balance_after: Decimal = field(default=Decimal("0"))


@dataclass(frozen=True)
class AccountFrozen(DomainEvent):
    """
    Emitted when freeze() is called on an ACTIVE account.
    NOT emitted if already frozen — freeze() is idempotent.
    Consumers: notification service, compliance dashboard, audit log.
    """

    account_id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)
    reason: str = field(default="")


@dataclass(frozen=True)
class AccountUnfrozen(DomainEvent):
    """
    Emitted when unfreeze() reinstates a FROZEN account to ACTIVE.
    NOT emitted if already active — unfreeze() is idempotent.
    Consumers: notification service, audit log.
    """

    account_id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AccountClosed(DomainEvent):
    """
    Terminal event — this account will never emit events again.
    Only reachable after balance reaches zero (enforced by close()).
    Consumers: audit log, data retention service.
    """

    account_id: UUID = field(default_factory=uuid4)
    owner_id: UUID = field(default_factory=uuid4)
