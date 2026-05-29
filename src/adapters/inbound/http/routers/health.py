from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", status_code=200)
async def health() -> dict:
    """
    GET /health — liveness check.
    Returns 200 if the application is running.
    Used by load balancers and container orchestrators.
    """
    return {"status": "ok"}
