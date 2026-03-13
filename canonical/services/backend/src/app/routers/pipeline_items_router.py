"""
PipelineItem API Router - RESTful endpoints for PipelineItem management.

Implements endpoints for managing PipelineItem instances which represent
execution history and context for notebook items.

PipelineItems are NOT persisted as separate entities. They are runtime DTOs
reconstructed from ExecutionRecords stored in NotebookItem.fragments.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional, Literal
import logging

from ..models import User
from ..models.execution_models import ExecutionRecord
from ..core.models import PipelineItem, NotebookItem
from ..models.content import Cell, Book
from ..database import db
from ..auth import get_current_user_required

logger = logging.getLogger(__name__)

# Create pipeline_items router
pipeline_items_router = APIRouter(prefix="/pipeline-items", tags=["PipelineItems"])


def _extract_execution_records_from_fragments(notebook_item: NotebookItem) -> List[ExecutionRecord]:
    """
    Extract and validate ExecutionRecords from NotebookItem.fragments.

    Filters fragments by type="execution_record" and validates them against
    the ExecutionRecord model.

    Args:
        notebook_item: NotebookItem containing fragments

    Returns:
        List of validated ExecutionRecord instances
    """
    execution_records = []

    for fragment in notebook_item.fragments:
        # Skip if not a dict (could be a simple string fragment)
        if not isinstance(fragment, dict):
            continue

        # Check if it's an execution record
        if fragment.get("type") == "execution_record":
            try:
                # Validate and create ExecutionRecord instance
                execution_record = ExecutionRecord(**fragment)
                execution_records.append(execution_record)
            except Exception as e:
                logger.warning(
                    f"Invalid execution record in {notebook_item.id}: {e}. " f"Fragment: {fragment}"
                )
                # Skip invalid records
                continue

    return execution_records


def _map_execution_record_to_pipeline_item(
    execution_record: ExecutionRecord, notebook_item: NotebookItem
) -> PipelineItem:
    """
    Map an ExecutionRecord to a PipelineItem DTO.

    Reconstructs a PipelineItem from a persisted ExecutionRecord,
    populating all required fields for the API response.

    Args:
        execution_record: ExecutionRecord from notebook_item.fragments
        notebook_item: The NotebookItem that owns this execution

    Returns:
        PipelineItem DTO for API response
    """
    # Determine cell_type_id from notebook_item
    cell_type_id = ""
    if hasattr(notebook_item, "notebook_item_type_id"):
        cell_type_id = notebook_item.notebook_item_type_id
    # tipoCelulaId is deprecated, removed fallback

    # Create PipelineItem from ExecutionRecord
    pipeline_item = PipelineItem(
        id=execution_record.pipeline_item_id,
        notebook_item_id=notebook_item.id,
        notebook_item_data=notebook_item,
        cell_id=notebook_item.id,  # For backward compatibility
        cell_type_id=cell_type_id,
        assignee_id=execution_record.assignee_id,
        fragments=execution_record.fragments,
        status=execution_record.status,
        data=execution_record.initial_data_snapshot or {},
        error=execution_record.error,
        created_at=execution_record.created_at,
        updated_at=execution_record.updated_at,
    )

    return pipeline_item


@pipeline_items_router.get("", response_model=List[PipelineItem])
async def list_pipeline_items(
    notebook_item_id: Optional[str] = Query(
        None, description="Filter by notebook_item_id to get execution history for a specific item"
    ),
    status_filter: Optional[Literal["pending", "running", "completed", "error"]] = Query(
        None, alias="status", description="Filter by execution status"
    ),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of items to return"),
    current_user: User = Depends(get_current_user_required),
):
    """
    List PipelineItem execution instances extracted from NotebookItem.fragments.

    This endpoint does NOT query a separate pipeline_items collection.
    Instead, it:
    1. Fetches NotebookItem(s) by notebook_item_id (if provided) or all for the user
    2. Extracts ExecutionRecords from notebook_item.fragments (filtered by type="execution_record")
    3. Maps each ExecutionRecord to a PipelineItem DTO
    4. Returns the list of PipelineItems

    Supports filtering by:
    - notebook_item_id: Get all executions for a specific notebook item
    - status: Filter by execution status (pending, running, completed, error)

    Returns PipelineItems with full notebook_item_data for traceability.

    Example usage:
    - GET /api/pipeline-items?notebook_item_id=abc123 - Get all executions for item abc123
    - GET /api/pipeline-items?status=error - Get all failed executions
    - GET /api/pipeline-items?notebook_item_id=abc123&status=completed - Get completed runs for abc123
    """
    try:
        all_pipeline_items = []

        if notebook_item_id:
            # Fetch specific notebook item
            # Try celulas first
            try:
                notebook_item = await db.find_one(
                    "cells",
                    notebook_item_id,
                    current_user=current_user,
                    model_class=Cell,
                )
            except PermissionError as e:
                raise HTTPException(status_code=403, detail=str(e))

            # If not found, try livros
            if not notebook_item:
                try:
                    notebook_item = await db.find_one(
                        "books",
                        notebook_item_id,
                        current_user=current_user,
                        model_class=Book,
                    )
                except PermissionError as e:
                    raise HTTPException(status_code=403, detail=str(e))

            if not notebook_item:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"NotebookItem {notebook_item_id} not found",
                )

            # Extract execution records from this notebook item
            execution_records = _extract_execution_records_from_fragments(notebook_item)

            # Map to PipelineItems
            for execution_record in execution_records:
                pipeline_item = _map_execution_record_to_pipeline_item(
                    execution_record, notebook_item
                )
                all_pipeline_items.append(pipeline_item)
        else:
            # Fetch all notebook items for the user
            # Get celulas
            try:
                celulas = await db.find_many(
                    "cells",
                    current_user=current_user,
                    model_class=Cell,
                )

                for celula in celulas:
                    execution_records = _extract_execution_records_from_fragments(celula)
                    for execution_record in execution_records:
                        pipeline_item = _map_execution_record_to_pipeline_item(
                            execution_record, celula
                        )
                        all_pipeline_items.append(pipeline_item)
            except Exception as e:
                logger.warning("Error fetching celulas: %s", e)

            # Get livros
            try:
                livros = await db.find_many(
                    "books",
                    current_user=current_user,
                    model_class=Book,
                )

                for livro in livros:
                    execution_records = _extract_execution_records_from_fragments(livro)
                    for execution_record in execution_records:
                        pipeline_item = _map_execution_record_to_pipeline_item(
                            execution_record, livro
                        )
                        all_pipeline_items.append(pipeline_item)
            except Exception as e:
                logger.warning("Error fetching livros: %s", e)

        # Filter by status if provided
        if status_filter:
            all_pipeline_items = [
                item for item in all_pipeline_items if item.status == status_filter
            ]

        # Sort by created_at descending (most recent first)
        all_pipeline_items.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        paginated_items = all_pipeline_items[skip : skip + limit]

        logger.info(
            f"Listed {len(paginated_items)} pipeline items "
            f"(total: {len(all_pipeline_items)}, "
            f"notebook_item_id: {notebook_item_id}, "
            f"status: {status_filter}, "
            f"skip: {skip}, limit: {limit})"
        )

        return paginated_items

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing pipeline items: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing pipeline items: {str(e)}",
        )


@pipeline_items_router.get("/{pipeline_item_id}", response_model=PipelineItem)
async def get_pipeline_item(
    pipeline_item_id: str, current_user: User = Depends(get_current_user_required)
):
    """
    Get a specific PipelineItem by ID.

    This endpoint does NOT query a separate pipeline_items collection.
    Instead, it:
    1. Searches through all NotebookItems (celulas and livros) for the user
    2. Looks for an ExecutionRecord with matching pipeline_item_id in fragments
    3. Maps the ExecutionRecord to a PipelineItem DTO
    4. Returns the PipelineItem

    Returns the full PipelineItem including notebook_item_data.
    """
    try:
        # Search in celulas
        try:
            celulas = await db.find_many("cells", current_user=current_user, model_class=Cell)

            for celula in celulas:
                execution_records = _extract_execution_records_from_fragments(celula)
                for execution_record in execution_records:
                    if execution_record.pipeline_item_id == pipeline_item_id:
                        pipeline_item = _map_execution_record_to_pipeline_item(
                            execution_record, celula
                        )
                        logger.info("Retrieved pipeline item: %s from celula %s", pipeline_item_id, celula.id)
                        return pipeline_item
        except Exception as e:
            logger.warning("Error searching celulas: %s", e)

        # Search in livros
        try:
            livros = await db.find_many("books", current_user=current_user, model_class=Book)

            for livro in livros:
                execution_records = _extract_execution_records_from_fragments(livro)
                for execution_record in execution_records:
                    if execution_record.pipeline_item_id == pipeline_item_id:
                        pipeline_item = _map_execution_record_to_pipeline_item(
                            execution_record, livro
                        )
                        logger.info("Retrieved pipeline item: %s from livro %s", pipeline_item_id, livro.id)
                        return pipeline_item
        except Exception as e:
            logger.warning("Error searching livros: %s", e)

        # Not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PipelineItem {pipeline_item_id} not found",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting pipeline item %s: %s", pipeline_item_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting pipeline item: {str(e)}",
        )
