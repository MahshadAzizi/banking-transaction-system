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


class CurrencyMismatchError(DomainException):
    def __init__(self, left: Currency, right: Currency) -> None:
        super().__init__(f"Cannot operate on different currencies: {left} vs {right}.")
