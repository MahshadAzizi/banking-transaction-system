import logging
import sys
from typing import Literal

import structlog


def configure_logging(
    level: str = "INFO",
    fmt: Literal["json", "console"] = "console",
) -> None:
    """
    Call once at application startup.
    After this, every module uses:  logger = structlog.get_logger(__name__)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)


    shared_processors: list = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if fmt == "json":

        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:

        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if level == "DEBUG" else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
