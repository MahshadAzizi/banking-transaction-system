from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.exceptions.base import DomainException

if TYPE_CHECKING:
    from src.domain.value_objects.identifiers import AccountId
    from src.domain.value_objects.money import Money


class InsufficientFundsError(DomainException):
    """
    WHY raised inside Money.__sub__ rather than in the service:
    The rule 'you cannot spend more than you have' belongs to the domain.
    Raising it inside Money subtraction makes it impossible to bypass —
    any code path that subtracts money gets this check for free.
    """

    def __init__(self, available: Money, requested: Money) -> None:
        super().__init__(
            f"Insufficient funds: requested {requested}, "
            f"but only {available} available."
        )
        self.available = available
        self.requested = requested


class AccountFrozenError(DomainException):
    def __init__(self, account_id: AccountId) -> None:
        super().__init__(
            f"Account '{account_id}' is frozen. "
            f"No transactions permitted until unfrozen."
        )
        self.account_id = account_id


class AccountClosedError(DomainException):
    def __init__(self, account_id: AccountId) -> None:
        super().__init__(
            f"Account '{account_id}' is permanently closed."
        )
        self.account_id = account_id

class AccountNotEmptyError(DomainException):
    def __init__(self, account_id: AccountId, balance: Money) -> None:
        super().__init__(
            f"Cannot close account '{account_id}': "
            f"balance must be zero, current balance is {balance}."
        )
        self.account_id = account_id
        self.balance = balance