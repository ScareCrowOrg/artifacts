"""
Core models for Pipeline Execution

This module defines the PipelineItem model which serves as the central artifact
for in-process workflow execution, replacing subprocess-based approaches.

PipelineItem encapsulates:
- Cell context and metadata
- Input/output data
- Execution fragments for traceability
- State management
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Fragment(BaseModel):
    """
    Execution or memory fragment representing a discrete unit of work or context.

    Acts as a digital "notebook entry" capable of recording any type of information
    (free text, JSON objects, operation results, etc.) without data loss or rigid validation.
    Provides traceability and auditability for pipeline execution,
    allowing real-time monitoring and post-execution analysis.
    """

    id: str = Field(
        default_factory=generate_uuid, description="Unique identifier for the fragment"
    )
    type: str = Field(
        ...,
        description="Fragment type (ex: 'narrative', 'memory', 'log', 'error', 'event', 'output', 'debug', 'execution', 'memory', or any custom string)",
    )
    content: Any = Field(
        ...,
        description="Main content of the fragment. Can be free text, JSON object, structured data, etc.",
    )
    result: Optional[Any] = Field(
        None,
        description="Optional field to record the direct result of an operation, can be of any type",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when fragment was created",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the fragment (ex: chunk_id, section, source_agent, severity, step_name)",
    )

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class ExecutionFragment(BaseModel):
    """
    Execution fragment for unified runtime architecture.

    Represents a discrete unit of execution within a NotebookItem (cell or book).
    Supports hierarchical tracing to track which NotebookItem executed a particular step.
    """

    timestamp: str = Field(..., description="ISO 8601 start time")
    duration_ms: Optional[int] = Field(None, description="Duration in milliseconds")
    step: str = Field(
        ..., description="Step name (e.g., 'discovery', 'planning', 'execute')"
    )
    status: Literal["running", "success", "failed", "waiting_approval", "skipped"] = (
        Field(..., description="Status of this specific step")
    )
    input: Optional[Any] = Field(
        None, description="Step input parameters (JSON-serializable)"
    )
    output: Optional[Any] = Field(
        None, description="Step output results (JSON-serializable)"
    )
    error: Optional[str] = Field(None, description="Error message if status='failed'")

    # Hierarchical tracing fields
    executed_by: Optional[str] = Field(
        None, description="ID of child NotebookItem that executed this step"
    )
    parent_fragment_index: Optional[int] = Field(
        None, description="Index of parent fragment (for nested steps within same item)"
    )

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class NotebookItem(BaseModel):
    """
    Base class for all notebook items (books and cells).

    Provides common fields and functionality for organizing and tracking
    work in the ScareVerse notebook system.

    This abstraction enables:
    - Unified identification and ownership tracking
    - Flexible fragment storage for any notebook item
    - Reference management for related files
    - Generic data storage for initialization
    - Unified runtime with 'kind' discriminator (cell vs book)
    """

    # Core identifiers
    id: str = Field(
        default_factory=generate_uuid, description="UUID of the notebook item"
    )
    assignee_id: str = Field(
        ..., description="UUID of the user/agent responsible for this item"
    )

    # Unified runtime discriminator
    kind: Optional[Literal["cell", "book"]] = Field(
        None,
        description="Discriminator field determining runtime behavior (cell or book)",
    )

    # Type identifier (for backward compatibility with existing code)
    notebook_item_type_id: Optional[str] = Field(
        None,
        description="References type.json (e.g., 'png-generator-cell', 'automation-book')",
    )

    # Flexible fragment storage (strings or structured dicts)
    fragments: List[Union[str, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Ordered list of flexible fragments for traceability and 'notebook' functionality. "
        "Supports both simple strings and structured dictionaries.",
    )

    # File references
    refs: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="References to files organized by type (docs, python, js, yaml, attachments)",
    )

    # Initial/generic data
    initial_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Initial data or generic data for the notebook item",
        alias="data",
    )

    # Execution state
    status: Optional[
        Literal["idle", "running", "AWAITING_REVIEW", "success", "failed", "paused"]
    ] = Field(None, description="Current execution status")

    # Outputs from execution
    outputs: Dict[str, Any] = Field(
        default_factory=dict, description="Results from execution (JSON-serializable)"
    )

    # Book-specific fields (only used when kind='book')
    cells: Optional[List[str]] = Field(
        None, description="Array of child NotebookItem IDs (book-specific)"
    )
    execution_mode: Optional[Literal["dag", "script", "hybrid"]] = Field(
        None,
        description="Execution strategy: dag (parallel), script (sequential), hybrid (mixed)",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when item was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="UTC timestamp of last update"
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        populate_by_name=True,  # Allow both field name and alias for deserialization
        by_alias=False,  # Serialize using field names, not aliases
    )

    @model_validator(mode="before")
    @classmethod
    def convert_none_to_defaults(cls, data: Any) -> Any:
        """
        Convert None values to appropriate defaults for fields with default_factory.

        This handles cases where database documents have explicit None values
        instead of missing fields, which would otherwise fail Pydantic validation.
        """
        if isinstance(data, dict):
            # Convert None to empty list for list fields
            if data.get("fragments") is None:
                data["fragments"] = []
            if data.get("cells") is None:
                data["cells"] = None  # Keep as None since it's Optional

            # Convert None to empty dict for dict fields
            if data.get("refs") is None:
                data["refs"] = {}
            if data.get("initial_data") is None:
                data["initial_data"] = {}
            if data.get("outputs") is None:
                data["outputs"] = {}

        return data


class PipelineItem(BaseModel):
    """
    Central artifact for pipeline workflow execution.

    PipelineItem is a separate execution entity that COMPOSES (not inherits) a NotebookItem.
    This separation ensures that the pure data model (NotebookItem) remains clean while
    execution state and context are managed independently.

    PipelineItem represents an execution context/instance of a NotebookItem (usually a Cell).
    It serves as the primary data structure passed between workflow nodes and scripts,
    encapsulating all execution context, data, and execution history.

    Key Design Principles:
    - Composition over Inheritance: Contains a NotebookItem reference, doesn't inherit from it
    - Separation of Concerns: Execution state separate from data model
    - No Metadata Duplication: References the original NotebookItem for all data fields

    This model enables:
    - Type-safe data passing between workflow components
    - Execution traceability via its own fragments
    - In-process execution without subprocess overhead
    - Seamless serialization for persistence and event streaming
    - Clear separation of cell definition (Cell) from execution context (PipelineItem)
    """

    # Core execution identifier
    id: str = Field(
        default_factory=generate_uuid, description="UUID of this execution instance"
    )

    # Reference to the NotebookItem being executed
    notebook_item_id: str = Field(
        ..., description="ID of the NotebookItem (Cell or other) being executed"
    )

    # CRITICAL: Direct reference to the NotebookItem instance being executed
    notebook_item_data: NotebookItem = Field(
        ..., description="The actual NotebookItem (Cell or Livro) being executed"
    )

    # Pipeline-specific identifiers (maintained for backward compatibility)
    cell_id: str = Field(
        ...,
        description="ID of the source cell being processed (usually same as notebook_item_id)",
    )
    cell_type_id: str = Field(..., description="ID of the cell type definition")

    # Assignee tracking (from the NotebookItem being executed)
    assignee_id: str = Field(
        ..., description="UUID of the user/agent responsible for this execution"
    )

    # Execution-specific fragments (NOT the NotebookItem's fragments)
    fragments: List[Union[str, Dict[str, Any]]] = Field(
        default_factory=list,
        description="Execution-specific fragments for this pipeline run",
    )

    # Execution context
    status: Literal["pending", "running", "completed", "error"] = Field(
        default="pending", description="Current execution status"
    )

    # Pipeline-specific data payload (input/output for execution)
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input/output data dictionary for workflow processing",
    )

    # Optional error information
    error: Optional[str] = Field(None, description="Error message if execution failed")

    # Agent context (optional)
    agent_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context about the agent executing this pipeline",
    )

    # Timestamps for execution tracking
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this execution instance was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update time for this execution",
    )

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    def add_fragment(
        self,
        type: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
        execution_fragment: Optional["ExecutionFragment"] = None,
    ) -> Union[Fragment, Dict[str, Any]]:
        """
        Add a new fragment to the pipeline item.

        Supports two fragment types:
        - Fragment (generic): For any data, logging, metadata without execution semantics
        - ExecutionFragment (specific): For execution steps with hierarchical tracing via executed_by

        Args:
            type: Fragment type (any string for categorization, e.g., 'narrative', 'memory', 'execution', 'log', etc.)
            content: Main content (can be text, JSON object, structured data, etc.)
            metadata: Additional metadata (optional)
            result: Optional result of an operation (optional)
            execution_fragment: Optional ExecutionFragment for hierarchical tracing. If provided, this will be
                                stored instead of creating a generic Fragment. Use this when tracking execution
                                steps with the executed_by field for hierarchy tracking.

        Returns:
            The created Fragment or ExecutionFragment as dict
        """
        if execution_fragment:
            # Use ExecutionFragment for hierarchical tracing
            self.fragments.append(execution_fragment.model_dump())
            self.updated_at = datetime.utcnow()
            return execution_fragment
        else:
            # Use Fragment for generic data (default behavior)
            fragment = Fragment(
                type=type, content=content, result=result, metadata=metadata or {}
            )
            # Store as dict to be compatible with Union[str, Dict] type
            self.fragments.append(fragment.model_dump())
            self.updated_at = datetime.utcnow()
            return fragment

    def update_status(
        self, new_status: Literal["pending", "running", "completed", "error"]
    ) -> None:
        """
        Update the pipeline item status.

        Args:
            new_status: New status value
        """
        self.status = new_status
        self.updated_at = datetime.utcnow()

    def set_error(self, error_message: str) -> None:
        """
        Mark the pipeline item as errored.

        Args:
            error_message: Description of the error
        """
        self.status = "error"
        self.error = error_message
        self.updated_at = datetime.utcnow()

        # Add error fragment
        self.add_fragment(
            type="execution",
            content=f"Error: {error_message}",
            metadata={"error": True},
        )

    def merge_data(self, new_data: Dict[str, Any]) -> None:
        """
        Merge new data into the existing data dictionary.

        Args:
            new_data: Dictionary to merge into self.data
        """
        self.data.update(new_data)
        self.updated_at = datetime.utcnow()

    def get_fragments_since(
        self, since_id: Optional[str] = None
    ) -> List[Union[str, Dict[str, Any]]]:
        """
        Get fragments created after a specific fragment ID.

        Args:
            since_id: Fragment ID to start from (exclusive). If None, returns all.

        Returns:
            List of fragments
        """
        if since_id is None:
            return self.fragments

        # Find the index of the fragment with since_id
        for idx, fragment in enumerate(self.fragments):
            # Handle both dict and Fragmento types
            frag_id = (
                fragment.get("id")
                if isinstance(fragment, dict)
                else (fragment.id if hasattr(fragment, "id") else None)
            )
            if frag_id == since_id:
                # Return all fragments after this one
                return self.fragments[idx + 1 :]

        # If since_id not found, return all fragments
        return self.fragments
