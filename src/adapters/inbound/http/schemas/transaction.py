from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.value_objects.enums import Currency


class TransferRequest(BaseModel):
    """
    The client generates a UUID before sending. If the request times out,
    they retry with the SAME key — the server returns the original result
    without double-processing. This is the standard pattern for safe retries.

    WHY from_account_id is client-supplied (unlike owner_id on accounts):
    A user may have multiple accounts. They choose which account to debit.
    The service validates they own that account (ownership check via token).
    """

    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal = Field(gt=0, description="Transfer amount. Must be > 0.")
    currency: Currency = Field(
        description="Account currency. Supported: EUR, USD, GBP, IRR"
    )
    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
        description="Client-generated unique key. Use UUID4. Retry with same key safely.",
    )


class TransactionResponse(BaseModel):
    id: UUID
    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal
    currency: Currency
    status: str
    idempotency_key: str
    failure_code: str | None
    failure_reason: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"use_enum_values": True}

    @classmethod
    def from_dto(cls, dto: object) -> TransactionResponse:
        from src.application.dtos.transaction import TransactionDTO

        assert isinstance(dto, TransactionDTO)
        return cls(
            id=dto.id,
            from_account_id=dto.from_account_id,
            to_account_id=dto.to_account_id,
            amount=dto.amount,
            currency=Currency(dto.currency),
            status=dto.status,
            idempotency_key=dto.idempotency_key,
            failure_code=dto.failure_code,
            failure_reason=dto.failure_reason,
            created_at=dto.created_at,
            completed_at=dto.completed_at,
        )
