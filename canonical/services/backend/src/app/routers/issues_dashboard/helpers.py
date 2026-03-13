"""
Helper functions for Issues Dashboard API endpoints.

Contains business logic for:
- Cell retrieval and filtering
- Issue counting by status
- Pagination calculations
- Orchestrator interactions
"""

import logging
import subprocess
from typing import List, Optional, Tuple

from fastapi import HTTPException, status

from ...config import BASE_DIR
from ...database import db
from ...models import Cell
from ...orchestrator import get_orchestrator_instance
from .models import IssueCounts

logger = logging.getLogger(__name__)


async def get_filtered_cells_and_counts(
    page: int,
    limit: int,
    status_filter: Optional[str] = None,
    item_type_filter: Optional[str] = None,
) -> Tuple[List[Cell], int, int, int, IssueCounts]:
    """
    Get filtered cells from issues-queue with pagination and counts.

    Args:
        page: Page number (starts at 1)
        limit: Number of items per page (1-100)
        status_filter: Optional status filter (pending, running, completed, error, or 'all')
        item_type_filter: Optional notebook_item_type_id filter

    Returns:
        Tuple of (page_items, total_items, total_pages, current_page, issue_counts)
    """
    # Get all cells and filter by type and book
    try:
        cells = await db.find_many("cells", current_user=current_user, model_class=Cell)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    base_filtered_cells = [
        c
        for c in cells
        if c.notebook_item_type_id == "ingestion-issue"
        and c.source_book_id == "book-issues-queue-v1"
    ]

    # Calculate total counts by status (for all cells, regardless of filter)
    # Map English status values (from CellStatus enum) to Portuguese field names
    issue_counts = IssueCounts()
    for cell in base_filtered_cells:
        cell_status = (
            cell.status.lower()
            if hasattr(cell.status, "lower")
            else str(cell.status).lower()
        )
        if cell_status == "pending":
            issue_counts.pendente += 1
        elif cell_status == "running":
            issue_counts.executando += 1
        elif cell_status == "completed":
            issue_counts.finalizado += 1
        elif cell_status == "error":
            issue_counts.erro += 1

    # Apply status filter if provided
    if status_filter and status_filter.lower() != "all":
        filtered_cells = [
            c for c in base_filtered_cells if c.status.lower() == status_filter.lower()
        ]
    else:
        filtered_cells = base_filtered_cells

    # Apply item_type filter if provided
    if item_type_filter and item_type_filter.lower() != "all":
        filtered_cells = [
            c
            for c in filtered_cells
            if hasattr(c, "notebook_item_type_id")
            and c.notebook_item_type_id == item_type_filter
        ]

    # Calculate pagination
    total_items = len(filtered_cells)
    total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1

    # Ensure page is within bounds
    if page > total_pages and total_pages > 0:
        page = total_pages

    # Calculate slice indices
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit

    # Get page items
    page_items = filtered_cells[start_idx:end_idx]

    logger.info(
        "Retrieved page %s/%s with %s items (total: %s, limit: %s, status_filter: %s, item_type_filter: %s)",
        page, total_pages, len(page_items), total_items, limit, status_filter or 'all', item_type_filter or 'all'
    )

    return page_items, total_items, total_pages, page, issue_counts


async def get_cell_by_id(cell_id: str) -> Cell:
    """
    Get a cell by its ID.

    Args:
        cell_id: UUID of the cell

    Returns:
        Cell object

    Raises:
        HTTPException: If cell not found
    """
    try:
        cell = await db.find_one(
            "cells", cell_id, current_user=current_user, model_class=Cell
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    if not cell:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Cell {cell_id} not found"
        )

    return cell


def trigger_ingest_script(
    source_dir: Optional[str] = None, dry_run: bool = False
) -> Tuple[str, str, int]:
    """
    Trigger the ingest.py script asynchronously.

    Args:
        source_dir: Optional source directory path
        dry_run: Whether to run in dry-run mode

    Returns:
        Tuple of (command_str, message, pid)

    Raises:
        HTTPException: If ingest.py not found or error triggering
    """
    # Build command
    ingest_script = BASE_DIR / "ingest.py"

    if not ingest_script.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ingest.py script not found"
        )

    cmd = ["python", str(ingest_script)]

    if source_dir:
        cmd.extend(["--source-dir", source_dir])

    if dry_run:
        cmd.append("--dry-run")

    # Run subprocess in background (non-blocking)
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(BASE_DIR)
    )

    command_str = " ".join(cmd)
    message = f"Ingest process started (PID: {process.pid})"
    logger.info("Started ingest.py process (PID: %s): %s", process.pid, command_str)

    return command_str, message, process.pid


def get_orchestrator_or_raise():
    """
    Get orchestrator instance or raise HTTPException if not available.

    Returns:
        Orchestrator instance

    Raises:
        HTTPException: If orchestrator not available
    """
    orchestrator = get_orchestrator_instance()

    if not orchestrator:
        logger.warning("Orchestrator instance not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized",
        )

    return orchestrator
