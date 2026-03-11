"""
Job Queue Module for 3D Mesh Generation

Provides Redis-based job queueing and status tracking for hybrid
Windows Worker integration.
"""

from .queue_manager import queue_3d_generation_job, get_job_status
from .file_manager import get_shared_volume_path

# Redis client from canonical shared (DRY principle)
try:
    from canonical.shared.redis_client import get_redis_client
except ImportError:
    # Local dev fallback
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'shared'))
    from redis_client import get_redis_client

__all__ = [
    'queue_3d_generation_job',
    'get_job_status',
    'get_redis_client',
    'get_shared_volume_path'
]
