from __future__ import annotations

from decimal import Decimal

from src.adapters.outbound.persistence.models import TransactionORM
from src.domain.entities.transaction import Transaction
from src.domain.value_objects.enums import Currency, TransactionStatus, TransactionType
from src.domain.value_objects.identifiers import (
    AccountId,
    IdempotencyKey,
    TransactionId,
)
from src.domain.value_objects.money import Money


class TransactionMapper:
    """
    Translates between TransactionORM (infrastructure) and Transaction (domain).

    Same split pattern as AccountMapper:
      to_domain()   → always (read path)
      to_new_orm()  → INSERT only (first save)
      update_orm()  → UPDATE only (status transitions, failure, completion)

    A transaction starts as PENDING and transitions through states.
    Each transition (mark_processing, complete, fail) must be persisted.
    The repository loads the tracked ORM row and calls update_orm()
    to apply the new state — never creates a new TransactionORM instance.
    """

    @staticmethod
    def to_domain(orm: TransactionORM) -> Transaction:
        """Rebuild domain aggregate from ORM row — no events, no validation."""
        return Transaction.reconstitute(
            id=TransactionId(orm.id),
            from_account_id=AccountId(orm.from_account_id),
            to_account_id=AccountId(orm.to_account_id),
            amount=Money(
                amount=Decimal(str(orm.amount)), currency=Currency(orm.currency)
            ),
            transaction_type=TransactionType(orm.transaction_type),
            status=TransactionStatus(orm.status),
            idempotency_key=IdempotencyKey(orm.idempotency_key),
            failure_code=orm.failure_code,
            failure_reason=orm.failure_reason,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            completed_at=orm.completed_at,
        )

    @staticmethod
    def to_new_orm(tx: Transaction) -> TransactionORM:
        """
        Build a new ORM row for first INSERT only.
        At creation time status is always PENDING — failure fields are null.
        """
        return TransactionORM(
            id=tx.id,
            from_account_id=tx.from_account_id,
            to_account_id=tx.to_account_id,
            amount=tx.amount.amount,
            currency=tx.amount.currency.value,
            transaction_type=tx.transaction_type.value,
            status=tx.status.value,
            idempotency_key=str(tx.idempotency_key),
            failure_code=tx.failure_code,
            failure_reason=tx.failure_reason,
            created_at=tx.created_at,
            updated_at=tx.updated_at,
            completed_at=tx.completed_at,
        )

    @staticmethod
    def update_orm(orm: TransactionORM, tx: Transaction) -> None:
        """
        Mutate a tracked ORM instance with the current domain aggregate state.

        Mutable fields — everything that changes during the lifecycle:
          status       → PENDING → PROCESSING → COMPLETED / FAILED
          failure_code → set when fail() is called
          failure_reason → set when fail() is called
          completed_at → set when complete() is called
          updated_at   → bumped on every state transition

        Immutable after creation (never updated here):
          id, from_account_id, to_account_id, amount, currency,
          transaction_type, idempotency_key, created_at
        """
        orm.status = tx.status.value
        orm.failure_code = tx.failure_code
        orm.failure_reason = tx.failure_reason
        orm.completed_at = tx.completed_at
        orm.updated_at = tx.updated_at
