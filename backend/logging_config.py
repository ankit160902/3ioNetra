"""Single source of truth for the backend's logging configuration.

Why this exists
---------------
`logging.basicConfig` is a no-op when the root logger already has handlers
(which is the case under uvicorn, since uvicorn configures its own handlers
before importing the application module). It also attaches its formatter to a
*new* StreamHandler — meaning any logger-level filter on the root logger is
NOT consulted for records that propagate up from child loggers like
`uvicorn.error`, `httpx`, or `google.genai`. That's the bug class that caused
hundreds of `KeyError: 'correlation_id'` tracebacks per request.

The durable fix is `logging.config.dictConfig`:
- declares the CorrelationFilter once
- attaches it to every handler (so propagated records from any child logger
  always pass through the filter before reaching the formatter)
- applies the same handler to uvicorn's loggers
- replaces uvicorn's default handlers, which would otherwise produce a
  parallel stream of logs without correlation IDs

This module exposes a single `LOGGING_CONFIG` dict and a small `configure()`
helper. Call `configure()` once at startup. Do not call `basicConfig()` from
anywhere in the application — every formatter that requires `correlation_id`
will crash on records that bypass the filter chain.
"""

from __future__ import annotations

from typing import Any, Dict

from config import settings

# Format string used by every handler. Using `[%(correlation_id)s]` lets us
# trace a single request across multiple log lines from different services
# without parsing structured fields. The CorrelationFilter guarantees the
# attribute is always present (default sentinel: "-").
LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] %(message)s"
)


def build_logging_config(level: str | None = None) -> Dict[str, Any]:
    """Build the dictConfig payload.

    Parameters
    ----------
    level: str | None
        Log level for the root and uvicorn loggers. Defaults to settings.LOG_LEVEL.

    Returns
    -------
    dict
        A dictConfig-compatible structure that:
        1. Declares the CorrelationFilter under the name `correlation_id`
        2. Declares one formatter (`default`) using LOG_FORMAT
        3. Declares one handler (`console`) attaching the filter and formatter
        4. Wires the handler to the root logger AND uvicorn's three loggers
           (uvicorn, uvicorn.error, uvicorn.access) with `propagate: False`
           so uvicorn doesn't double-log via its own default handler.
    """
    log_level = level or settings.LOG_LEVEL

    return {
        "version": 1,
        # IMPORTANT: keep existing loggers (created at import time before
        # configure() runs) — disabling them would silence everything that
        # was logged during module import.
        "disable_existing_loggers": False,
        "filters": {
            "correlation_id": {
                "()": "services.observability.CorrelationFilter",
            },
        },
        "formatters": {
            "default": {
                "format": LOG_FORMAT,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "filters": ["correlation_id"],
                "formatter": "default",
            },
        },
        "loggers": {
            # Root logger — catches everything from application code and any
            # third-party library that doesn't have its own logger config.
            "": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            # Uvicorn's three loggers. Without these entries uvicorn keeps
            # its own handler with its own formatter, producing duplicate
            # output. We override them so all server logs go through our
            # correlation-aware handler.
            "uvicorn": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                # access logs default to INFO regardless of LOG_LEVEL — they
                # are noisy but expected. Operators can lower via env if
                # needed (LOG_LEVEL=WARNING silences both error and access).
                "level": log_level,
                "propagate": False,
            },
        },
    }


# Module-level constant for callers that prefer importing the dict directly
# (e.g., uvicorn's --log-config flag, or tests that want to inspect the shape).
LOGGING_CONFIG: Dict[str, Any] = build_logging_config()


def configure(level: str | None = None) -> None:
    """Apply LOGGING_CONFIG to the global logging system.

    Idempotent: calling this multiple times is safe — dictConfig replaces the
    handler list rather than appending. Call this exactly once at process
    startup, before the first log line that needs correlation_id.
    """
    from logging.config import dictConfig

    dictConfig(build_logging_config(level=level))
