"""
Trace Export Utilities - Export and analyze conversation traces.

This module provides utilities for:
- Exporting trace data to JSON format
- Summarizing trace stages and metrics
- Analyzing trace fragments

Technical naming: All functions and variables in English.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def export_trace_to_json(
    trace_cell: Any, pretty: bool = True, include_metadata: bool = True
) -> str:
    """
    Export a trace cell to JSON format.

    Converts a trace cell (Cell instance) to a JSON string with all
    trace data including fragments, metadata, and timestamps.

    Args:
        trace_cell: Cell instance containing trace data
        pretty: Whether to pretty-print JSON with indentation (default: True)
        include_metadata: Whether to include full metadata (default: True)

    Returns:
        JSON string of trace data

    Example:
        >>> from app.services.conversation_trace_service import get_conversation_trace_service
        >>> service = get_conversation_trace_service()
        >>> trace_cell = # ... retrieve trace cell
        >>> json_str = export_trace_to_json(trace_cell, pretty=True)
        >>> print(json_str)
    """
    try:
        # Extract basic trace information
        trace_data = {
            "trace_id": trace_cell.id,
            "conversation_id": trace_cell.initial_data.get("conversation_id"),
            "session_id": trace_cell.initial_data.get("session_id"),
            "user_message": trace_cell.initial_data.get("user_message"),
            "target_llm": trace_cell.initial_data.get("target_llm"),
            "tracing_enabled": trace_cell.initial_data.get("tracing_enabled", True),
        }

        # Add timestamps
        if hasattr(trace_cell, "dataCriacao"):
            created_at = trace_cell.dataCriacao
            if isinstance(created_at, datetime):
                trace_data["created_at"] = created_at.isoformat()
            else:
                trace_data["created_at"] = str(created_at)
        else:
            trace_data["created_at"] = trace_cell.initial_data.get("created_at")

        # Add fragments
        trace_data["fragments"] = trace_cell.fragments
        trace_data["fragments_count"] = len(trace_cell.fragments)

        # Add optional metadata
        if include_metadata:
            trace_data["metadata"] = {
                "assignee_id": trace_cell.assignee_id,
                "notebook_item_type_id": trace_cell.notebook_item_type_id,
                "origem_livro_id": getattr(trace_cell, "origemLivroId", None),
                "estado": getattr(trace_cell, "estado", None),
            }

        # Serialize to JSON
        if pretty:
            return json.dumps(trace_data, indent=2, ensure_ascii=False)
        return json.dumps(trace_data, ensure_ascii=False)

    except Exception as e:
        logger.error("Error exporting trace to JSON: %s", e)
        raise ValueError(f"Failed to export trace: {str(e)}") from e


def summarize_trace_stages(trace_cell: Any) -> Dict[str, Any]:
    """
    Generate a summary of stages captured in a trace.

    Analyzes fragments to provide insights about which pipeline stages
    were captured, their timing, and frequency.

    Args:
        trace_cell: Cell instance containing trace data

    Returns:
        Dictionary with stage summary including:
        - total_fragments: Total number of fragments
        - stages_captured: List of stage names
        - stage_details: Dict with per-stage statistics
        - duration_ms: Total trace duration if timestamps available

    Example:
        >>> summary = summarize_trace_stages(trace_cell)
        >>> print(f"Captured {summary['total_fragments']} fragments")
        >>> print(f"Stages: {', '.join(summary['stages_captured'])}")
    """
    try:
        stages = {}
        first_timestamp = None
        last_timestamp = None

        for fragment in trace_cell.fragments:
            stage = fragment.get("stage", "unknown")
            timestamp_str = fragment.get("timestamp")

            # Parse timestamp
            try:
                if timestamp_str:
                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )

                    # Track first and last timestamps
                    if first_timestamp is None or timestamp < first_timestamp:
                        first_timestamp = timestamp
                    if last_timestamp is None or timestamp > last_timestamp:
                        last_timestamp = timestamp
                else:
                    timestamp = None
            except (ValueError, AttributeError):
                timestamp = None

            # Initialize or update stage stats
            if stage not in stages:
                stages[stage] = {
                    "count": 0,
                    "first_timestamp": timestamp_str,
                    "last_timestamp": timestamp_str,
                }

            stages[stage]["count"] += 1
            stages[stage]["last_timestamp"] = timestamp_str

        # Calculate duration if timestamps available
        duration_ms = None
        if first_timestamp and last_timestamp:
            duration = last_timestamp - first_timestamp
            duration_ms = int(duration.total_seconds() * 1000)

        return {
            "conversation_id": trace_cell.initial_data.get("conversation_id"),
            "total_fragments": len(trace_cell.fragments),
            "stages_captured": list(stages.keys()),
            "stage_count": len(stages),
            "stage_details": stages,
            "duration_ms": duration_ms,
            "first_timestamp": first_timestamp.isoformat() if first_timestamp else None,
            "last_timestamp": last_timestamp.isoformat() if last_timestamp else None,
        }

    except Exception as e:
        logger.error("Error summarizing trace stages: %s", e)
        raise ValueError(f"Failed to summarize trace: {str(e)}") from e


def extract_stage_data(trace_cell: Any, stage_name: str) -> List[Dict[str, Any]]:
    """
    Extract all fragments for a specific stage.

    Useful for analyzing a particular pipeline stage in detail.

    Args:
        trace_cell: Cell instance containing trace data
        stage_name: Name of the stage to extract (e.g., 'rag_retrieval')

    Returns:
        List of fragment data dicts for the specified stage

    Example:
        >>> rag_fragments = extract_stage_data(trace_cell, "rag_retrieval")
        >>> for frag in rag_fragments:
        ...     print(f"Retrieved {frag['data'].get('chunks_retrieved', 0)} chunks")
    """
    try:
        stage_fragments = []

        for fragment in trace_cell.fragments:
            if fragment.get("stage") == stage_name:
                stage_fragments.append(
                    {
                        "timestamp": fragment.get("timestamp"),
                        "conversation_id": fragment.get("conversation_id"),
                        "data": fragment.get("data", {}),
                    }
                )

        return stage_fragments

    except Exception as e:
        logger.error("Error extracting stage data for '%s': %s", stage_name, e)
        return []


def compare_traces(trace_cell_1: Any, trace_cell_2: Any) -> Dict[str, Any]:
    """
    Compare two trace cells to identify differences.

    Useful for A/B testing, debugging, or analyzing different
    conversation flows.

    Args:
        trace_cell_1: First trace cell to compare
        trace_cell_2: Second trace cell to compare

    Returns:
        Dictionary with comparison results including:
        - common_stages: Stages present in both traces
        - unique_to_trace_1: Stages only in first trace
        - unique_to_trace_2: Stages only in second trace
        - fragment_count_diff: Difference in fragment counts

    Example:
        >>> comparison = compare_traces(trace_a, trace_b)
        >>> print(f"Common stages: {comparison['common_stages']}")
    """
    try:
        summary_1 = summarize_trace_stages(trace_cell_1)
        summary_2 = summarize_trace_stages(trace_cell_2)

        stages_1 = set(summary_1["stages_captured"])
        stages_2 = set(summary_2["stages_captured"])

        common_stages = list(stages_1 & stages_2)
        unique_to_1 = list(stages_1 - stages_2)
        unique_to_2 = list(stages_2 - stages_1)

        return {
            "trace_1_id": trace_cell_1.id,
            "trace_2_id": trace_cell_2.id,
            "trace_1_conversation_id": trace_cell_1.initial_data.get("conversation_id"),
            "trace_2_conversation_id": trace_cell_2.initial_data.get("conversation_id"),
            "common_stages": common_stages,
            "unique_to_trace_1": unique_to_1,
            "unique_to_trace_2": unique_to_2,
            "fragment_count_diff": summary_1["total_fragments"]
            - summary_2["total_fragments"],
            "trace_1_fragments": summary_1["total_fragments"],
            "trace_2_fragments": summary_2["total_fragments"],
            "duration_diff_ms": (
                (
                    (summary_1.get("duration_ms", 0) or 0)
                    - (summary_2.get("duration_ms", 0) or 0)
                )
                if summary_1.get("duration_ms") and summary_2.get("duration_ms")
                else None
            ),
        }

    except Exception as e:
        logger.error("Error comparing traces: %s", e)
        raise ValueError(f"Failed to compare traces: {str(e)}") from e
