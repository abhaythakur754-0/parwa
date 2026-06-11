"""Structured JSON logging for PARWA.

Configures the Python logging system to emit structured JSON logs
suitable for production log aggregation systems (ELK, CloudWatch,
Datadog, etc.).

Each log entry includes:
- timestamp (ISO 8601)
- level
- logger name
- message
- any extra fields passed via logger.info("msg", extra={...})

Usage:
    from parwa.utils.json_logging import configure_json_logging

    configure_json_logging()  # Call once at startup

    # Then use standard logging — output is automatically JSON
    logger = logging.getLogger("parwa.graph")
    logger.info("ticket processed", extra={"ticket_id": "TKT-123", "variant": "parwa"})
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Log formatter that outputs structured JSON.

    Each log record is formatted as a single-line JSON object with
    standard fields plus any extra fields from the log record.
    """

    # Fields that come from the standard LogRecord — don't duplicate
    _STANDARD_FIELDS = frozenset({
        "name", "msg", "args", "created", "relativeCreated",
        "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "pathname", "filename", "module", "thread", "threadName",
        "process", "processName", "levelname", "levelno", "message",
        "msecs", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        # Base fields
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add location info
        log_entry["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add any extra fields that aren't standard
        for key, value in record.__dict__.items():
            if key not in self._STANDARD_FIELDS and not key.startswith("_"):
                try:
                    # Test if value is JSON-serializable
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError, OverflowError):
                    log_entry[key] = str(value)

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add stack info if present
        if record.stack_info:
            log_entry["stack_trace"] = self.formatStack(record.stack_info)

        # Add PARWA-specific context
        log_entry["service"] = "parwa"
        log_entry["version"] = "0.1.0"

        try:
            return json.dumps(log_entry, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            # Fallback to simple format if JSON serialization fails
            return f"{log_entry['timestamp']} {log_entry['level']} {log_entry['logger']} {log_entry['message']}"


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for development.

    Includes color codes and structured layout for terminal readability.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        # Format timestamp
        ts = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).strftime("%H:%M:%S")

        # Build base message
        msg = f"{color}{ts} {record.levelname:8s}{reset} [{record.name}] {record.getMessage()}"

        # Add extra fields inline if present
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in JSONFormatter._STANDARD_FIELDS and not k.startswith("_")
        }
        if extras:
            extra_str = " ".join(f"{k}={v}" for k, v in extras.items())
            msg += f" {color}|{reset} {extra_str}"

        # Add exception
        if record.exc_info and record.exc_info[0] is not None:
            msg += "\n" + self.formatException(record.exc_info)

        return msg


def configure_json_logging(
    level: int = logging.INFO,
    json_mode: bool | None = None,
) -> None:
    """Configure PARWA logging with structured output.

    Args:
        level: Logging level (default INFO).
        json_mode: Force JSON output (True) or human-readable (False).
            None = auto-detect based on PARWA_LOG_FORMAT env var,
            defaulting to human-readable for development.
    """
    import os

    if json_mode is None:
        json_mode = os.getenv("PARWA_LOG_FORMAT", "human").lower() == "json"

    # Select formatter
    formatter = JSONFormatter() if json_mode else HumanFormatter()

    # Configure root handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Remove existing handlers to avoid duplicate output
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Set PARWA logger levels
    logging.getLogger("parwa").setLevel(level)

    # Quiet down noisy libraries
    for noisy in ("httpx", "httpcore", "openai", "langchain", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    mode_str = "JSON" if json_mode else "human-readable"
    logging.getLogger("parwa").info(
        "logging configured: level=%s format=%s",
        logging.getLevelName(level), mode_str,
    )
