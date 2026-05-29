from __future__ import annotations

from src.application.ports.outbound.event_bus import IEventBus
from src.domain.events.base import DomainEvent


class InMemoryEventBus(IEventBus):
    """
    In-memory event bus for unit tests.

    Collects all published events in a list.
    Tests can inspect self.published to assert
    the correct events were emitted in the correct order.
    """

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.published.append(event)

    async def publish_many(self, events: list[DomainEvent]) -> None:
        self.published.extend(events)
