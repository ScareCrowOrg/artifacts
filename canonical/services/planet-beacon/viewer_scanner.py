#!/usr/bin/env python3
"""
Viewer scanner for planet-beacon.

Scans a base directory for available viewers. A viewer is a subdirectory
that contains an ``index.html`` file.

Usage::

    from viewer_scanner import scan_viewers

    viewers = await scan_viewers("/app/artifacts/canonical/viewers")
    # [{"id": "dynamic-workspace", "path": "/artifacts/canonical/viewers/dynamic-workspace"}]
"""

import logging
import os
from typing import List, Dict

logger = logging.getLogger(__name__)


async def scan_viewers(base_dir: str) -> List[Dict[str, str]]:
    """
    Scan *base_dir* for subdirectories that contain an ``index.html``.

    Each qualifying subdirectory is considered an available viewer.

    Args:
        base_dir: Absolute path to the viewers root directory.

    Returns:
        List of dicts with keys ``id`` (directory name) and ``path``
        (canonical URL path, e.g. ``/artifacts/canonical/viewers/dynamic-workspace``).
        Returns an empty list if *base_dir* does not exist or is not a directory.
    """
    if not os.path.isdir(base_dir):
        logger.warning("Viewers directory does not exist or is not a directory: %s", base_dir)
        return []

    viewers: List[Dict[str, str]] = []

    try:
        entries = os.listdir(base_dir)
    except OSError as exc:
        logger.warning("Failed to list viewers directory %s: %s", base_dir, exc)
        return []

    for entry in sorted(entries):
        viewer_path = os.path.join(base_dir, entry)
        if not os.path.isdir(viewer_path):
            continue
        index_path = os.path.join(viewer_path, "index.html")
        if not os.path.isfile(index_path):
            logger.debug("Skipping %s — no index.html found", entry)
            continue
        viewers.append(
            {
                "id": entry,
                "path": f"/artifacts/canonical/viewers/{entry}",
            }
        )
        logger.debug("Discovered viewer: %s", entry)

    logger.info("Scanned %s — found %d viewer(s)", base_dir, len(viewers))
    return viewers
