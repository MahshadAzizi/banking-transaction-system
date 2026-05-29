from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.domain.exceptions.account import (
    AccountClosedError,
    AccountFrozenError,
    AccountNotEmptyError,
    InsufficientFundsError,
)
from src.domain.exceptions.base import (
    ConcurrencyConflictError,
    CurrencyMismatchError,
    DomainException,
    ResourceNotFoundError,
)
from src.domain.exceptions.transaction import (
    DuplicateIdempotencyKeyError,
    InvalidTransferAmountError,
    SameAccountTransferError,
    TransactionAlreadyCompletedError,
    TransactionAlreadyProcessingError,
    TransactionNotFailableError,
)

# Explicit mapping — every domain exception gets a deliberate status code.
# DomainException base catches anything not listed here → 500.
_STATUS_MAP: dict[type[DomainException], int] = {
    # 400 — bad request (client sent invalid data)
    InvalidTransferAmountError: 400,
    SameAccountTransferError: 400,
    CurrencyMismatchError: 400,
    # 404 — resource not found
    ResourceNotFoundError: 404,
    # 409 — conflict (client should retry)
    # WHY 409 for concurrency and not 503:
    # 503 means the server is unavailable. 409 means "conflict with
    # current state — retry and you will likely succeed". This is the
    # correct signal for a distributed lock timeout.
    ConcurrencyConflictError: 409,
    TransactionAlreadyProcessingError: 409,
    DuplicateIdempotencyKeyError: 409,
    # 422 — business rule violation (request was valid but domain rejected it)
    InsufficientFundsError: 422,
    AccountFrozenError: 422,
    AccountClosedError: 422,
    AccountNotEmptyError: 422,
    TransactionAlreadyCompletedError: 422,
    TransactionNotFailableError: 422,
}


def _error_response(exc: Exception, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": type(exc).__name__,
            "detail": str(exc),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all domain exception handlers on the FastAPI app.
    Called once at startup in main.py.

    WHY register here and not use @app.exception_handler decorators:
    This function is called with the app instance — no circular imports.
    All handlers live in one file — easy to audit which exceptions
    map to which status codes.
    """

    @app.exception_handler(DomainException)
    async def domain_exception_handler(
        request: Request, exc: DomainException
    ) -> JSONResponse:
        status_code = _STATUS_MAP.get(type(exc), 500)
        return _error_response(exc, status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return _error_response(exc, 500)
