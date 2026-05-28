from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import String, DateTime, func, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.outbound.persistence.models.shared import _utcnow
from src.infrastructure.database.engine import Base


class OutboxMessageORM(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    published: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"OutboxMessageORM("
            f"id={self.id}, "
            f"event_type={self.event_type}, "
            f"aggregate_id={self.aggregate_id}, "
            f"published={self.published})"
        )
