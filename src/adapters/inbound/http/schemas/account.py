from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from src.domain.value_objects.enums import Currency


class CreateAccountRequest(BaseModel):
    currency: Currency = Field(
        description="Account currency. Supported: EUR, USD, GBP, IRR"
    )
    initial_balance: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Opening balance. Defaults to zero.",
    )


class AccountResponse(BaseModel):
    id: UUID
    owner_id: UUID
    account_number: str
    balance: Decimal
    currency: Currency
    status: str

    model_config = {"from_attributes": True, "use_enum_values": True}

    @classmethod
    def from_dto(cls, dto: object) -> "AccountResponse":
        from src.application.dtos.account import AccountDTO

        assert isinstance(dto, AccountDTO)
        return cls(
            id=dto.id,
            owner_id=dto.owner_id,
            account_number=dto.account_number,
            balance=dto.balance,
            currency=Currency(dto.currency),
            status=dto.status,
        )
