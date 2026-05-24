from dependency_injector import containers, providers
from src.infrastructure.config.settings import get_settings
from src.infrastructure.database.engine import build_engine, build_session_factory


class Container(containers.DeclarativeContainer):
    settings = providers.Singleton(get_settings)
    db_engine = providers.Singleton(
        build_engine,
    )

    session_factory = providers.Singleton(
        build_session_factory,
        engine=db_engine,
    )
