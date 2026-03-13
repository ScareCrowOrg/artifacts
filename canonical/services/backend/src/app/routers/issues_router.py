"""
Issues API Router - Simplified endpoints for issues queue management.

Implements the endpoints requested in the issue:
- POST /api/issues/process - Trigger manual processing
- POST /api/issues/monitoring/start - Start automatic monitoring
- POST /api/issues/monitoring/stop - Stop automatic monitoring
- POST /api/issues/processing/pause - Pause queue processing
- POST /api/issues/processing/resume - Resume queue processing
- POST /api/issues/ingest - Trigger manual ingestion
"""

import logging
import subprocess
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..config import BASE_DIR
from ..models.users import User
from ..orchestrator import get_orchestrator_instance
from ..permissions import has_permission

logger = logging.getLogger(__name__)

# Create issues router
issues_router = APIRouter(prefix="/issues", tags=["Issues"])


# Request/Response models


class IngestRequest(BaseModel):
    """Request model for triggering ingest.py."""

    source_dir: Optional[str] = None
    dry_run: bool = False


class IngestResponse(BaseModel):
    """Response model for ingest trigger."""

    status: str
    ingested: int = 0
    message: Optional[str] = None


class ProcessResponse(BaseModel):
    """Response model for processing trigger."""

    status: str
    processed: int


class MonitoringResponse(BaseModel):
    """Response model for monitoring control."""

    status: str


class ProcessingResponse(BaseModel):
    """Response model for processing control."""

    status: str


# Endpoints


@issues_router.post("/ingest", response_model=IngestResponse)
async def trigger_manual_ingest(
    request: IngestRequest,
    _current_user: User = Depends(has_permission(["issues.ingest"])),
) -> IngestResponse:
    """
    Trigger manual ingestion of documents.

    Required permission: issues.ingest

    Executes the ingest.py script with parameters received from the frontend,
    creating new cells in the issues book.

    Args:
        request: IngestRequest with source_dir and dry_run options

    Returns:
        IngestResponse with status and number of files ingested
    """
    try:
        # Build command
        ingest_script = BASE_DIR / "ingest.py"

        if not ingest_script.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ingest.py script not found",
            )

        cmd = ["python", str(ingest_script)]

        if request.source_dir:
            cmd.extend(["--source-dir", request.source_dir])

        if request.dry_run:
            cmd.append("--dry-run")

        # Run subprocess in background (non-blocking)
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(BASE_DIR)
        )

        command_str = " ".join(cmd)
        logger.info("Started ingest.py process (PID: %s): %s", process.pid, command_str)

        return IngestResponse(
            status="ok",
            ingested=0,  # Cannot determine count immediately for async process
            message=f"Ingest process started (PID: {process.pid})",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error triggering ingest: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering ingest: {str(e)}",
        )


@issues_router.post("/process", response_model=ProcessResponse)
async def trigger_manual_processing(
    _current_user: User = Depends(has_permission(["issues.process"])),
) -> ProcessResponse:
    """
    Trigger manual processing of all pending cells.

    Required permission: issues.process

    Processes immediately all pending cells in the issues book,
    executing the main workflow of each cell.

    Returns:
        ProcessResponse with status and number of cells processed
    """
    try:
        # Get the orchestrator instance
        orchestrator = get_orchestrator_instance()

        if not orchestrator:
            logger.warning("Orchestrator instance not available for manual trigger")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Orchestrator not running. Please start the orchestrator service.",
            )

        # Trigger immediate processing
        result = await orchestrator.force_process_pending_issues()

        logger.info("Manual processing trigger result: %s", result)

        # Map internal status to issue requirements
        response_status = (
            "ok"
            if result["status"] in ["processing_triggered", "no_pending_cells"]
            else "error"
        )

        return ProcessResponse(
            status=response_status, processed=result.get("pending_count", 0)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error triggering pending cells processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering processing: {str(e)}",
        )


@issues_router.post("/monitoring/start", response_model=MonitoringResponse)
async def start_automatic_monitoring(
    _current_user: User = Depends(has_permission(["issues.control"])),
) -> MonitoringResponse:
    """
    Start automatic monitoring loop.

    Required permission: issues.control

    Starts the background monitoring task that continuously processes
    pending cells in the issues queue at configurable intervals.

    Returns:
        MonitoringResponse with status
    """
    try:
        orchestrator = get_orchestrator_instance()

        if not orchestrator:
            logger.warning("Orchestrator instance not available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Orchestrator not initialized",
            )

        result = orchestrator.start_monitoring()

        logger.info("Start monitoring result: %s", result)

        return MonitoringResponse(status="monitoring_started")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error starting monitoring: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting monitoring: {str(e)}",
        )


@issues_router.post("/monitoring/stop", response_model=MonitoringResponse)
async def stop_automatic_monitoring(
    _current_user: User = Depends(has_permission(["issues.control"])),
) -> MonitoringResponse:
    """
    Stop automatic monitoring loop.

    Required permission: issues.control

    Stops the background monitoring task, interrupting automatic
    processing of pending cells.

    Returns:
        MonitoringResponse with status
    """
    try:
        orchestrator = get_orchestrator_instance()

        if not orchestrator:
            logger.warning("Orchestrator instance not available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Orchestrator not initialized",
            )

        result = orchestrator.stop_monitoring()

        logger.info("Stop monitoring result: %s", result)

        return MonitoringResponse(status="monitoring_stopped")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error stopping monitoring: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping monitoring: {str(e)}",
        )


@issues_router.post("/processing/pause", response_model=ProcessingResponse)
async def pause_queue_processing(
    _current_user: User = Depends(has_permission(["issues.control"])),
) -> ProcessingResponse:
    """
    Pause queue processing.

    Required permission: issues.control

    Pauses the processing of cells, temporarily disabling the queue.
    The monitoring loop continues running but will not process cells.

    Returns:
        ProcessingResponse with status
    """
    try:
        orchestrator = get_orchestrator_instance()

        if not orchestrator:
            logger.warning("Orchestrator instance not available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Orchestrator not initialized",
            )

        result = orchestrator.pause_processing()

        logger.info("Pause processing result: %s", result)

        return ProcessingResponse(status="processing_paused")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error pausing processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausing processing: {str(e)}",
        )


@issues_router.post("/processing/resume", response_model=ProcessingResponse)
async def resume_queue_processing(
    _current_user: User = Depends(has_permission(["issues.control"])),
) -> ProcessingResponse:
    """
    Resume queue processing.

    Required permission: issues.control

    Resumes the processing of cells, re-enabling the queue after it
    was previously paused.

    Returns:
        ProcessingResponse with status
    """
    try:
        orchestrator = get_orchestrator_instance()

        if not orchestrator:
            logger.warning("Orchestrator instance not available")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Orchestrator not initialized",
            )

        result = orchestrator.resume_processing()

        logger.info("Resume processing result: %s", result)

        return ProcessingResponse(status="processing_resumed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error resuming processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resuming processing: {str(e)}",
        )
