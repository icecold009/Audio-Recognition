"""Production Gunicorn settings for the Flask application."""

from __future__ import annotations

import os


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


bind = f"0.0.0.0:{_bounded_int('PORT', 5000, 1, 65535)}"
workers = _bounded_int("GUNICORN_WORKERS", 2, 1, 8)
timeout = _bounded_int("GUNICORN_TIMEOUT_SECONDS", 45, 10, 120)
graceful_timeout = min(timeout, 15)
keepalive = 5
accesslog = "-"
errorlog = "-"
capture_output = True
