from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import String, Numeric, DateTime, Enum, func, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.outbound.persistence.models.shared import _utcnow
from src.domain.value_objects.enums import AccountStatus, Currency
from src.infrastructure.database.engine import Base

_VALID_CURRENCIES = ", ".join(f"'{c.value}'" for c in Currency)


class AccountORM(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    account_number: Mapped[str] = mapped_column(String(34), nullable=False, unique=True)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(precision=19, scale=4),
        nullable=False,
        default=Decimal("0.0000"),
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            *[s.value for s in AccountStatus],
            name="account_status",
            create_type=True,
        ),
        nullable=False,
        default=AccountStatus.ACTIVE.value,
    )
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

    __table_args__ = (
        Index("ix_accounts_owner_status", "owner_id", "status"),
        CheckConstraint(
            f"currency IN ({_VALID_CURRENCIES})",
            name="ck_accounts_currency_valid",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"AccountORM("
            f"id={self.id}, "
            f"balance={self.balance} {self.currency}, "
            f"status={self.status})"
        )
