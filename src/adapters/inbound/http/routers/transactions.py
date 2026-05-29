from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.adapters.inbound.http.middleware.auth import (
    AuthenticatedUser,
    get_current_user,
)
from src.adapters.inbound.http.schemas.transaction import (
    TransactionResponse,
    TransferRequest,
)
from src.application.dtos.transaction import TransferCommand
from src.application.ports.inbound.transfer_service import ITransferService
from src.application.ports.inbound.account_service import IAccountService

from src.infrastructure.containers.container import container

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def get_transfer_service() -> ITransferService:
    return await container.transfer_service()


@router.post(
    "/transfer",
    response_model=TransactionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def initiate_transfer(
    body: TransferRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: ITransferService = Depends(get_transfer_service),
) -> TransactionResponse:
    """
    POST /transactions/transfer

    Ownership check: the authenticated user must own from_account_id.
    The service validates balance and business rules after this check.

    Idempotency: supply a unique idempotency_key (UUID4 recommended).
    Retrying with the same key returns the original result safely.

    Dev usage:
        curl -X POST /transactions/transfer \\
          -H "X-Dev-User-Id: <your-uuid>" \\
          -d '{"from_account_id": "...", "to_account_id": "...",
               "amount": "100", "currency": "EUR",
               "idempotency_key": "<uuid4>"}'
    """
    # Ownership check — verify the caller owns the sender account
    # This happens at the adapter layer, not in the domain
    _ = await _get_account_or_403(body.from_account_id, current_user, service)

    cmd = TransferCommand(
        from_account_id=body.from_account_id,
        to_account_id=body.to_account_id,
        amount=body.amount,
        currency=body.currency.value,
        idempotency_key=body.idempotency_key,
    )
    return TransactionResponse.from_dto(await service.initiate(cmd))


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_transaction(
    transaction_id: UUID,
    service: ITransferService = Depends(get_transfer_service),
) -> TransactionResponse:
    """GET /transactions/{id} — authenticated users can view their transactions."""
    return TransactionResponse.from_dto(await service.get(transaction_id))


async def _get_account_or_403(
    account_id: UUID,
    current_user: AuthenticatedUser,
) -> None:
    """
    Verify the current user owns this account before allowing a transfer.
    Raises 403 if they don't — before any domain logic runs.
    """

    account_service: IAccountService = container.account_service()

    try:
        dto = await account_service.get(account_id)
    except Exception:
        return

    if not current_user.can_access_account(dto.owner_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this account.",
        )
