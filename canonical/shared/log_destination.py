"""
log_destination — Shared utility: configure a file handler for SCARE_LOG_DESTINATION.

When the environment variable ``SCARE_LOG_DESTINATION`` is set, this module
attaches a ``logging.FileHandler`` (and optionally a ``JSONFormatter``) to the
root Python logger so that every log record is **also** written to the mapped
host file (via the Docker volume injected by scareverse-builder).

Usage::

    # At the end of a service's logging initialisation (after basicConfig):
    from canonical.shared.log_destination import configure_log_destination
    configure_log_destination()

    # With JSONFormatter (gatekeeper-style):
    from canonical.shared.log_destination import configure_log_destination
    configure_log_destination(use_json=True)

The function is **idempotent**: calling it more than once for the same path
adds the handler only once.

Environment variable:
    SCARE_LOG_DESTINATION   Absolute path where logs should be written inside
                            the container (e.g. ``/app/logs/service.log``).
                            When absent or empty, this function is a no-op.
"""

import logging
import os
from typing import Optional

__all__ = ["configure_log_destination"]

_ENV_VAR = "SCARE_LOG_DESTINATION"


def configure_log_destination(
    logger: Optional[logging.Logger] = None,
    use_json: bool = False,
) -> bool:
    """
    Attach a ``FileHandler`` to *logger* (default: root logger) writing to
    ``$SCARE_LOG_DESTINATION`` when that env var is set.

    Args:
        logger:   Logger to attach the handler to.  Defaults to the root logger.
        use_json: When ``True``, wraps the handler with ``JSONFormatter`` from
                  ``json_logger`` (available in gatekeeper).  Falls back to a
                  plain text formatter if the import fails.

    Returns:
        ``True`` if a new ``FileHandler`` was added, ``False`` otherwise
        (env var not set, already configured, or path error).
    """
    dest = os.environ.get(_ENV_VAR, "").strip()
    if not dest:
        return False

    target = logger or logging.getLogger()

    # Idempotency: skip if a FileHandler for this path is already attached
    dest_norm = os.path.normcase(os.path.abspath(dest))
    for handler in target.handlers:
        if isinstance(handler, logging.FileHandler) and os.path.normcase(handler.baseFilename) == dest_norm:
            logging.getLogger(__name__).debug(
                "[log_destination] FileHandler already configured for %s — skipping", dest
            )
            return False

    # Ensure parent directory exists (the builder already creates it on the host,
    # but in-container the mount target may need the parent dir inside /app/logs/).
    log_dir = os.path.dirname(dest)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    try:
        file_handler = logging.FileHandler(dest, encoding="utf-8")
    except OSError as exc:
        logging.getLogger(__name__).error(
            "[log_destination] Cannot open %s for writing: %s", dest, exc
        )
        return False

    # Formatter selection
    formatter: logging.Formatter
    if use_json:
        try:
            # json_logger lives in gatekeeper; import lazily to avoid hard dependency
            import importlib
            json_logger_mod = importlib.import_module("json_logger")
            formatter = json_logger_mod.JSONFormatter()
        except ImportError:
            logging.getLogger(__name__).warning(
                "[log_destination] json_logger unavailable — falling back to plain text formatter"
            )
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    file_handler.setFormatter(formatter)
    target.addHandler(file_handler)

    logging.getLogger(__name__).info(
        "[log_destination] FileHandler added → %s (json=%s)", dest, use_json
    )
    return True
