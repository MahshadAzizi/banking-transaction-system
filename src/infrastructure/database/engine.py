from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.infrastructure.config.settings import get_settings


class Base(DeclarativeBase):
    """
    SQLAlchemy declarative base.
    All ORM models inherit from this.
    Kept here so alembic env.py has one import point.
    """
    pass


def build_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database.url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_pre_ping=True,
        echo=settings.debug,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for per-request DB sessions.
    Used directly in routers OR injected via container.

    Usage in router (without DI container):
        async def endpoint(session: AsyncSession = Depends(get_db_session)):
            ...

    The container wires this automatically — routers don't call it directly.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()