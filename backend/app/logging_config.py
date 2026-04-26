"""
Logging configuration with structlog + stdlib integration.

Produces structured JSON logs to stdout.
"""

import sys
import logging
import logging.config
import structlog


def configure_logging() -> None:
    """Configure structlog + stdlib logging for JSON output."""
    
    # Shared processors for both structlog and stdlib logging
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.filter_by_level,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.JSONRenderer(),
                ],
                "foreign_pre_chain": shared_processors,
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": sys.stdout,
            },
        },
        "loggers": {
            # Suppress noisy libraries
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.access": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "httpx": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            "httpcore": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            "sqlalchemy.engine": {"handlers": ["default"], "level": "WARNING", "propagate": False},
        },
        "root": {
            "handlers": ["default"],
            "level": "INFO",
        },
    })


# Auto-configure on import
configure_logging()


# Convenience function to get a logger
def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_registered", user_id=123, email="test@example.com")
    """
    return structlog.get_logger(name)
