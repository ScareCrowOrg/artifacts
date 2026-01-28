"""
Shared Volume File Management for 3D Mesh Generation

Provides path management for file transfer between Backend (Kind/Linux)
and Windows Worker through shared volume architecture.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def get_shared_volume_path() -> Path:
    r"""
    Get the shared volume path for file transfer with Windows Worker.
    
    Path Mapping Architecture (MVP 4.1):
    - Backend (Kind/Linux): Uses /app volume mount (project root in Kind)
    - Worker (Windows Docker): Mounts project's .local-dev-data/scareverse-data as /data
    - Files written by Backend to /app/.local-dev-data/scareverse-data/jobs/{id}/input.png
    - Are visible in Windows at [PROJECT_ROOT]\.local-dev-data\scareverse-data\jobs\{id}\input.png
    - Are read by Worker from /data/jobs/{id}/input.png
    
    The SHARED_VOLUME_PATH for Backend should be /app/.local-dev-data/scareverse-data (default)
    The SHARED_VOLUME for Worker should be /data (default, mounting .local-dev-data/scareverse-data)
    
    Environment Variables:
        SHARED_VOLUME_PATH: Override default shared volume path
    
    Returns:
        Path object pointing to shared volume (Backend perspective)
    """
    # Use environment variable or default to /app bridge path
    shared_volume_env = os.getenv('SHARED_VOLUME_PATH', '/app/.local-dev-data/scareverse-data')
    shared_volume_path = Path(shared_volume_env)
    
    # Log the configuration for debugging
    logger.info(f"✅ Shared volume path configured: {shared_volume_path}")
    logger.debug(f"Shared volume exists: {shared_volume_path.exists()}")
    
    return shared_volume_path
