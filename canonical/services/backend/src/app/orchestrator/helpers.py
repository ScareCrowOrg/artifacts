"""
Helper functions for the Orchestrator.

This module contains utility functions for:
- Converting between Cell and PipelineItem
- Updating cells from pipeline results
- Publishing fragments to Redis for real-time streaming
- Publishing fragments to event bus as fallback

Technical naming: All function names and parameters in English.
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime

from app.models import Cell, CellStatus, Fragment
from app.core.models import PipelineItem, Fragment as CoreFragment
from app.database import db
from app.auth_legacy import SYSTEM_USER
from app.event_bus import publish_fragment_added_sync

logger = logging.getLogger(__name__)

# Redis client (imported from parent module)
redis_client = None


def set_redis_client(client) -> None:
    """
    Set the Redis client for publishing fragments.

    Args:
        client: Redis client instance or None
    """
    global redis_client
    redis_client = client


def cell_to_pipeline_item(cell: Cell, agent_data: Dict[str, Any]) -> PipelineItem:
    """
    Convert a Cell to a PipelineItem for workflow execution.

    Handles mixed fragment types (str and Dict) from the Cell model,
    converting them to CoreFragment objects for pipeline processing.

    Args:
        cell: Source cell
        agent_data: Context about the executing agent

    Returns:
        PipelineItem instance
    """
    # Convert existing fragments (str or Dict) to CoreFragment objects
    fragments = []
    for frag in cell.fragments:
        if isinstance(frag, str):
            # Legacy string fragment - convert to CoreFragment and serialize
            core_frag = CoreFragment(type="legacy_memory", content=frag)
            fragments.append(core_frag.model_dump())
        elif isinstance(frag, dict):
            # Structured dict fragment - extract fields and serialize
            core_frag = CoreFragment(
                type=frag.get("tipo", "unknown"),
                content=frag.get("conteudo", frag),
                result=frag.get("resultado"),
            )
            fragments.append(core_frag.model_dump())
        else:
            # Handle CoreFragment objects or other types
            if hasattr(frag, "tipo") and hasattr(frag, "conteudo"):
                # Already a Fragment-like object
                core_frag = CoreFragment(
                    type=frag.type, content=frag.content, result=getattr(frag, "resultado", None)
                )
                fragments.append(core_frag.model_dump())
            else:
                # Unknown type - convert to string and serialize
                core_frag = CoreFragment(type="unknown", content=str(frag))
                fragments.append(core_frag.model_dump())

    return PipelineItem(
        notebook_item_id=cell.id,  # Ensure notebook_item_id is set
        notebook_item_data=cell,  # Ensure notebook_item_data is set
        cell_id=cell.id,
        cell_type_id=cell.notebook_item_type_id,
        status="pending",
        data=cell.initial_data.copy(),
        fragments=fragments,
        agent_data=agent_data,
        assignee_id=cell.assignee_id,  # Use validated assignee_id
        created_at=cell.created_at,
        updated_at=cell.updated_at,
    )


async def update_cell_from_pipeline_item(cell_id: str, item: PipelineItem) -> bool:
    """
    Update a Cell from a PipelineItem by creating and persisting an ExecutionRecord.

    This function has been refactored to use the ExecutionRecord approach instead of
    directly merging PipelineItem.fragments into Cell.fragments.

    The ExecutionRecord is created from the PipelineItem and appended to the Cell.fragments
    with a type marker for filtering.

    Args:
        cell_id: ID of the cell to update
        item: PipelineItem with execution results

    Returns:
        True if update succeeded, False otherwise
    """
    try:
        from app.models.execution_models import ExecutionRecord

        # Fetch the cell
        cell = await db.find_one("cells", cell_id, current_user=SYSTEM_USER, model_class=Cell)
        if not cell:
            logger.error("Cell %s not found for update", cell_id)
            return False

        # Create ExecutionRecord DTO from PipelineItem
        execution_record = ExecutionRecord(
            pipeline_item_id=item.id,
            status=item.status,
            assignee_id=item.assignee_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            fragments=item.fragments,
            error=item.error,
            initial_data_snapshot=cell.initial_data.copy() if cell.initial_data else None,
        )

        # Convert to dict with type marker (already has type="execution_record" by default)
        execution_record_dict = execution_record.model_dump(mode="json")

        # Append to cell.fragments (using the property for backward compatibility)
        cell.fragments.append(execution_record_dict)

        # Convert status to CellStatus
        status_map = {
            "pending": CellStatus.PENDING,
            "running": CellStatus.RUNNING,
            "completed": CellStatus.COMPLETED,
            "error": CellStatus.ERROR,
        }
        status = status_map.get(item.status, CellStatus.ERROR)

        # Prepare updates
        updates = {
            "status": status.value,
            "fragments": [f if isinstance(f, str) else f for f in cell.fragments],
            "updated_at": item.updated_at.isoformat(),
        }

        # Only update data fields that changed in the pipeline
        # Don't overwrite the entire initial_data
        if item.data and item.data != cell.initial_data:
            # Merge data changes
            updated_data = cell.initial_data.copy()
            updated_data.update(item.data)
            updates["initial_data"] = updated_data

        # Update the cell in database
        success = await db.update("cells", cell_id, updates, current_user=SYSTEM_USER)

        if success:
            logger.info("Updated cell %s with ExecutionRecord %s (status: %s)", cell_id, item.id, item.status)
        else:
            logger.warning("Failed to update cell %s - database update returned False", cell_id)

        return success

    except Exception as e:
        logger.error("Error updating cell %s from PipelineItem: %s", cell_id, e, exc_info=True)
        return False


def publish_fragment_to_redis(
    cell_id: str, fragment: Union[CoreFragment, Dict[str, Any], str]
) -> None:
    """
    Publish a fragment to Redis for real-time streaming and to event bus as fallback.

    When Redis is disabled, fragments are published only to the event bus.
    When Redis is enabled, fragments are published to both Redis and event bus
    for maximum compatibility.

    Args:
        cell_id: ID of the cell this fragment belongs to
        fragment: Fragment to publish (can be Fragment/CoreFragment model, dict, or str)
    """
    # Handle both Pydantic models and dicts/strings
    if isinstance(fragment, dict):
        fragment_dict = fragment
        # Serialize dict to JSON string for Redis
        fragment_json = json.dumps(fragment_dict, default=str)
    elif isinstance(fragment, str):
        # Handle string fragments (for backward compatibility with Cell.fragments)
        fragment_dict = {"content": fragment, "type": "info"}
        fragment_json = json.dumps(fragment_dict)
    else:
        # Pydantic model (Fragment or CoreFragment)
        fragment_dict = fragment.model_dump()
        fragment_json = fragment.model_dump_json()

    # Always publish to event bus for event-based SSE fallback
    try:
        publish_fragment_added_sync(cell_id, fragment_dict)
        logger.debug("Published fragment to event bus for cell: %s", cell_id)
    except Exception as e:
        logger.error("Error publishing fragment to event bus for cell %s: %s", cell_id, e, exc_info=True)

    # Also publish to Redis if available
    if redis_client:
        try:
            channel = f"cell:{cell_id}:fragmentos"
            redis_client.publish(channel, fragment_json)
            logger.debug("Published fragment to Redis channel: %s", channel)
        except Exception as e:
            logger.error("Error publishing fragment to Redis for cell %s: %s", cell_id, e, exc_info=True)


def publish_pipeline_fragments(item: PipelineItem, since_fragment_id: Optional[str] = None) -> None:
    """
    Publish all new fragments from a PipelineItem to Redis and event bus.

    Args:
        item: PipelineItem containing fragments
        since_fragment_id: Only publish fragments after this ID (exclusive)
    """
    fragments_to_publish = item.get_fragments_since(since_fragment_id)
    for fragment in fragments_to_publish:
        publish_fragment_to_redis(item.cell_id, fragment)
