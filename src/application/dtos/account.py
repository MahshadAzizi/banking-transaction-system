from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID
from src.domain.entities.account import Account


@dataclass(frozen=True)
class CreateAccountCommand:
    """
    Carries intent from HTTP adapter → AccountService.

    WHY frozen dataclass and not Pydantic model:
    Pydantic belongs in the adapter layer (HTTP schemas).
    Commands are internal — pure Python, no framework dependency.
    frozen=True makes commands immutable: the service cannot
    accidentally modify the command while processing it.

    WHY owner_id is UUID and not OwnerId (NewType):
    Commands cross the adapter→application boundary. The adapter
    constructs the command from raw HTTP input where the ID is
    just a UUID. The service and aggregate cast to typed IDs
    internally. Keeping UUID here avoids the adapter needing to
    import domain-level NewTypes.
    """

    owner_id: UUID
    currency: str
    initial_balance: Decimal = Decimal("0")


@dataclass(frozen=True)
class AccountDTO:
    """
    Read-only snapshot of Account aggregate state.
    Crosses the application→adapter boundary safely.

    WHY DTO and not the Account aggregate directly:
    1. The adapter cannot call mutating methods (debit, freeze)
       on a DTO — it's a plain dataclass with no methods.
    2. DTOs decouple the HTTP response shape from the domain model.
       The domain can evolve internally without breaking the API contract.
    3. Serialisation logic (JSON, Pydantic) lives in the adapter,
       not in the aggregate.
    """

    id: UUID
    owner_id: UUID
    account_number: str
    balance: Decimal
    currency: str
    status: str

    @classmethod
    def from_aggregate(cls, account: object) -> AccountDTO:
        """
        Map Account aggregate → AccountDTO.
        application and domain layers.
        """
        assert isinstance(account, Account)
        return cls(
            id=account.id,
            owner_id=account.owner_id,
            account_number=account.account_number,
            balance=account.balance.amount,
            currency=account.balance.currency.value,
            status=account.status.value,
        )
