"""
Shared utilities for artifacts/canonical.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Pattern for safe profile names: alphanumeric start, then alnum/dot/dash/underscore
_SAFE_PROFILE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")


def resolve_venv_path(workers_path: Path, worker_name: str) -> Path:
    """Return the venv path for *worker_name*, respecting ``.venv-profile``.

    If the worker directory contains a ``.venv-profile`` file with a
    non-empty, safe profile name, the venv is placed under
    ``shared_venvs/{profile_name}/`` so multiple workers in the same profile
    share a single environment.

    Validation performed:
      - Empty or whitespace-only profile -> fallback to 1:1 venv (with warning).
      - ``..``, ``/``, ``\\`` or other unsafe characters -> fallback to 1:1
        (with error log) as a defence-in-depth measure against path traversal.
    """
    worker_dir = workers_path / worker_name
    profile_file = worker_dir / ".venv-profile"

    if not profile_file.exists():
        return worker_dir / ".venv"

    profile_name = profile_file.read_text().strip()

    # Finding 1: Empty or whitespace-only profile
    if not profile_name:
        logger.warning(
            "Empty .venv-profile for %s -- falling back to 1:1 venv",
            worker_name,
        )
        return worker_dir / ".venv"

    # Finding 3: Path traversal / unsafe profile name
    if not _SAFE_PROFILE_RE.match(profile_name):
        logger.error(
            "Invalid profile name %r for worker %s -- falling back to 1:1 venv",
            profile_name,
            worker_name,
        )
        return worker_dir / ".venv"

    return workers_path / "shared_venvs" / profile_name / ".venv"


def utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def load_job_type_definitions(job_types_dir: Path) -> Dict[str, Any]:
    """
    Load all job-type JSON definitions from a directory.

    Args:
        job_types_dir: Path to directory containing *.json job-type files.

    Returns:
        Dict mapping job-type name → definition dict. Aliases are also included
        as additional keys pointing to the same definition.
    """
    if not job_types_dir.exists():
        logger.warning("job-types directory not found: %s", job_types_dir)
        return {}

    result: Dict[str, Any] = {}
    for json_file in sorted(job_types_dir.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as fh:
                definition = json.load(fh)
            name = definition.get("name")
            if not name:
                logger.warning("Job type file missing 'name' field: %s", json_file)
                continue
            result[name] = definition
            for alias in definition.get("aliases", []):
                if alias != name:
                    result[alias] = definition
            logger.debug("Loaded job-type: %s", name)
        except Exception as exc:
            logger.error("Failed to load job-type from %s: %s", json_file, exc)

    return result


def strip_data_uri_prefix(data: str) -> str:
    """
    Strip base64 data-URI prefix if present.

    Handles both ``data:image/png;base64,<b64>`` and plain base64 strings.

    Args:
        data: Input string (with or without data-URI prefix).

    Returns:
        Plain base64 string without prefix.
    """
    if "," in data:
        return data.split(",", 1)[1]
    return data


def safe_json_loads(raw: str, context: str = "") -> Optional[Dict[str, Any]]:
    """Parse JSON string, returning None and logging on error."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("JSON decode error%s: %s | raw: %.200s", f" ({context})" if context else "", exc, raw)
        return None
