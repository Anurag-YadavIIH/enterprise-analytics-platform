"""Structured logging via ``structlog``.

Call :func:`configure_logging` once at process start (CLI entrypoints, API
startup). Everywhere else, use :func:`get_logger` to obtain a bound logger.
Console output in dev, JSON in production/CI when ``EAP_LOG_JSON=true``.
"""

from __future__ import annotations

import logging
import sys

import structlog

from eap.config import get_settings

_CONFIGURED = False


def configure_logging(level: str | None = None, json_logs: bool | None = None) -> None:
    """Configure structlog + stdlib logging. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    resolved_level = (level or settings.log_level).upper()
    resolved_json = settings.log_json if json_logs is None else json_logs

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, resolved_level, logging.INFO),
    )

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if resolved_json
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, resolved_level, logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, configuring on first use."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)  # type: ignore[return-value]
