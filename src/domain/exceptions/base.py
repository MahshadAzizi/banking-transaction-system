from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.value_objects.enums import Currency


class DomainException(Exception):
    """
    Root of all domain exceptions.
    The HTTP adapter catches this and maps subclasses to status codes.
    The domain never imports FastAPI — it only raises DomainException subtypes.
    """


class ResourceNotFoundError(DomainException):
    def __init__(self, resource: str, id: object) -> None:
        super().__init__(f"{resource} with id '{id}' not found.")
        self.resource = resource
        self.id = id


class CurrencyMismatchError(DomainException):
    def __init__(self, left: Currency, right: Currency) -> None:
        super().__init__(f"Cannot operate on different currencies: {left} vs {right}.")


class ConcurrencyConflictError(DomainException):
    """
    Maps to HTTP 409 — signals the client to retry.
    A generic 500 would make the client think it should NOT retry.
    """

    def __init__(self, resource: str) -> None:
        super().__init__(
            f"Concurrent operation in progress on '{resource}'. Please retry."
        )


class BusinessRuleViolationError(DomainException):
    """Catch-all for domain invariant violations without a specific subclass."""
