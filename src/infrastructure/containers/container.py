from __future__ import annotations

from dependency_injector import containers, providers

from src.adapters.outbound.locking.redis_lock_manager import RedisLockManager
from src.adapters.outbound.messaging.in_memory_event_bus import InMemoryEventBus
from src.adapters.outbound.persistence.sqlalchemy_unit_of_work import (
    SQLAlchemyUnitOfWork,
)
from src.application.services.account import AccountService
from src.application.services.transfer import TransferService
from src.infrastructure.cache.redis import build_redis_client
from src.infrastructure.config.settings import Settings
from src.infrastructure.database.engine import build_engine, build_session_factory


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    settings = providers.Singleton(Settings)

    db_engine = providers.Singleton(build_engine)

    session_factory = providers.Singleton(
        build_session_factory,
        engine=db_engine,
    )

    redis_client = providers.Resource(
        build_redis_client,
        url=providers.Callable(lambda s: s.redis.url, settings),
    )

    lock_manager = providers.Singleton(
        RedisLockManager,
        redis=redis_client,
    )

    event_bus = providers.Singleton(
        InMemoryEventBus,
    )

    uow = providers.Factory(
        SQLAlchemyUnitOfWork,
        session_factory=session_factory,
    )

    account_service = providers.Factory(
        AccountService,
        uow=uow,
    )

    transfer_service = providers.Factory(
        TransferService,
        uow=uow,
        lock_manager=lock_manager,
        event_bus=event_bus,
    )


container = Container()
