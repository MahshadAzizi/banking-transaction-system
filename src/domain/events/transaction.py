from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.events.base import DomainEvent


@dataclass(frozen=True)
class TransactionInitiated(DomainEvent):
    """
    Emitted once when a transfer is created via Transaction.initiate().
    Never emitted by Transaction.reconstitute() — rebuilds from DB silently.

    WHY emit at initiation and not at completion:
    Downstream consumers (fraud detection, rate limiter, audit log) need
    to react the moment a transfer is attempted — not after it succeeds.
    A fraud signal on a PENDING transaction can still abort the transfer.

    Consumers: fraud detection, rate limiter, audit log, notification service.
    """

    transaction_id: UUID = field(default_factory=uuid4)
    from_account_id: UUID = field(default_factory=uuid4)
    to_account_id: UUID = field(default_factory=uuid4)
    amount: Decimal = field(default=Decimal("0"))
    currency: str = field(default="")
    idempotency_key: str = field(default="")


@dataclass(frozen=True)
class TransactionProcessing(DomainEvent):
    """
    Emitted when the transfer moves from PENDING → PROCESSING.
    At this point the distributed lock is held and debit is about to execute.

    WHY this event exists separately from TransactionInitiated:
    The gap between PENDING and PROCESSING is where concurrency lives.
    Consumers that build real-time ledgers need to know that funds
    are in flight — reserved but not yet settled. This event marks
    that exact moment.

    Consumers: ledger service (reserve funds), real-time balance display.
    """

    transaction_id: UUID = field(default_factory=uuid4)
    from_account_id: UUID = field(default_factory=uuid4)
    to_account_id: UUID = field(default_factory=uuid4)
    amount: Decimal = field(default=Decimal("0"))
    currency: str = field(default="")


@dataclass(frozen=True)
class TransactionCompleted(DomainEvent):
    """
    Emitted once when both debit and credit have been applied successfully.
    Terminal success event — this transaction_id will never emit again.

    WHY include both account IDs and amount:
    Each event must be self-contained. A consumer processing only this
    event (e.g. a notification service that woke up after being down)
    must not need to fetch the transaction from the DB to send the right
    notification. All context lives in the event itself.

    Consumers: notification service, ledger settlement, statement generator,
               analytics pipeline, compliance reporting.
    """

    transaction_id: UUID = field(default_factory=uuid4)
    from_account_id: UUID = field(default_factory=uuid4)
    to_account_id: UUID = field(default_factory=uuid4)
    amount: Decimal = field(default=Decimal("0"))
    currency: str = field(default="")


@dataclass(frozen=True)
class TransactionFailed(DomainEvent):
    """
    Emitted when the transfer reaches a terminal failure state.
    Can transition from PENDING (validation failure) or PROCESSING
    (debit succeeded but credit failed — rollback required).

    WHY failure_code is separate from failure_reason:
    failure_code is machine-readable: "INSUFFICIENT_FUNDS", "ACCOUNT_FROZEN".
    failure_reason is human-readable: "Sender has EUR 45.00, required EUR 100.00".
    Downstream systems route on code; humans read reason.

    WHY rollback_required is explicit on the event:
    If we failed during PROCESSING (debit already applied), the service
    must reverse the debit. Consumers that handle compensation (Saga
    orchestrator, rollback handler) need to know this without re-fetching
    transaction state.

    Consumers: rollback handler, notification service, audit log,
               fraud detection (failed transfers are signals too).
    """

    transaction_id: UUID = field(default_factory=uuid4)
    from_account_id: UUID = field(default_factory=uuid4)
    to_account_id: UUID = field(default_factory=uuid4)
    amount: Decimal = field(default=Decimal("0"))
    currency: str = field(default="")
    failure_code: str = field(default="")
    failure_reason: str = field(default="")
    rollback_required: bool = field(default=False)


@dataclass(frozen=True)
class TransactionRolledBack(DomainEvent):
    """
    Emitted after a PROCESSING transaction's debit has been reversed.
    Signals that the sender's balance is fully restored.

    This event only exists when rollback_required=True on TransactionFailed.
    It is NOT emitted for PENDING→FAILED transitions (nothing to roll back).

    WHY a dedicated event (not just TransactionFailed with rollback_required):
    The rollback is a separate DB operation that can itself fail.
    Separating the events gives consumers a clean signal for each outcome:
      TransactionFailed(rollback_required=True) → "transfer failed, rollback starting"
      TransactionRolledBack                     → "rollback complete, funds restored"

    Consumers: ledger service (release reserved funds), notification service,
               Saga orchestrator (compensation step confirmed).
    """

    transaction_id: UUID = field(default_factory=uuid4)
    from_account_id: UUID = field(default_factory=uuid4)
    amount: Decimal = field(default=Decimal("0"))
    currency: str = field(default="")


@dataclass(frozen=True)
class DuplicateTransactionDetected(DomainEvent):
    """
    Emitted when a transfer arrives with an already-used idempotency key.
    The duplicate is NOT processed — the original transaction ID is returned.

    WHY emit an event for a no-op:
    Duplicate detection is an observable operation for compliance and fraud.
    A spike in DuplicateTransactionDetected events for the same account
    may signal a replay attack or a buggy client. Silence would hide it.

    Consumers: fraud detection, audit log, observability dashboard.
    """

    idempotency_key: str = field(default="")
    original_transaction_id: UUID = field(default_factory=uuid4)
    from_account_id: UUID = field(default_factory=uuid4)
