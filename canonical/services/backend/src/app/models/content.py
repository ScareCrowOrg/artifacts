"""
Content models for cells, books, and related entities.

Models for managing cells (artifacts), cell types, books (notebooks), and fragments.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.models import NotebookItem
from .base import BookType, CellStatus, generate_uuid


class Scripts(BaseModel):
    """Scripts in different languages."""

    python: Optional[str] = Field(None, description="Python code")
    js: Optional[str] = Field(None, description="JavaScript code")


class DiscoveryMetadata(BaseModel):
    """
    Discovery metadata for notebook item types.

    This metadata enables the Discovery System to:
    - Perform semantic search via the describe field
    - Filter cells by labels (tags)
    - Estimate resource requirements and duration
    - Understand cell dependencies and use cases
    """

    labels: List[str] = Field(
        default_factory=list,
        description="Tags for label-based filtering (e.g., ['#3d', '#logic', '#generator'])",
    )
    describe: str = Field(
        ...,
        description=(
            "Detailed description for semantic search (embeddings). "
            "Should clearly explain what the cell does, when to use it, limitations, and performance characteristics."
        ),
    )
    estimated_duration_seconds: Optional[int] = Field(
        None, description="Estimated execution time in seconds for planning purposes"
    )
    required_resources: Optional[List[str]] = Field(
        default_factory=list,
        description="Required resources (e.g., ['gpu', 'high-memory', 'external-api'])",
    )
    dependencies: Optional[List[str]] = Field(
        default_factory=list,
        description="Cell IDs or service names that this cell typically works with or requires",
    )
    tags: Optional[List[str]] = Field(
        default_factory=list, description="Additional tags for categorization"
    )
    use_cases: Optional[List[str]] = Field(
        default_factory=list, description="Common use cases for this cell type"
    )


class NotebookItemType(BaseModel):
    """
    Type definition for notebook items (cells and books).

    NotebookItemType defines the blueprint/schema for notebook items, providing:
    - Default references (workflow_graph, docs, python scripts, etc.)
    - Default initial data for new instances
    - Validation rules and constraints
    - Override policies for instances

    This enables dynamic, type-driven behavior where notebook items inherit
    default execution patterns from their types while allowing instance-specific overrides.
    """

    id: str = Field(
        default_factory=generate_uuid, description="UUID of the notebook item type",
        alias="_id"
    )
    name: str = Field(
        ..., description="Name of the type (e.g., 'Ingestion Cell', 'Issues Book')"
    )
    description: Optional[str] = Field(
        None, description="Description of the type and its purpose"
    )
    kind: Optional[str] = Field(None, description="Type kind (e.g., 'cell', 'book')")
    default_refs: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Default references for this type (e.g., 'workflow_graph': ['path/to/default_workflow.py'])",
    )
    default_initial_data: Optional[Dict[str, Any]] = Field(
        None, description="Default initial data for instances of this type"
    )
    allow_instance_override_refs: Optional[bool] = Field(
        None, description="If True, instances can override default_refs"
    )
    can_render_dynamically: Optional[bool] = Field(
        None,
        description="If True, this cell type can be rendered in DynamicWorkspace (has compatible Vue component)",
    )
    discovery: Optional[DiscoveryMetadata] = Field(
        None,
        description=(
            "Discovery metadata for semantic search and intelligent cell selection. "
            "Optional field - cells without this metadata can still be loaded but won't be discoverable via the Discovery System."
        ),
        alias="_discovery",
    )
    created_at: Optional[datetime] = Field(
        None, description="UTC timestamp when type was created"
    )
    updated_at: Optional[datetime] = Field(
        None, description="UTC timestamp of last update"
    )

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}, populate_by_name=True
    )


# TipoCelula has been removed. Use NotebookItemType instead, which is the unified abstraction for both cells and books.


# Type alias for fragments
Fragment = str


class Cell(NotebookItem):
    """Cell instance model.

    Inherits from NotebookItem, providing:
    - Base notebook functionality (id, assignee_id, fragments, refs, initial_data, created_at, updated_at)
    - Cell-specific properties (notebook_item_type_id, source_book_id, status, version, category)

    Fragment Flexibility (Mixed Types):
    The 'fragments' field (inherited from NotebookItem) is designed as a "wildcard" capable of storing any relevant
    information in flexible formats:
    - str: Simple strings for memories, short narratives, quick notes
    - Dict[str, Any]: Structured data with keys like 'type', 'content', 'result', etc.

    This flexibility aligns with the "Everything is an Artifact" principle, allowing
    capture of the full spectrum of relevant information without data loss or rigid validation.

    Note: For pipeline execution context, use PipelineItem which references this Cell via notebook_item_id.
    """

    # Cell-specific fields
    notebook_item_type_id: str = Field(
        ..., description="ID of the NotebookItemType this cell belongs to"
    )
    source_book_id: Optional[str] = Field(None, description="UUID of the source book")
    status: CellStatus = Field(
        default=CellStatus.PENDING, description="Cell execution status"
    )
    version: str = Field(default="1.0.0", description="Cell version")
    category: Optional[str] = Field(
        None,
        description="Cell category (e.g., 'ephemeral' for non-persistent cells, 'persistent' for saved cells)",
    )

    # Semantic fields for better user presentation
    title: Optional[str] = Field(None, description="Human-readable title for the cell")
    content: Optional[str] = Field(
        None,
        description="Main content/description of the cell (text, markdown, code, etc.)",
    )

    @model_validator(mode="before")
    @classmethod
    def handle_semantic_field_migration(cls, data):
        """Migrate semantic fields and category from initial_data if not present at top level."""
        if isinstance(data, dict):
            # Remove pipeline-specific fields if they exist (should not be in Cell)
            pipeline_fields = ["cell_id", "cell_type_id", "error", "agent_data"]
            for field in pipeline_fields:
                data.pop(field, None)

            # Migrate semantic fields from initial_data if not present at top level
            # This supports lazy migration of existing cells
            initial_data = data.get("initial_data", {})
            if isinstance(initial_data, dict):
                # Migrate title
                if "title" not in data and "title" in initial_data:
                    data["title"] = initial_data["title"]

                # Migrate content
                if "content" not in data and "content" in initial_data:
                    data["content"] = initial_data["content"]

                # Migrate category from initial_data to core field
                if "category" not in data and "category" in initial_data:
                    data["category"] = initial_data["category"]
                    # Remove from initial_data to avoid duplication
                    initial_data.pop("category", None)

        return data


class Book(NotebookItem):
    """Book model (collection of cells).

    Inherits from NotebookItem, providing base notebook functionality while
    adding book-specific organizational and metadata capabilities.
    """

    notebook_item_type_id: Optional[str] = Field(
        None,
        description="ID of the NotebookItemType this book belongs to (optional for books)",
    )
    name: str = Field(
        ..., description="Human-readable name for the book (e.g., 'issues-queue')"
    )
    description: str = Field(
        ..., description="Detailed description of the book's purpose"
    )
    type: BookType = Field(..., description="Book type (VOLATILE or MASTER)")
    source: Optional[str] = Field(None, description="UUID of the source cell")
    purpose: str = Field(..., description="Purpose/objective of the book")
    children: List[str] = Field(
        default_factory=list, description="UUIDs of child books"
    )
    cells: List[str] = Field(
        default_factory=list, description="UUIDs of cells in this book"
    )

    # Flags for book classification
    is_unclassified_master_template: bool = Field(
        default=False,
        description="If True, this book is the ad-hoc master blueprint for new user books.",
    )
    is_canonical_system_book: bool = Field(
        default=False,
        description="If True, this book is a canonical system book (e.g., issues-queue) and doesn't appear in user sidebar.",
    )

    @model_validator(mode="before")
    @classmethod
    def convert_none_booleans_to_defaults(cls, data: Any) -> Any:
        """Convert None boolean fields to their default values."""
        if isinstance(data, dict):
            if data.get("is_unclassified_master_template") is None:
                data["is_unclassified_master_template"] = False
            if data.get("is_canonical_system_book") is None:
                data["is_canonical_system_book"] = False
        return data

    @model_validator(mode="after")
    def check_cells_for_canonical(self) -> "Book":
        """
        Validates that canonical books cannot have cells manipulated directly.

        Canonical books should only be references - cells should reference
        the book through the source_book_id field, not through the cells array.
        """
        # If canonical and trying to set/modify cells array with non-empty value
        if self.is_canonical_system_book and self.cells:
            raise ValueError(
                "Canonical system book cannot have cells array instantiated or modified. "
                "Use the source_book_id field in cells to reference this book."
            )
        return self


# Request models for content operations
class CreateCellRequest(BaseModel):
    """Request to create a new cell."""

    assignee_id: str = Field(..., description="User UUID")
    notebook_item_type_id: str = Field(..., description="NotebookItemType UUID")
    source_book_id: Optional[str] = Field(None, description="Source book UUID")
    initial_data: Optional[Dict[str, Any]] = Field(
        None, description="Initial data for the cell"
    )
    refs: Optional[Dict[str, List[str]]] = Field(
        None, description="Override refs for this cell instance"
    )

    # Semantic fields
    title: Optional[str] = Field(None, description="Human-readable title for the cell")
    content: Optional[str] = Field(
        None, description="Main content/description of the cell"
    )


class CreateBookRequest(BaseModel):
    """Request to create a new book."""

    name: str = Field(..., description="Book name")
    description: str = Field(..., description="Book description")
    purpose: str = Field(..., description="Purpose/objective of the book")
    assignee_id: Optional[str] = Field(
        None, description="Responsible user UUID (if not provided, use current user)"
    )
    notebook_item_type_id: Optional[str] = Field(
        None, description="NotebookItemType UUID (optional for books)"
    )
    refs: Optional[Dict[str, List[str]]] = Field(
        None, description="Override refs for this book instance"
    )


class AddCellToBookRequest(BaseModel):
    """Request to add a cell to a book."""

    cell_id: str = Field(..., description="UUID of the cell to add")


class ExecuteCellRequest(BaseModel):
    """Request to execute a cell."""

    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Execution parameters"
    )


class ExecuteEphemeralCellRequest(BaseModel):
    """Request to execute an ephemeral cell (non-persistent)."""

    cell_type: str = Field(..., description="Cell type ID to execute")
    input_data: Dict[str, Any] = Field(
        default_factory=dict, description="Input data for cell execution"
    )


class UpdateCellRequest(BaseModel):
    """Request to update a cell."""

    initial_data: Optional[Dict[str, Any]] = Field(
        None, description="New initial cell data"
    )
    status: Optional[CellStatus] = Field(None, description="New status")
    fragments: Optional[List[Union[str, Dict[str, Any]]]] = Field(
        None,
        description="New fragments - accepts simple strings or structured dictionaries",
    )

    # Semantic fields
    title: Optional[str] = Field(None, description="New title for the cell")
    content: Optional[str] = Field(None, description="New content for the cell")

    # Additional fields for complete cell update (Issue #1206)
    # metadata: UI state, tags, categories, user annotations, etc.
    # history: Execution records, version changes, user actions, audit trail
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Cell metadata (UI state, tags, categories, custom annotations)",
    )
    history: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Cell history (execution records, version changes, audit trail)",
    )


class CellRunRequest(BaseModel):
    """Request to execute complete cell lifecycle atomically."""

    cell_id: str = Field(..., description="Cell ID to execute")
    lifecycle: Dict[str, Any] = Field(
        ...,
        description="Lifecycle configuration with setup, execute, save, and show steps",
    )
