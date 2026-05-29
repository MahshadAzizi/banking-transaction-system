from __future__ import annotations

import json
import uuid
from typing import Any
from datetime import UTC, datetime
from dataclasses import field, asdict, dataclass


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """
    Base class for all domain events.

    Domain events represent significant business occurrences that domain experts
    care about. They are immutable value objects that capture what happened in
    the domain at a specific point in time.

    Attributes:
        event_id: Unique identifier for this event instance (UUID v4)
        occurred_at: Timestamp when the event occurred (UTC)
        metadata: Additional technical metadata (not business data)
    """

    event_id: uuid.UUID = field(
        default_factory=uuid.uuid4,
        kw_only=True,
        compare=False,
    )

    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        kw_only=True,
        compare=False,
    )

    metadata: dict[str, Any] = field(
        default_factory=dict,
        kw_only=True,
        compare=False,
    )

    @property
    def event_type(self) -> str:
        return self.__class__.__name__

    def to_dict(self) -> dict:
        data = asdict(self)
        data["event_type"] = self.event_type
        for k, v in data.items():
            if isinstance(v, uuid.UUID):
                data[k] = str(v)
            elif isinstance(v, datetime):
                data[k] = v.isoformat()

        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(event_id={self.event_id!r}, occurred_at={self.occurred_at.isoformat()!r})"
