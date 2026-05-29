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
from src.domain.value_objects.enums import TransactionStatus, TransactionType, Currency
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
    failure_reason: str | None = field(default=None)
    completed_at: datetime | None = field(default=None)
    rollback_required: bool = field(default=False)

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
                transaction_id=tx.transaction_id,
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
        rollback_required: bool = False,
    ) -> Transaction:
        """Rebuild from persistence — no events, no validation."""
        tx = cls(
            transaction_type=transaction_type,
            status=status,
            idempotency_key=idempotency_key,
            failure_code=failure_code,
            failure_reason=failure_reason,
            completed_at=completed_at,
            rollback_required=rollback_required,
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

    @property
    def currency(self) -> Currency:
        """Derived from amount — always consistent, never stored separately."""
        return self._amount.currency

    @property
    def transaction_id(self) -> TransactionId:
        """
        Typed ID — used in exception constructors.
        Avoids repeating TransactionId(self.id) at every raise site.
        """
        return TransactionId(self.id)

    def mark_processing(self) -> None:
        """
        Advance from PENDING to PROCESSING.
        Called by the service after acquiring the distributed lock and
        before calling Account.debit().
        """
        if not self.status.can_process():
            raise TransactionAlreadyProcessingError(
                self.transaction_id, self.status.value
            )
        self.status = TransactionStatus.PROCESSING
        self.updated_at = _now()
        self._record_event(
            TransactionProcessing(
                transaction_id=self.transaction_id,
                from_account_id=self.from_account_id,
                to_account_id=self.to_account_id,
                amount=self.amount.amount,
                currency=self.currency.value,
            )
        )

    def complete(self) -> None:
        """
        Advance from PROCESSING to COMPLETED.
        Called by the service after both Account.debit() and Account.credit()
        have succeeded and the accounts have been persisted.
        """
        if not self.status.can_complete():
            raise TransactionAlreadyCompletedError(
                self.transaction_id, self.status.value
            )
        self.status = TransactionStatus.COMPLETED
        self.completed_at = _now()
        self.updated_at = self.completed_at
        self._record_event(
            TransactionCompleted(
                transaction_id=self.transaction_id,
                from_account_id=self.from_account_id,
                to_account_id=self.to_account_id,
                amount=self.amount.amount,
                currency=self.currency.value,
            )
        )

    def fail(self, failure_code: str, failure_reason: str) -> None:
        """
        Move to terminal FAILED state.
        Can be called from PENDING (validation failure — no debit occurred)
        or from PROCESSING (runtime failure — debit may have been applied).
        """
        if not self.status.can_fail():
            raise TransactionNotFailableError(self.transaction_id, self.status.value)

        self.rollback_required = self.status == TransactionStatus.PROCESSING
        self.status = TransactionStatus.FAILED
        self.failure_code = failure_code
        self.failure_reason = failure_reason
        self.updated_at = _now()
        self._record_event(
            TransactionFailed(
                transaction_id=self.transaction_id,
                from_account_id=self.from_account_id,
                to_account_id=self.to_account_id,
                amount=self.amount.amount,
                currency=self.currency.value,
                failure_code=failure_code,
                failure_reason=failure_reason,
                rollback_required=self.rollback_required,
            )
        )

    def mark_rolled_back(self) -> None:
        """
        Record that the debit has been successfully reversed.
        Only valid on a FAILED transaction that reached PROCESSING.
        """
        if self.status != TransactionStatus.FAILED:
            raise TransactionRollbackError(self.transaction_id, self.status.value)
        self.updated_at = _now()
        self._record_event(
            TransactionRolledBack(
                transaction_id=self.transaction_id,
                from_account_id=self.from_account_id,
                amount=self.amount.amount,
                currency=self.currency.value,
            )
        )

    def is_terminal(self) -> bool:
        return self.status.is_terminal()

    def needs_rollback(self) -> bool:
        return self.status == TransactionStatus.FAILED and self.rollback_required

    def __repr__(self) -> str:
        return (
            f"Transaction("
            f"id={self.id}, "
            f"{self.from_account_id}→{self.to_account_id}, "
            f"amount={self._amount}, "
            f"status={self.status.value}"
            f")"
        )
