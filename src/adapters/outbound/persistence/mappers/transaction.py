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
    @staticmethod
    def to_domain(orm: TransactionORM) -> Transaction:
        return Transaction.reconstitute(
            id=TransactionId(orm.id),
            from_account_id=AccountId(orm.from_account_id),
            to_account_id=AccountId(orm.to_account_id),
            amount=Money(
                amount=Decimal(str(orm.amount)),
                currency=Currency(orm.currency),
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
    def to_orm(tx: Transaction) -> TransactionORM:
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
