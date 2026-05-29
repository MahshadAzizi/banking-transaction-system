from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.adapters.inbound.http.middleware.auth import (
    AuthenticatedUser,
    get_current_user,
)
from src.adapters.inbound.http.schemas.account import (
    AccountResponse,
    CreateAccountRequest,
)
from src.application.dtos.account import CreateAccountCommand
from src.application.ports.inbound.account_service import IAccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


def get_account_service() -> IAccountService:
    from src.infrastructure.containers.container import container

    return container.account_service()


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: CreateAccountRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: IAccountService = Depends(get_account_service),
) -> AccountResponse:
    """
    POST /accounts — open a new bank account.

    owner_id is derived from the authenticated token — never from request body.
    The domain generates the account ID and account number internally.

    Dev usage:
        curl -X POST /accounts \\
          -H "X-Dev-User-Id: <your-uuid>" \\
          -d '{"currency": "EUR"}'
    """
    cmd = CreateAccountCommand(
        owner_id=current_user.user_id,
        currency=body.currency.value,
        initial_balance=body.initial_balance,
    )
    return AccountResponse.from_dto(await service.create(cmd))


@router.get(
    "/{account_id}", response_model=AccountResponse, status_code=status.HTTP_200_OK
)
async def get_account(
    account_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    service: IAccountService = Depends(get_account_service),
) -> AccountResponse:
    """
    GET /accounts/{id}

    Ownership enforced: users can only retrieve their own accounts.
    Admin role bypasses this restriction.
    """
    dto = await service.get(account_id)
    if not current_user.can_access_account(dto.owner_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this account.",
        )

    return AccountResponse.from_dto(dto)
