from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.logging.setup import get_logger

logger = get_logger(__name__)
_bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    def __init__(self, user_id: UUID, roles: list[str]) -> None:
        self.user_id = user_id
        self.roles = roles

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def can_access_account(self, account_owner_id: UUID) -> bool:
        return self.has_role("admin") or self.user_id == account_owner_id


def _is_development() -> bool:
    from src.infrastructure.config.settings import get_settings

    return get_settings().is_development


def _parse_dev_token(token: str) -> UUID | None:
    """
    Parses 'dev:<uuid>' tokens issued by POST /auth/dev-token.
    Returns None if the token is not in dev format.
    """
    if token.startswith("dev:"):
        try:
            return UUID(token[4:])
        except ValueError:
            return None
    return None


def _validate_jwt(token: str) -> dict:
    """
    Production JWT validation placeholder.

    Replace with:
        from jose import jwt, JWTError
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
        return {"sub": payload["sub"], "roles": payload.get("roles", ["user"])}
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="JWT validation not implemented. Use dev token in development.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> AuthenticatedUser:
    """
    Resolves the authenticated caller from the request.

    Development — three accepted methods (in priority order):
      1. X-Dev-User-Id: <uuid>        header (simplest for curl)
      2. Authorization: Bearer dev:<uuid>  (Swagger Authorize button)

    Production:
      Authorization: Bearer <jwt>

    HOW TO USE IN SWAGGER:
      1. POST /auth/dev-token → copy the token
      2. Click Authorize (top right in Swagger UI)
      3. Paste: Bearer dev:<uuid>
      4. Click Authorize — all requests now carry your identity
    """
    if _is_development():
        # Method 1: plain header — easiest for curl and Postman
        dev_user_id = request.headers.get("X-Dev-User-Id")
        if dev_user_id:
            try:
                uid = UUID(dev_user_id)
                logger.debug("dev_auth_header", user_id=str(uid))
                return AuthenticatedUser(user_id=uid, roles=["user"])
            except ValueError:
                raise HTTPException(400, "X-Dev-User-Id must be a valid UUID.")

        # Method 2: dev Bearer token from /auth/dev-token
        if credentials:
            uid = _parse_dev_token(credentials.credentials)
            if uid:
                logger.debug("dev_auth_bearer", user_id=str(uid))
                return AuthenticatedUser(user_id=uid, roles=["user"])

    # Production: validate real JWT
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _validate_jwt(credentials.credentials)
    return AuthenticatedUser(
        user_id=UUID(payload["sub"]),
        roles=payload.get("roles", ["user"]),
    )


async def require_admin(
    current_user: AuthenticatedUser = Security(get_current_user),
) -> AuthenticatedUser:
    if not current_user.has_role("admin"):
        raise HTTPException(status_code=403, detail="Admin role required.")
    return current_user
