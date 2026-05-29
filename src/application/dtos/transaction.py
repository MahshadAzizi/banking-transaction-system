from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from src.domain.entities.transaction import Transaction


@dataclass(frozen=True)
class TransferCommand:
    """
    Carries transfer intent from HTTP adapter → TransferService.

    WHY idempotency_key is str here (not IdempotencyKey NewType):
    Same reasoning as CreateAccountCommand — the adapter constructs
    this from raw HTTP input. The service wraps it in IdempotencyKey
    before passing to the domain.

    WHY amount is Decimal and not Money:
    Money requires Currency enum — the adapter works with raw strings.
    The service constructs Money(amount, Currency[currency]) internally.
    This keeps the command simple and adapter-friendly.
    """

    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal
    currency: str
    idempotency_key: str


@dataclass(frozen=True)
class TransactionDTO:
    """
    Read-only snapshot of Transaction aggregate state.

    WHY rollback_required is NOT on the DTO:
    rollback_required is an internal orchestration concern for the service.
    The HTTP client never needs to know whether a rollback is in progress —
    they see the final status (FAILED or COMPLETED). Exposing internal
    compensation state to the API would be a leaky abstraction.
    """

    id: UUID
    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal
    currency: str
    status: str
    idempotency_key: str
    failure_code: str | None
    failure_reason: str | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_aggregate(cls, tx: object) -> TransactionDTO:
        """Map Transaction aggregate → TransactionDTO."""
        assert isinstance(tx, Transaction)
        return cls(
            id=tx.id,
            from_account_id=tx.from_account_id,
            to_account_id=tx.to_account_id,
            amount=tx.amount.amount,
            currency=tx.amount.currency.value,
            status=tx.status.value,
            idempotency_key=str(tx.idempotency_key),
            failure_code=tx.failure_code,
            failure_reason=tx.failure_reason,
            created_at=tx.created_at,
            completed_at=tx.completed_at,
        )
