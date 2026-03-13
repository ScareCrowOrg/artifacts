"""
Execution tracking models for pipeline execution history.

This module defines DTOs (Data Transfer Objects) for tracking pipeline executions,
which are stored as part of NotebookItem.fragments for traceability.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ExecutionRecord(BaseModel):
    """
    Data Transfer Object representing a single pipeline execution record.

    ExecutionRecord is NOT a persisted entity. It is a DTO used to structure
    execution history data before it is serialized to dict and stored in
    NotebookItem.fragments.

    Each ExecutionRecord represents one execution instance of a NotebookItem
    (typically a Cell), capturing:
    - Execution metadata (pipeline_item_id, status, timestamps)
    - Execution fragments (logs, results, errors from this specific run)
    - Optional snapshot of initial data at execution time

    When persisted, ExecutionRecord is converted to dict with type marker:
    {
        "type": "execution_record",
        "pipeline_item_id": "...",
        "status": "...",
        ...
    }

    This allows filtering execution records from other fragment types in
    NotebookItem.fragments.
    """

    # Execution identifier
    pipeline_item_id: str = Field(
        ..., description="UUID of the PipelineItem execution instance"
    )

    # Execution status
    status: Literal["pending", "running", "completed", "error"] = Field(
        ..., description="Final status of this execution"
    )

    # Execution owner
    assignee_id: str = Field(
        ..., description="UUID of the user/agent who executed this pipeline"
    )

    # Timestamps
    created_at: datetime = Field(..., description="When this execution started")
    updated_at: datetime = Field(
        ..., description="When this execution last updated/completed"
    )

    # Execution-specific fragments
    fragments: List[Union[str, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Execution-specific fragments (logs, outputs, errors) from this run",
    )

    # Type marker for filtering (set as default)
    type: Literal["execution_record"] = Field(
        default="execution_record",
        description="Type marker to identify execution records in NotebookItem.fragments",
    )

    # Optional snapshot of initial data
    initial_data_snapshot: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional snapshot of NotebookItem.initial_data at execution time",
    )

    # Optional error message
    error: Optional[str] = Field(None, description="Error message if execution failed")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
