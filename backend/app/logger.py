"""
PARWA Structured Logger (BC-012)

Uses structlog for JSON-formatted structured logging.
- Production: JSON output for log aggregation
- Test/Dev: console output for readability
- Every log entry includes: timestamp, level, environment, module
"""

import logging
import os
import sys
from typing import Any

import structlog


def _add_env_info(logger, method_name, event_dict):
    """Add environment info to log events.

    Replaces structlog.processors.add_env_info.
    """
    event_dict["environment"] = os.getenv("ENVIRONMENT", "unknown")
    return event_dict


def configure_logging(environment: str = "development") -> None:
    """Configure structlog based on environment."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            _add_env_info,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    level = logging.DEBUG if environment != "production" else logging.INFO
    root_logger.setLevel(level)


def get_logger(name: str) -> Any:
    """Get a bound structlog logger with module name."""
    return structlog.get_logger(name)
