"""
Shared utilities for artifacts/canonical.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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


def safe_json_loads(raw: str, context: str = "") -> Optional[Dict[str, Any]]:
    """Parse JSON string, returning None and logging on error."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("JSON decode error%s: %s | raw: %.200s", f" ({context})" if context else "", exc, raw)
        return None
