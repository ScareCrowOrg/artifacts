"""
Thin bridge to ``artifacts/canonical/shared`` job-creation utilities.

Exports ``create_job`` from the canonical shared module so backend routers can
import with a single, stable path instead of repeating sys.path manipulation in
every call-site.  The canonical shared package is located relative to this file,
so the bridge works regardless of the working directory or install layout.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure artifacts/canonical/ is on sys.path before the first import.
# This file is at  backend/app/services/canonical_client.py
# parents[0] = services/   parents[1] = app/   parents[2] = backend/
# parents[3] = project root
# ---------------------------------------------------------------------------
_CANONICAL_DIR = str(Path(__file__).resolve().parents[3] / "artifacts" / "canonical")
if _CANONICAL_DIR not in sys.path:
    sys.path.insert(0, _CANONICAL_DIR)

try:
    from shared.redis_client import create_job as create_job  # noqa: F401  (re-export)
except ImportError as _exc:
    # Canonical shared not available (e.g., stripped deployment without artifacts/).
    # Raise a clear error rather than propagating a confusing ImportError later.
    raise ImportError(
        "Cannot import 'create_job' from artifacts/canonical/shared/redis_client. "
        f"Ensure the canonical directory exists at {_CANONICAL_DIR!r}. "
        f"Original error: {_exc}"
    ) from _exc

__all__ = ["create_job"]
