"""
JSONFormatter – Structured JSON log formatter for GateKeeper.

Produces one JSON object per log record, compatible with ELK / Loki /
any log-aggregation stack that consumes newline-delimited JSON (NDJSON).

Usage::

    import logging
    from json_logger import JSONFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.getLogger().addHandler(handler)

Each log line is a JSON object with at minimum::

    {
        "timestamp": "2026-03-10T02:48:30.123456+00:00",
        "level": "INFO",
        "logger": "venv_manager",
        "message": "✅ [rembg] Venv ready",
        "module": "venv_manager"
    }

Additional structured fields are added when present in ``record.extra``
(i.e. passed via ``logger.info(..., extra={...})``).  Commonly used keys:

- ``worker``   – worker name
- ``action``   – lifecycle action (created | reused | verified | rebuilt)
- ``duration_sec`` – elapsed seconds
- ``size_mb``  – venv size in megabytes
- ``job_type`` – job type name
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Format log records as single-line JSON objects.

    Thread-safe; all state is computed per-record from the ``LogRecord``.
    """

    # Extra fields propagated from ``extra=`` kwargs to the JSON output.
    _EXTRA_FIELDS = (
        "worker",
        "action",
        "duration_sec",
        "size_mb",
        "job_type",
        "job_id",
        "source",
    )

    def format(self, record: logging.LogRecord) -> str:
        # Signature intentionally returns str (same as the base class at runtime).
        # The `# type: ignore[override]` below is NOT needed because the base
        # Formatter.format() already returns str; keeping the signature clean.
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
        }

        # Attach optional structured fields.
        for field in self._EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                log_obj[field] = value

        # Include exception info when present.
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


def configure_json_logging(level: str = "INFO") -> None:
    """
    Replace the root logger's formatter with ``JSONFormatter``.

    Call once at application startup *after* ``logging.basicConfig`` if
    structured JSON output is desired.

    Args:
        level: Logging level string (e.g. ``"INFO"``, ``"DEBUG"``).
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers:
        handler.setFormatter(JSONFormatter())
