from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Awaitable

    from src.domain.events.base import DomainEvent


@runtime_checkable
class IEventBus(Protocol):
    """
    Event Bus Protocol.

    This is your PRIMARY event handling interface.
    """

    async def publish(self, event: DomainEvent) -> None:
        """
        Publish a single domain event.

        Args:
            event: The domain event to publish
        """
        ...

    async def publish_many(self, events: list[DomainEvent]) -> None:
        """
        Publish multiple events efficiently.

        Args:
            events: List of domain events to publish
        """
        ...

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: Event class to subscribe to
            handler: Async callable that handles the event
        """
        ...

    async def start(self) -> None:
        """
        Start the event bus (connect to infrastructure).

        - Connect to RabbitMQ
        - Initialize connection pools
        - Start consuming messages
        """
        ...

    async def stop(self) -> None:
        """
        Stop the event bus gracefully.

        - Close RabbitMQ connections
        - Flush pending events
        - Clean up resources
        """
        ...
