from __future__ import annotations

from enum import Enum


class Currency(Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    IRR = "IRR"

    def __str__(self) -> str:
        return self.value


class AccountStatus(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"

    def can_transact(self) -> bool:
        return self == AccountStatus.ACTIVE

    def can_close(self) -> bool:
        return self in (AccountStatus.ACTIVE, AccountStatus.FROZEN)

    def is_terminal(self) -> bool:
        return self == AccountStatus.CLOSED


class KycStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    REJECTED = "rejected"

    def can_open_account(self) -> bool:
        return self == KycStatus.VERIFIED

    def is_terminal(self) -> bool:
        return self == KycStatus.REJECTED


class TransactionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        return self in (TransactionStatus.COMPLETED, TransactionStatus.FAILED)

    def can_process(self) -> bool:
        return self == TransactionStatus.PENDING

    def can_complete(self) -> bool:
        return self == TransactionStatus.PROCESSING

    def can_fail(self) -> bool:
        return self in (TransactionStatus.PENDING, TransactionStatus.PROCESSING)


class TransactionType(Enum):
    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
