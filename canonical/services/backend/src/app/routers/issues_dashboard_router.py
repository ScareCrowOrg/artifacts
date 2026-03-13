"""
Issues Dashboard API Router - Reactive monitoring for the issues-queue.

Implements endpoints for:
- Listing cells from issues-queue
- Getting individual cell details
- Server-Sent Events (SSE) for real-time updates
- Triggering the ingest.py script
- Triggering manual processing of pending cells
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..auth import get_user_from_token_query
from ..models import Cell
from ..models.users import User
from ..permissions import has_permission
from .issues_dashboard.helpers import (
    get_cell_by_id,
    get_filtered_cells_and_counts,
    get_orchestrator_or_raise,
    trigger_ingest_script,
)

# Import models, streaming functions and helpers from submodules
from .issues_dashboard.models import (
    MonitoringControlResponse,
    MonitoringStatusResponse,
    PaginatedResponse,
    ProcessingControlResponse,
    ProcessingStatusResponse,
    ProcessPendingCellsResponse,
    TriggerIngestRequest,
    TriggerIngestResponse,
)
from .issues_dashboard.streaming import (
    stream_all_active_fragments,
    stream_cell_fragments,
    stream_events,
)

logger = logging.getLogger(__name__)

# Create dashboard router
issues_dashboard_router = APIRouter(
    prefix="/issues-dashboard", tags=["Issues Dashboard"]
)


# Endpoints


@issues_dashboard_router.get("/cells", response_model=PaginatedResponse[Cell])
async def get_issues_queue_cells(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    status: Optional[str] = Query(
        None,
        description="Filter by status (pending, running, completed, error, or 'all')",
    ),
    item_type: Optional[str] = Query(
        None, description="Filter by notebook_item_type_id"
    ),
    _current_user: User = Depends(has_permission(["issues.read"])),
) -> PaginatedResponse[Cell]:
    """
    Get paginated ingestion-issue cells from issues-queue with optional filtering.

    Required permission: issues.read

    Args:
        page: Page number (starts at 1)
        limit: Number of items per page (1-100)
        status: Optional status filter (pending, running, completed, error, or 'all')
        item_type: Optional notebook_item_type_id filter

    Returns:
        Paginated response with Cell objects and total issue counts by status
    """
    try:
        (
            page_items,
            total_items,
            total_pages,
            current_page,
            issue_counts,
        ) = await get_filtered_cells_and_counts(page, limit, status, item_type)

        return PaginatedResponse(
            items=page_items,
            total_items=total_items,
            total_pages=total_pages,
            current_page=current_page,
            items_per_page=limit,
            issue_counts=issue_counts,
        )
    except Exception as e:
        logger.error("Error retrieving cells: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving cells: {str(e)}",
        )


@issues_dashboard_router.get("/cells/{cell_id}", response_model=Cell)
async def get_cell_details(
    cell_id: str, _current_user: User = Depends(has_permission(["issues.read"]))
) -> Cell:
    """
    Get details of a specific cell.

    Required permission: issues.read

    Args:
        cell_id: UUID of the cell

    Returns:
        Cell object with full details
    """
    try:
        return await get_cell_by_id(cell_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving cell %s: %s", cell_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving cell: {str(e)}",
        )


@issues_dashboard_router.post("/ingest/trigger", response_model=TriggerIngestResponse)
async def trigger_ingest(
    request: TriggerIngestRequest,
    _current_user: User = Depends(has_permission(["issues.ingest"])),
) -> TriggerIngestResponse:
    """
    Trigger the ingest.py script asynchronously.

    Required permission: issues.ingest

    Args:
        request: TriggerIngestRequest with source_dir and dry_run options

    Returns:
        Status message about the triggered process
    """
    try:
        command_str, message, _pid = trigger_ingest_script(
            source_dir=request.source_dir, dry_run=request.dry_run
        )

        return TriggerIngestResponse(
            status="started", message=message, command=command_str
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error triggering ingest: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering ingest: {str(e)}",
        )


@issues_dashboard_router.post(
    "/process-pending-cells", response_model=ProcessPendingCellsResponse
)
async def process_pending_cells(
    _current_user: User = Depends(has_permission(["issues.process"])),
) -> ProcessPendingCellsResponse:
    """
    Trigger the orchestrator to immediately process pending cells.

    Required permission: issues.process

    This endpoint signals the running orchestrator to bypass its regular
    polling interval and immediately check and process any PENDING cells
    in the issues-queue.

    Returns:
        Status message about the triggered processing
    """
    try:
        orchestrator = get_orchestrator_or_raise()
        result = await orchestrator.force_process_pending_issues()

        logger.info("Manual processing trigger result: %s", result)

        return ProcessPendingCellsResponse(
            status=result["status"],
            message=result["message"],
            pending_count=result["pending_count"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error triggering pending cells processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering processing: {str(e)}",
        )


@issues_dashboard_router.get(
    "/monitoring/status", response_model=MonitoringStatusResponse
)
async def get_monitoring_status(
    _current_user: User = Depends(has_permission(["issues.read"])),
) -> MonitoringStatusResponse:
    """
    Get current status of the orchestrator monitoring loop.

    Required permission: issues.read

    Returns:
        Current monitoring status including active state and configuration
    """
    try:
        orchestrator = get_orchestrator_or_raise()
        status_info = orchestrator.get_monitoring_status()

        return MonitoringStatusResponse(
            active=status_info["active"],
            polling_interval=status_info["polling_interval"],
            max_concurrent_cells=status_info["max_concurrent_cells"],
            task_running=status_info["task_running"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting monitoring status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting status: {str(e)}",
        )


@issues_dashboard_router.post(
    "/monitoring/start", response_model=MonitoringControlResponse
)
async def start_monitoring(
    _current_user: User = Depends(has_permission(["issues.control"])),
) -> MonitoringControlResponse:
    """
    Start the orchestrator monitoring loop.

    Required permission: issues.control

    This endpoint starts the background task that continuously monitors
    the issues-queue for pending cells and processes them automatically.

    Returns:
        Status message about the monitoring start operation
    """
    try:
        orchestrator = get_orchestrator_or_raise()
        result = orchestrator.start_monitoring()

        logger.info("Start monitoring result: %s", result)

        return MonitoringControlResponse(
            status=result["status"], message=result["message"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error starting monitoring: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting monitoring: {str(e)}",
        )


@issues_dashboard_router.post(
    "/monitoring/stop", response_model=MonitoringControlResponse
)
async def stop_monitoring(
    _current_user: User = Depends(has_permission(["issues.control"])),
) -> MonitoringControlResponse:
    """
    Stop the orchestrator monitoring loop.

    Required permission: issues.control

    This endpoint stops the background task that monitors the issues-queue,
    effectively pausing automatic processing of pending cells.

    Returns:
        Status message about the monitoring stop operation
    """
    try:
        orchestrator = get_orchestrator_or_raise()
        result = orchestrator.stop_monitoring()

        logger.info("Stop monitoring result: %s", result)

        return MonitoringControlResponse(
            status=result["status"], message=result["message"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error stopping monitoring: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping monitoring: {str(e)}",
        )


@issues_dashboard_router.get(
    "/processing/status", response_model=ProcessingStatusResponse
)
async def get_processing_status(
    _current_user: User = Depends(has_permission(["issues.read"])),
) -> ProcessingStatusResponse:
    """
    Get current status of cell processing (paused or active).

    Required permission: issues.read

    Returns:
        Current processing status
    """
    try:
        orchestrator = get_orchestrator_or_raise()
        status_info = orchestrator.get_processing_status()

        return ProcessingStatusResponse(paused=status_info["paused"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting processing status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting status: {str(e)}",
        )


@issues_dashboard_router.post(
    "/processing/pause", response_model=ProcessingControlResponse
)
async def pause_processing(
    _current_user: User = Depends(has_permission(["issues.control"])),
) -> ProcessingControlResponse:
    """
    Pause cell processing.

    Required permission: issues.control

    When paused, the monitoring loop continues running but will not
    process any pending cells. This allows temporary suspension of processing.

    Returns:
        Status message about the pause operation
    """
    try:
        orchestrator = get_orchestrator_or_raise()
        result = orchestrator.pause_processing()

        logger.info("Pause processing result: %s", result)

        return ProcessingControlResponse(
            status=result["status"], message=result["message"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error pausing processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausing processing: {str(e)}",
        )


@issues_dashboard_router.post(
    "/processing/resume", response_model=ProcessingControlResponse
)
async def resume_processing(
    _current_user: User = Depends(has_permission(["issues.control"])),
) -> ProcessingControlResponse:
    """
    Resume cell processing.

    Required permission: issues.control

    Resumes processing of pending cells if it was previously paused.

    Returns:
        Status message about the resume operation
    """
    try:
        orchestrator = get_orchestrator_or_raise()
        result = orchestrator.resume_processing()

        logger.info("Resume processing result: %s", result)

        return ProcessingControlResponse(
            status=result["status"], message=result["message"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error resuming processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resuming processing: {str(e)}",
        )


@issues_dashboard_router.get("/events")
async def events_endpoint(
    request: Request,
    token: Optional[str] = Query(
        None, description="JWT token for authentication (required for SSE)"
    ),
):
    """
    Server-Sent Events (SSE) endpoint for real-time updates.

    Required permission: issues.read (validated via token)

    Note: Since EventSource doesn't support custom headers, authentication token
    must be passed via query parameter: ?token=<jwt_token>

    Streams events from the event bus to connected clients.
    Events include:
    - cell_state_changed
    - fragment_added
    - cell_created

    Returns:
        StreamingResponse with text/event-stream content type
    """
    # Authenticate user from token
    current_user = await get_user_from_token_query(token=token)

    # Check permissions after authentication
    if not any(perm in current_user.permissions for perm in ["issues.read", "*"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    return await stream_events(request)


@issues_dashboard_router.get("/cells/{cell_id}/stream-fragments")
async def cell_fragments_endpoint(
    cell_id: str,
    request: Request,
    _current_user: User = Depends(has_permission(["issues.read"])),
):
    """
    Server-Sent Events (SSE) endpoint for streaming cell fragments from Redis.

    Required permission: issues.read

    Streams fragments in real-time as they are published by the orchestrator
    during workflow execution.

    Args:
        cell_id: ID of the cell to stream fragments for
        request: FastAPI request object for disconnect detection

    Returns:
        StreamingResponse with text/event-stream content type
    """
    return await stream_cell_fragments(cell_id, request)


@issues_dashboard_router.get("/stream-all-active-fragments")
async def all_active_fragments_endpoint(
    request: Request,
    token: Optional[str] = Query(
        None, description="JWT token for authentication (required for SSE)"
    ),
):
    """
    Server-Sent Events (SSE) endpoint for streaming fragments from all active cells.

    Required permission: issues.read (validated via token)

    Note: Since EventSource doesn't support custom headers, authentication token
    must be passed via query parameter: ?token=<jwt_token>

    Subscribes to all cell fragment channels using Redis pattern subscription (celula:*:fragmentos)
    to provide a holistic real-time view of pipeline activity.

    Args:
        request: FastAPI request object for disconnect detection
        token: JWT token for authentication

    Returns:
        StreamingResponse with text/event-stream content type
    """
    # Authenticate user from token
    current_user = await get_user_from_token_query(token=token)

    # Check permissions after authentication
    if not any(perm in current_user.permissions for perm in ["issues.read", "*"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    return await stream_all_active_fragments(request)
