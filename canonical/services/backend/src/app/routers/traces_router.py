"""
Traces API Router - Retrieve and analyze conversation trace data.

This router provides endpoints for:
- Retrieving trace data by conversation ID
- Listing recent traces for the current user
- Exporting trace data

All endpoints require authentication and enforce user access control.
Technical naming: All functions and variables in English.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import get_current_user_required
from ..database import db
from ..models import User
from ..models.content import Cell

logger = logging.getLogger(__name__)

# Create traces router
traces_router = APIRouter(prefix="/traces", tags=["Conversation Traces"])


@traces_router.get("/conversation/{conversation_id}")
async def get_trace_by_conversation_id(
    conversation_id: str, current_user: User = Depends(get_current_user_required)
) -> Dict[str, Any]:
    """
    Retrieve trace data for a specific conversation.

    Returns the trace cell with all recorded fragments, including:
    - Trace metadata (conversation ID, session ID, user message, target LLM)
    - All captured fragments from pipeline stages
    - Creation timestamp

    Args:
        conversation_id: Unique identifier for the conversation
        current_user: Authenticated user making the request

    Returns:
        Dictionary containing trace data with fragments

    Raises:
        HTTPException: 404 if trace not found, 403 if unauthorized

    Example response:
    ```json
    {
        "trace_id": "cell_abc123",
        "conversation_id": "conv_xyz789",
        "session_id": "sess_456",
        "user_message": "How do I create a cell?",
        "target_llm": "openai",
        "created_at": "2025-11-18T10:00:00",
        "fragments_count": 8,
        "fragments": [...]
    }
    ```
    """
    try:
        # Find trace cell by conversation_id in initial_data
        # Since we need to scan initial_data, we retrieve all trace cells
        try:
            trace_cells = await db.find_many(
                "cells", current_user=current_user, model_class=Cell
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        matching_trace = None
        for cell in trace_cells:
            # Check if this is a trace cell with matching conversation_id
            if (
                cell.notebook_item_type_id == "conversation-trace-item"
                and cell.initial_data.get("conversation_id") == conversation_id
            ):
                matching_trace = cell
                break

        if not matching_trace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No trace found for conversation: {conversation_id}",
            )

        # Verify user has access (either owner or admin)
        # For now, users can only access their own traces
        if matching_trace.assignee_id != current_user.id:
            # TODO: Add admin role check here when role system is implemented
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this trace",
            )

        # Return trace data
        return {
            "trace_id": matching_trace.id,
            "conversation_id": conversation_id,
            "session_id": matching_trace.initial_data.get("session_id"),
            "user_message": matching_trace.initial_data.get("user_message"),
            "target_llm": matching_trace.initial_data.get("target_llm"),
            "created_at": (
                matching_trace.created_at.isoformat()
                if hasattr(matching_trace.created_at, "isoformat")
                else str(matching_trace.created_at)
            ),
            "fragments_count": len(matching_trace.fragments),
            "fragments": matching_trace.fragments,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving trace for conversation %s: %s", conversation_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving trace data",
        )


@traces_router.get("/recent")
async def get_recent_traces(
    limit: int = Query(
        10, ge=1, le=100, description="Maximum number of traces to return"
    ),
    offset: int = Query(0, ge=0, description="Number of traces to skip for pagination"),
    current_user: User = Depends(get_current_user_required),
) -> Dict[str, Any]:
    """
    Retrieve recent trace cells for the current user.

    Returns a paginated list of trace summaries (without full fragment data).
    Useful for listing conversations that have been traced.

    Args:
        limit: Maximum number of traces to return (1-100, default: 10)
        offset: Number of traces to skip for pagination (default: 0)
        current_user: Authenticated user making the request

    Returns:
        Dictionary with trace count and list of trace summaries

    Example response:
    ```json
    {
        "count": 25,
        "limit": 10,
        "offset": 0,
        "traces": [
            {
                "trace_id": "cell_abc123",
                "conversation_id": "conv_xyz789",
                "session_id": "sess_456",
                "user_message": "How do I create a cell?",
                "target_llm": "openai",
                "created_at": "2025-11-18T10:00:00",
                "fragments_count": 8
            },
            ...
        ]
    }
    ```
    """
    try:
        # Get all trace cells for user
        try:
            all_cells = await db.find_many(
                "cells", current_user=current_user, model_class=Cell
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        # Filter to only trace cells owned by current user
        user_traces = [
            cell
            for cell in all_cells
            if (
                cell.assignee_id == current_user.id
                and cell.notebook_item_type_id == "conversation-trace-item"
            )
        ]

        # Sort by created_at descending (most recent first)
        user_traces.sort(
            key=lambda c: c.created_at if hasattr(c, "created_at") else "", reverse=True
        )

        # Get total count before pagination
        total_count = len(user_traces)

        # Apply pagination
        paginated_traces = user_traces[offset : offset + limit]

        # Build trace summaries (without full fragment data for performance)
        trace_summaries = []
        for trace in paginated_traces:
            # Truncate user message to 100 chars for summary
            user_msg = trace.initial_data.get("user_message", "")
            if len(user_msg) > 100:
                user_msg = user_msg[:100] + "..."

            trace_summaries.append(
                {
                    "trace_id": trace.id,
                    "conversation_id": trace.initial_data.get("conversation_id"),
                    "session_id": trace.initial_data.get("session_id"),
                    "user_message": user_msg,
                    "target_llm": trace.initial_data.get("target_llm"),
                    "created_at": (
                        trace.created_at.isoformat()
                        if hasattr(trace.created_at, "isoformat")
                        else str(trace.created_at)
                    ),
                    "fragments_count": len(trace.fragments),
                }
            )

        logger.info(
            "Retrieved %s traces for user %s (total: %s, offset: %s, limit: %s)",
            len(trace_summaries), current_user.id, total_count, offset, limit
        )

        return {
            "count": total_count,
            "limit": limit,
            "offset": offset,
            "traces": trace_summaries,
        }

    except Exception as e:
        logger.error("Error retrieving recent traces: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving recent traces",
        )
