from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.adapters.inbound.http.exception_handlers import register_exception_handlers
from src.adapters.inbound.http.middleware.request_id import RequestIdMiddleware
from src.adapters.inbound.http.routers import accounts, health, transactions, auth

from src.infrastructure.config.settings import get_settings
from src.infrastructure.containers.container import container
from src.infrastructure.logging.setup import setup_logging
from src.infrastructure.logging.setup import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _wire_container() -> None:
    """
    Central DI wiring — must run BEFORE app starts serving requests.
    """
    container.config.from_dict(settings.model_dump())

    container.wire(
        modules=[
            "src.adapters.inbound.http.routers.accounts",
            "src.adapters.inbound.http.routers.transactions",
            "src.adapters.inbound.http.routers.auth",
        ]
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. logging first
    setup_logging(
        log_level=settings.observability.log_level,
        json_logs=settings.observability.log_format == "json",
    )

    _wire_container()

    logger.info("application_started", version="0.1.0")

    yield

    logger.info("application_shutting_down")

    result = container.shutdown_resources()
    if asyncio.iscoroutine(result):
        await result


def create_app() -> FastAPI:
    app = FastAPI(
        title="Banking Transaction System",
        description="DDD + Hexagonal Architecture",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(accounts.router)
    app.include_router(transactions.router)
    register_exception_handlers(app)
    return app


app = create_app()
