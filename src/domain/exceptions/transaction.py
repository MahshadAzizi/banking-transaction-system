from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.exceptions.base import DomainException

if TYPE_CHECKING:
    from src.domain.value_objects.identifiers import (
        IdempotencyKey,
        TransactionId,
        AccountId,
    )
    from src.domain.value_objects.money import Money


class InvalidTransferAmountError(DomainException):
    """
    Raised when the transfer amount is zero or negative.

    WHY raised in Transaction.initiate() and not in Money.__init__:
    Money(0) is valid in other contexts (opening balance, zero-value
    assertions in tests). Zero is only invalid for transfers specifically.
    This is a transaction business rule, not a Money invariant.
    """

    def __init__(self, amount: Money) -> None:
        super().__init__(f"Transfer amount must be greater than zero. Got: {amount}.")
        self.amount = amount


class SameAccountTransferError(DomainException):
    """
    Raised when from_account_id == to_account_id.

    WHY this check lives in the aggregate and not the service:
    This is a domain invariant — a transfer to yourself is structurally
    meaningless regardless of any business context. It cannot be made
    valid by any service-level condition, so the aggregate enforces it.
    """

    def __init__(self, account_id: AccountId) -> None:
        super().__init__(f"Cannot transfer to the same account: '{account_id}'.")
        self.account_id = account_id


class TransactionAlreadyProcessingError(DomainException):
    """
    Raised when mark_processing() is called on a non-PENDING transaction.

    WHY this is a domain error and not a programming error (AssertionError):
    In a distributed system, two workers can simultaneously pick up the
    same transaction. The first succeeds; the second hits this error.
    This is an expected race condition, not a bug — it needs a domain name.
    The service layer catches this and treats it as a concurrent operation
    to retry or discard, not as a crash.
    """

    def __init__(self, transaction_id: TransactionId, current_status: str) -> None:
        super().__init__(
            f"Transaction '{transaction_id}' cannot move to PROCESSING: "
            f"current status is '{current_status}'. "
            f"Only PENDING transactions can begin processing."
        )
        self.transaction_id = transaction_id
        self.current_status = current_status


class TransactionAlreadyCompletedError(DomainException):
    """
    Raised when complete() is called on a non-PROCESSING transaction.

    The most important case: calling complete() twice.
    The second call must be rejected — idempotent completion would silently
    double-credit the receiver if the service retried carelessly.
    """

    def __init__(self, transaction_id: TransactionId, current_status: str) -> None:
        super().__init__(
            f"Transaction '{transaction_id}' cannot be completed: "
            f"current status is '{current_status}'. "
            f"Only PROCESSING transactions can complete."
        )
        self.transaction_id = transaction_id
        self.current_status = current_status


class TransactionNotFailableError(DomainException):
    """
    Raised when fail() is called on an already-terminal transaction.

    WHY COMPLETED cannot be failed:
    Money has already moved. To undo a completed transfer you must
    use a reversal (separate Transaction with type=REVERSAL), not
    mark the original as failed. This preserves the audit trail.
    """

    def __init__(self, transaction_id: TransactionId, current_status: str) -> None:
        super().__init__(
            f"Transaction '{transaction_id}' cannot be failed: "
            f"current status is '{current_status}'. "
            f"To reverse a COMPLETED transfer, create a REVERSAL transaction."
        )
        self.transaction_id = transaction_id
        self.current_status = current_status


class DuplicateIdempotencyKeyError(DomainException):
    """
    Raised by the repository when an idempotency key is already stored.
    The service layer catches this and returns the original transaction
    instead of creating a new one — safe client retry semantics.

    WHY raised by repository and not the aggregate:
    The aggregate has no access to storage. Only the repository can
    detect that a key already exists in the database.
    The aggregate handles all other invariants; this one is structural.
    """

    def __init__(
        self,
        idempotency_key: IdempotencyKey,
        existing_transaction_id: TransactionId,
    ) -> None:
        super().__init__(
            f"Idempotency key '{idempotency_key}' was already used "
            f"by transaction '{existing_transaction_id}'. "
            f"Return the existing transaction — do not create a duplicate."
        )
        self.idempotency_key = idempotency_key
        self.existing_transaction_id = existing_transaction_id


class TransactionRollbackError(DomainException):
    """
    Raised when mark_rolled_back() is called on a transaction that
    was not in a rollback-eligible state.

    Rollback is only valid after PROCESSING→FAILED where the debit
    was already applied. Calling rollback on a PENDING→FAILED transaction
    (where no debit occurred) is a service logic error.
    """

    def __init__(self, transaction_id: TransactionId, current_status: str) -> None:
        super().__init__(
            f"Transaction '{transaction_id}' cannot be rolled back: "
            f"current status is '{current_status}'. "
            f"Rollback is only valid for FAILED transactions that reached PROCESSING."
        )
        self.transaction_id = transaction_id
        self.current_status = current_status
