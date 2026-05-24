from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.infrastructure.config.settings import get_settings
from src.infrastructure.containers.container import Container
from src.infrastructure.logging.setup import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(
        level=settings.observability.log_level,
        fmt=settings.observability.log_format,
    )
    logger = structlog.get_logger(__name__)

    logger.info(
        "application_starting",
        env=settings.app_env,
        version=settings.app_version,
    )

    container: Container = app.state.container
    yield


def _wire_container(app: FastAPI) -> None:
    container = Container()

    app.state.container = container


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Banking Transaction Processing System\n\n"
            "Architecture: Domain-Driven Design + Hexagonal (Ports & Adapters)\n"
            "Stack: FastAPI · PostgreSQL"
        ),

        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )
    _wire_container(app)

    return app


app = create_app()
