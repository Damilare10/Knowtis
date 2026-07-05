"""
Structured logging configuration.

Wires the standard-library ``logging`` package through ``structlog`` so that
every existing ``logging.getLogger(__name__)`` logger across routes, services,
the scheduler and Celery tasks emits structured (JSON) log records.

Request-scoped fields — ``request_id``, ``user_id``, ``route``, ``method`` —
are bound to a contextvar by the request-id middleware and merged into every
record (even those produced by plain stdlib loggers) via ``merge_contextvars``.
"""
import logging
import sys

import structlog


def setup_logging(level: str = "INFO", log_format: str = "json", debug: bool = False) -> None:
    """Configure structured logging for the whole process.

    Args:
        level: Root log level name (e.g. ``"INFO"``, ``"DEBUG"``).
        log_format: ``"json"`` for structured production logs, ``"console"``
            for pretty, human-readable output during local development.
        debug: Enables colored console output when ``log_format`` is
            ``"console"``. Does not affect the log level.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    use_json = log_format.lower() != "console"

    # Processors applied to both structlog and stdlib log records.
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    renderer = (
        structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(colors=debug)
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Route noisy third-party loggers through our formatter instead of their
    # own handlers so every line is structured uniformly.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", "slowapi"):
        third_party = logging.getLogger(name)
        third_party.handlers.clear()
        third_party.propagate = True
        third_party.setLevel(log_level)
