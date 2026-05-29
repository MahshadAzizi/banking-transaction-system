from __future__ import annotations

from uuid import UUID, uuid4
from typing import TypeVar
from datetime import datetime, timezone
from dataclasses import field, dataclass

from src.domain.events.base import DomainEvent


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


EntityType = TypeVar("EntityType", bound="Entity")


@dataclass
class Entity:
    id: UUID = field(default_factory=uuid4, init=False)

    created_at: datetime = field(
        default_factory=_now,
        init=False,
    )

    updated_at: datetime = field(default_factory=_now, init=False)

    def __eq__(self, other: Entity) -> bool:
        return isinstance(other, Entity) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id}>"


@dataclass
class AggregateRoot(Entity):
    """
    Extends Entity with domain event collection.

    WHY: An Aggregate is a cluster of domain objects treated as a single unit
    for data changes. The AggregateRoot is the only entry point — nothing
    outside the aggregate reaches inside to modify its state directly.

    Domain events are collected here (not published directly) so that:
    1. The aggregate stays pure — it knows nothing about Kafka or Redis.
    2. Events are only published AFTER the database transaction commits
       successfully. This is enforced by the Unit of Work, which calls
       collect_events() and flushes them to the outbox atomically.
    3. If the DB transaction rolls back, the events are discarded — no
       phantom events for operations that never actually happened.
    """

    _domain_events: list[DomainEvent] = field(
        default_factory=list, init=False, repr=False
    )

    def _record_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def collect_events(self) -> list[DomainEvent]:
        """
        Called by the Unit of Work after commit.
        Clears the internal list — events are emitted exactly once.
        """
        events, self._domain_events = self._domain_events, []
        return events

    def has_pending_events(self) -> bool:
        return len(self._domain_events) > 0
