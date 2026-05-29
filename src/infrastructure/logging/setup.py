from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(log_level: str = "INFO", json_logs: bool = True) -> None:
    """
    Configure structlog for structured, context-aware logging.

    WHY structlog over standard logging:
    Standard logging produces unstructured text — hard to search, filter,
    and aggregate in production. structlog produces JSON with bound context
    fields (request_id, account_id) attached to every log line automatically.

    A failed transfer at 3am produces logs like:
        {"event": "debit_failed", "request_id": "abc-123",
         "account_id": "xyz", "amount": "500.00", "level": "warning"}

    That JSON feeds directly into DataDog/Elasticsearch for instant filtering.
    Unstructured text requires regex parsing — fragile and slow.

    WHY request_id binding matters:
    The RequestIdMiddleware calls structlog.contextvars.bind_contextvars(request_id=...)
    at the start of each request. Every log line emitted anywhere in that request —
    service, repository, domain — automatically carries the same request_id.
    No need to thread it through every function signature.
    """
    shared_processors: list = [
        # Bind request_id and other context vars to every log line
        structlog.contextvars.merge_contextvars,
        # Add log level as a string field
        structlog.stdlib.add_log_level,
        # Add logger name (module path)
        structlog.stdlib.add_logger_name,
        # ISO8601 timestamp
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Format exceptions as a structured field, not a raw traceback string
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        # Production: machine-readable JSON for log aggregation
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: human-readable coloured console output
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Silence noisy third-party loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger bound to a module name.

    Usage:
        logger = get_logger(__name__)
        logger.info("transfer_initiated", amount="100.00", currency="EUR")
        logger.warning("lock_contention", account_id=str(account_id))
        logger.error("db_commit_failed", exc_info=True)
    """
    return structlog.get_logger(name)
