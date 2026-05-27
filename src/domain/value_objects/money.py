from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from src.domain.exceptions.account import InsufficientFundsError
from src.domain.exceptions.base import CurrencyMismatchError
from src.domain.value_objects.enums import Currency


@dataclass(frozen=True)
class Money:
    """
    WHY Money is a value object and not Decimal + str:

    1. Float arithmetic is wrong for banking.
       0.1 + 0.2 == 0.30000000000000004 in Python floats.
       Decimal gives exact arithmetic. One rounding rule defined
       once here (ROUND_HALF_UP), not scattered across services.

    2. Currency mismatch must be caught at the domain level.
       EUR 100 + USD 100 is not EUR 200. Without Money, every
       caller must remember to check currencies manually.
       Money enforces it structurally — you cannot add EUR to USD.

    3. Negative money is meaningless as a balance.
       Debits are expressed as subtracting a positive Money value.
       Money(amount=-50) is rejected at construction.
    """

    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            try:
                object.__setattr__(self, "amount", Decimal(str(self.amount)))
            except InvalidOperation as exc:
                raise ValueError(f"Invalid monetary amount: {self.amount!r}") from exc

        rounded = self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        object.__setattr__(self, "amount", rounded)

        if self.amount < Decimal("0"):
            raise ValueError(
                f"Money amount cannot be negative: {self.amount}. "
                f"Use a positive amount and call debit() on the account."
            )

    def __add__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        result_amount = (self.amount - other.amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if result_amount < Decimal("0"):
            raise InsufficientFundsError(available=self, requested=other)
        return Money(result_amount, self.currency)

    def __lt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount >= other.amount

    def is_zero(self) -> bool:
        return self.amount == Decimal("0")

    def _assert_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency)

    def __str__(self) -> str:
        return f"{self.currency.value} {self.amount:.2f}"

    def __repr__(self) -> str:
        return f"Money(amount={self.amount!r}, currency={self.currency!r})"
