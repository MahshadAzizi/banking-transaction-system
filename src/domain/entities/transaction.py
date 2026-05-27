from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.entities.base import AggregateRoot, _now
from src.domain.events.transaction import (
    TransactionCompleted,
    TransactionFailed,
    TransactionInitiated,
    TransactionProcessing,
    TransactionRolledBack,
)
from src.domain.exceptions.transaction import (
    InvalidTransferAmountError,
    SameAccountTransferError,
    TransactionAlreadyCompletedError,
    TransactionAlreadyProcessingError,
    TransactionNotFailableError,
    TransactionRollbackError,
)
from src.domain.value_objects.enums import TransactionStatus, TransactionType
from src.domain.value_objects.identifiers import (
    AccountId,
    IdempotencyKey,
    TransactionId,
    new_transaction_id,
)
from src.domain.value_objects.money import Money


@dataclass
class Transaction(AggregateRoot):
    """
    Transaction aggregate root.

    Owns transfer lifecycle and transaction state transitions.

    A transaction references accounts by ID only to preserve
    aggregate isolation and avoid cross-aggregate coupling.

    Lifecycle:
    PENDING -> PROCESSING -> COMPLETED
    PENDING -> FAILED
    PROCESSING -> FAILED -> ROLLED BACK
    """

    from_account_id: AccountId = field(default=None, init=False, repr=True)
    to_account_id: AccountId = field(default=None, init=False, repr=True)
    _amount: Money = field(default=None, init=False, repr=False)
    transaction_type: TransactionType = field(default=TransactionType.TRANSFER)
    status: TransactionStatus = field(default=TransactionStatus.PENDING)
    idempotency_key: IdempotencyKey = field(default_factory=lambda: IdempotencyKey(""))
    failure_code: str | None = field(default=None)
    _rollback_required: bool = field(default=False, init=False, repr=False)
    failure_reason: str | None = field(default=None)
    completed_at: datetime | None = field(default=None)

    @classmethod
    def initiate(
            cls,
            from_account_id: AccountId,
            to_account_id: AccountId,
            amount: Money,
            idempotency_key: IdempotencyKey,
            transaction_type: TransactionType = TransactionType.TRANSFER,
    ) -> Transaction:
        """
        Create and validate a new transfer.

        WHY validation lives here and not in the service:
        These are structural invariants of what a transfer IS — a transfer
        to yourself is not a transfer, a zero-amount transfer is not a transfer.
        No service-layer context changes these facts. The aggregate enforces
        them unconditionally, making it impossible to create an invalid
        transaction regardless of which service calls initiate().

        WHY we do NOT check account balances here:
        Balance is owned by the Account aggregate. Transaction has no
        access to Account objects — that would violate aggregate isolation.
        Insufficient funds is caught later when Account.debit() is called
        inside the transfer service. Transaction records that failure via fail().
        """
        if amount.is_zero():
            raise InvalidTransferAmountError(amount)

        if from_account_id == to_account_id:
            raise SameAccountTransferError(from_account_id)

        tx = cls(
            transaction_type=transaction_type,
            status=TransactionStatus.PENDING,
            idempotency_key=idempotency_key,
        )
        object.__setattr__(tx, "id", new_transaction_id())
        object.__setattr__(tx, "from_account_id", from_account_id)
        object.__setattr__(tx, "to_account_id", to_account_id)
        object.__setattr__(tx, "_amount", amount)

        tx._record_event(
            TransactionInitiated(
                transaction_id=tx.id,
                from_account_id=from_account_id,
                to_account_id=to_account_id,
                amount=amount.amount,
                currency=amount.currency.value,
                idempotency_key=str(idempotency_key),
            )
        )
        return tx

    @classmethod
    def reconstitute(
            cls,
            id: TransactionId,
            from_account_id: AccountId,
            to_account_id: AccountId,
            amount: Money,
            transaction_type: TransactionType,
            status: TransactionStatus,
            idempotency_key: IdempotencyKey,
            created_at: datetime,
            updated_at: datetime,
            failure_code: str | None = None,
            failure_reason: str | None = None,
            completed_at: datetime | None = None,
    ) -> Transaction:
        """Rebuild from persistence — no events, no validation."""
        tx = cls(
            transaction_type=transaction_type,
            status=status,
            idempotency_key=idempotency_key,
            failure_code=failure_code,
            failure_reason=failure_reason,
            completed_at=completed_at,
        )
        object.__setattr__(tx, "id", id)
        object.__setattr__(tx, "from_account_id", from_account_id)
        object.__setattr__(tx, "to_account_id", to_account_id)
        object.__setattr__(tx, "_amount", amount)
        object.__setattr__(tx, "created_at", created_at)
        object.__setattr__(tx, "updated_at", updated_at)
        return tx

    @property
    def amount(self) -> Money:
        return self._amount

    def mark_processing(self) -> None:
        """
        Advance from PENDING to PROCESSING.
        Called by the service after acquiring the distributed lock and
        before calling Account.debit().

        WHY raise on non-PENDING rather than silently ignoring:
        If this transaction is already PROCESSING, something is wrong —
        two workers are processing the same transfer simultaneously.
        The second worker must fail loudly, not silently succeed.
        The service catches TransactionAlreadyProcessingError and aborts.
        """
        if not self.status.can_process():
            raise TransactionAlreadyProcessingError(
                TransactionId(self.id), self.status.value
            )

        self.status = TransactionStatus.PROCESSING
        self.updated_at = _now()

        self._record_event(
            TransactionProcessing(
                transaction_id=self.id,
                from_account_id=self.from_account_id,
                to_account_id=self.to_account_id,
                amount=self._amount.amount,
                currency=self._amount.currency.value,
            )
        )

    def complete(self) -> None:
        """
        Advance from PROCESSING to COMPLETED.
        Called by the service after both Account.debit() and Account.credit()
        have succeeded and the accounts have been persisted.

        WHY completed_at is set here (not by the DB):
        The completed_at timestamp is a business fact — the moment the transfer
        was confirmed at the domain level. Letting the DB set it means the
        timestamp reflects when the row was written, which may differ due to
        network or transaction latency. Domain-set timestamps are more precise.
        """
        if not self.status.can_complete():
            raise TransactionAlreadyCompletedError(
                TransactionId(self.id), self.status.value
            )

        self.status = TransactionStatus.COMPLETED
        self.completed_at = _now()
        self.updated_at = self.completed_at

        self._record_event(
            TransactionCompleted(
                transaction_id=self.id,
                from_account_id=self.from_account_id,
                to_account_id=self.to_account_id,
                amount=self._amount.amount,
                currency=self._amount.currency.value,
            )
        )

    def fail(self, failure_code: str, failure_reason: str) -> None:
        """
        Move to terminal FAILED state.
        Can be called from PENDING (validation failure — no debit occurred)
        or from PROCESSING (runtime failure — debit may have been applied).

        WHY rollback_required is derived from current status:
        If we are PROCESSING when fail() is called, the service has already
        called Account.debit() — those funds are gone from the sender's balance.
        The service MUST reverse them. We signal this need explicitly on the
        event rather than forcing consumers to infer it from the status history.
        """
        if not self.status.can_fail():
            raise TransactionNotFailableError(
                TransactionId(self.id), self.status.value
            )

        rollback_required = self.status == TransactionStatus.PROCESSING
        self._rollback_required = rollback_required

        self.status = TransactionStatus.FAILED
        self.failure_code = failure_code
        self.failure_reason = failure_reason
        self.updated_at = _now()

        self._record_event(
            TransactionFailed(
                transaction_id=self.id,
                from_account_id=self.from_account_id,
                to_account_id=self.to_account_id,
                amount=self._amount.amount,
                currency=self._amount.currency.value,
                failure_code=failure_code,
                failure_reason=failure_reason,
                rollback_required=rollback_required,
            )
        )

    def mark_rolled_back(self) -> None:
        """
        Record that the debit has been successfully reversed.
        Only valid on a FAILED transaction that reached PROCESSING.

        WHY this method exists on the aggregate at all:
        The rollback is observable — it must emit TransactionRolledBack so
        downstream consumers (ledger, notification) know funds are restored.
        The aggregate is the only place that can emit domain events, so
        the method must live here even though the actual Account.credit()
        call happens in the service layer.
        """
        if self.status != TransactionStatus.FAILED:
            raise TransactionRollbackError(
                TransactionId(self.id), self.status.value
            )

        self.updated_at = _now()

        self._record_event(
            TransactionRolledBack(
                transaction_id=self.id,
                from_account_id=self.from_account_id,
                amount=self._amount.amount,
                currency=self._amount.currency.value,
            )
        )

    def is_terminal(self) -> bool:
        return self.status.is_terminal()

    def requires_rollback(self) -> bool:
        return self.status == TransactionStatus.FAILED and self._rollback_required

    def __repr__(self) -> str:
        return (
            f"Transaction("
            f"id={self.id}, "
            f"{self.from_account_id}→{self.to_account_id}, "
            f"amount={self._amount}, "
            f"status={self.status.value}"
            f")"
        )
