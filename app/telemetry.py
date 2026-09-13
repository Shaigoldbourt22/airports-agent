"""Structured JSON logging to stdout.

Azure Container Apps forwards stdout to Log Analytics, so emitting one JSON
object per event makes every field queryable in KQL without any agent or SDK.
"""

import json
import logging
import os
import sys
import time
from contextlib import contextmanager

_LOGGER = logging.getLogger("airports")


def configure() -> None:
    if _LOGGER.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    _LOGGER.propagate = False


def event(name: str, level: int = logging.INFO, **fields) -> None:
    """Emit one JSON line. Never include message text or attachment contents."""
    payload = {"event": name, **{k: v for k, v in fields.items() if v is not None}}
    _LOGGER.log(level, json.dumps(payload, default=str))


@contextmanager
def timed(name: str, **fields):
    """Log an event with duration and outcome, whether it succeeds or raises."""
    start = time.perf_counter()
    try:
        yield fields
    except Exception as exc:
        event(
            name,
            level=logging.ERROR,
            outcome="error",
            error_type=type(exc).__name__,
            error=str(exc)[:300],
            ms=round((time.perf_counter() - start) * 1000),
            **fields,
        )
        raise
    event(
        name,
        outcome="ok",
        ms=round((time.perf_counter() - start) * 1000),
        **fields,
    )
