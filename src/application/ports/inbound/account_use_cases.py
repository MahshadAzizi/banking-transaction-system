from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from src.application.dtos.account import AccountDTO, CreateAccountCommand


@runtime_checkable
class ICreateAccount(Protocol):
    """
    Inbound port — create a new bank account.

    WHY Protocol instead of ABC:
    Protocol enables structural subtyping (duck typing with type safety).
    Any class that implements execute() with the correct signature satisfies
    this port — no explicit inheritance required. This makes testing easier:
    a plain function wrapped in a class satisfies the Protocol without
    needing to import and subclass an ABC.

    WHY this port exists at all (not just calling AccountService directly):
    The HTTP router depends on ICreateAccount, not on AccountService.
    This means:
    1. The router can be tested with any mock that satisfies the Protocol.
    2. AccountService can be swapped (e.g. for a read-only variant in admin)
       without touching the router.
    3. The dependency flows inward: adapter → port ← service.
       The service is never imported by the adapter directly.
    """

    async def execute(self, command: CreateAccountCommand) -> AccountDTO: ...


@runtime_checkable
class IGetAccount(Protocol):
    """
    Inbound port — retrieve account details by ID.

    WHY returns AccountDTO and not Account aggregate:
    The HTTP adapter must never receive a domain aggregate directly.
    If it did, it could call aggregate methods (debit, freeze) from
    outside the application layer — bypassing the service entirely.
    DTO is a read-only snapshot: safe to pass across layer boundaries.
    """

    async def execute(self, account_id: UUID) -> AccountDTO: ...
