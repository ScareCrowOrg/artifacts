"""
JobExecutor – Subprocess orchestration for GateKeeper Service.

Delegates to the shared WorkerExecutor implementation, providing a thin
wrapper that resolves the workers path from config and handles the
job-type config shape expected by the dispatcher.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import config

# Support importing shared module both in Docker (PYTHONPATH=/app/artifacts)
# and in local development / tests (path resolved relative to this file).
try:
    from canonical.shared.worker_executor import WorkerExecutor as _WorkerExecutor
except ImportError:
    _canonical_parent = Path(__file__).resolve().parents[2].parent
    if str(_canonical_parent) not in sys.path:
        sys.path.insert(0, str(_canonical_parent))
    from canonical.shared.worker_executor import WorkerExecutor as _WorkerExecutor

logger = logging.getLogger(__name__)

_executor: Optional[_WorkerExecutor] = None


def _get_executor() -> _WorkerExecutor:
    global _executor
    if _executor is None:
        _executor = _WorkerExecutor(workers_path=str(config.WORKERS_PATH))
    return _executor


async def execute_subprocess_job(
    job_type: str,
    job_id: str,
    input_data: Dict[str, Any],
    job_type_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a job via subprocess worker.

    Args:
        job_type: Job type name.
        job_id: Unique job identifier.
        input_data: Arbitrary job input forwarded to the worker stdin.
        job_type_config: Entry from JOB_TYPES_CONFIG with ``execution_model == "subprocess"``.

    Returns:
        The result dict produced by the worker.
    """
    executor = _get_executor()
    logger.info("[%s] Dispatching subprocess job type=%s", job_id, job_type)
    return await executor.execute(job_type, job_id, input_data, job_type_config)


def invalidate_venv_cache(worker_name: str | None = None) -> None:
    """Force venv re-check on next execution (useful after worker updates)."""
    _get_executor().invalidate_venv_cache(worker_name)
