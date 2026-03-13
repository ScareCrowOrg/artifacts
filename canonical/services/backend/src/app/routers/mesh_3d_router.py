"""
3D Mesh Prototyping Cell - API Endpoints

Provides job status polling and asset serving endpoints for the 3D cell.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)

# Create router
mesh_3d_router = APIRouter(prefix="/cells", tags=["3D Mesh Prototyping"])


@mesh_3d_router.get("/3d-job-status/{job_id}")
async def get_3d_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status of a 3D mesh generation job.

    Polls Redis for job status and retrieves results when completed.

    Args:
        job_id: Unique job identifier returned from execute-ephemeral

    Returns:
        Dict containing:
            - status: Job status (queued/processing/completed/failed/not_found)
            - mesh_data: Base64 GLB data (if completed)
            - metadata: Processing metadata (if completed)
            - error: Error message (if failed or not found)

    Status Codes:
        200: Status retrieved successfully
        404: Job not found
        500: Server error
    """
    try:
        logger.info("Polling job status: %s", job_id)

        # Import get_job_status from cell backend dynamically
        get_status = await import_cell_function(
            "3d-mesh-prototyping-cell", "get_job_status"
        )

        result = await get_status(job_id)

        if result.get("status") == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error polling job status: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status polling failed: {str(e)}",
        )


async def import_cell_function(cell_type_id: str, function_name: str):
    """
    Dynamically import a function from a cell's backend module.

    Args:
        cell_type_id: Cell type identifier
        function_name: Name of the function to import

    Returns:
        The imported function
    """
    import importlib.util

    from ..config import BASE_DIR

    cell_backend_path = (
        BASE_DIR
        / "artifacts"
        / "canonical"
        / "cell_types"
        / cell_type_id
        / "backend"
        / "scripts"
        / "main.py"
    )

    if not cell_backend_path.exists():
        raise FileNotFoundError(f"Backend script not found: {cell_backend_path}")

    spec = importlib.util.spec_from_file_location(
        f"cell_{cell_type_id}_main", cell_backend_path
    )

    if not spec or not spec.loader:
        raise ImportError(f"Failed to load module spec for {cell_type_id}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, function_name):
        raise AttributeError(
            f"Function '{function_name}' not found in {cell_type_id} backend"
        )

    return getattr(module, function_name)
