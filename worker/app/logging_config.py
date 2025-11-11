"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any
import structlog
from app.config import settings


def configure_logging():
    """Configure structured logging for the application."""

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ])
    else:
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True),
        ])

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


# Configure logging on module import
configure_logging()

# Create logger instance
logger = structlog.get_logger()


def redact_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from log data.

    Args:
        data: Dictionary potentially containing sensitive data

    Returns:
        Dictionary with sensitive fields redacted
    """
    sensitive_keys = {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "api_key",
        "authorization",
    }

    redacted = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value

    return redacted
