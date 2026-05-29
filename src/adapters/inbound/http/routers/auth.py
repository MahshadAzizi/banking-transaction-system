from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth (dev only)"])


class DevTokenRequest(BaseModel):
    """
    Request a dev token for a specific user.
    user_id defaults to a new UUID if not provided —
    useful for quickly getting a fresh identity in Swagger.
    """

    user_id: UUID | None = None


class DevTokenResponse(BaseModel):
    token: str
    user_id: UUID
    instructions: str


@router.post(
    "/dev-token",
    response_model=DevTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a dev token (development only)",
    description=(
        "Returns a dev token to use in the Authorize dialog in Swagger UI. "
        "This endpoint is DISABLED in production. "
        "Copy the token value and paste it into the Authorize button at the "
        "top of this page as: `Bearer <token>`"
    ),
)
async def get_dev_token(body: DevTokenRequest = DevTokenRequest()) -> DevTokenResponse:
    """
    WHY this endpoint exists:
    Without a real identity provider, Swagger and Postman have no way
    to get a token. This endpoint bridges that gap for development and
    evaluator testing. It is disabled in production via the startup check.

    HOW to use in Swagger:
        1. POST /auth/dev-token  (optionally pass a user_id)
        2. Copy the token value from the response
        3. Click the "Authorize" button at the top of Swagger UI
        4. Enter: Bearer <token>
        5. All subsequent requests will be authenticated as that user

    HOW to use in Postman:
        1. POST /auth/dev-token
        2. Set the response token as a collection variable
        3. Use {{token}} in Authorization header of other requests

    SECURITY: This endpoint ONLY works when ENV=development.
    It raises 403 in production. It does not accept passwords or
    validate anything — it simply wraps a user_id as a dev token.
    """
    from src.infrastructure.config.settings import get_settings

    if get_settings().is_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev token endpoint is disabled in production.",
        )

    user_id = body.user_id or uuid4()
    # The token IS the user_id — the auth middleware reads X-Dev-User-Id
    # or parses this token format in development mode
    token = f"dev:{user_id}"

    return DevTokenResponse(
        token=token,
        user_id=user_id,
        instructions=(
            f"Add this header to every request: "
            f"X-Dev-User-Id: {user_id}  "
            f"OR use Bearer token in Authorization header."
        ),
    )
