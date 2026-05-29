from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    String,
    Numeric,
    DateTime,
    Enum,
    func,
    Text,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.outbound.persistence.models.shared import _utcnow
from src.domain.value_objects.enums import TransactionType, TransactionStatus, Currency
from src.infrastructure.database.engine import Base

_VALID_CURRENCIES = ", ".join(f"'{c.value}'" for c in Currency)


class TransactionORM(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    from_account_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    to_account_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(
        Enum(
            *[t.value for t in TransactionType],
            name="transaction_type",
            create_type=True,
        ),
        nullable=False,
        default=TransactionType.TRANSFER.value,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            *[s.value for s in TransactionStatus],
            name="transaction_status",
            create_type=True,
        ),
        nullable=False,
        default=TransactionStatus.PENDING.value,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        Index("ix_transactions_from_status", "from_account_id", "status"),
        Index("ix_transactions_from_created", "from_account_id", "created_at"),
        CheckConstraint(
            f"currency IN ({_VALID_CURRENCIES})",
            name="ck_transactions_currency_valid",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"TransactionORM(id={self.id}, "
            f"{self.from_account_id}→{self.to_account_id}, "
            f"{self.amount} {self.currency}, status={self.status})"
        )
