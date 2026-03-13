"""
MongoDB schema definitions for session persistence.

⚠️  INDEX DEFINITIONS MOVED TO CENTRALHUB ⚠️

Index management is now handled by CentralHub migrations.
SESSIONS_INDEXES below are kept for reference only.

Schema definitions (BookSchema, CellSchema) are still used for
data validation and serialization.

Defines the structure of session data (Books and Cells) stored in MongoDB
for synchronization and persistent state management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FragmentSchema(BaseModel):
    """Schema for a Fragment (execution result)."""

    fragment_id: str = Field(..., description="Unique fragment identifier")
    cell_id: str = Field(..., description="Parent cell identifier")
    fragment_type: str = Field(
        ..., description="Type of fragment (output, error, result, etc.)"
    )
    content: str = Field(..., description="Fragment content")
    mime_type: str = Field(default="text/plain", description="MIME type of content")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp (UTC)"
    )
    sequence: int = Field(..., description="Sequence number within cell")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class CellSchema(BaseModel):
    """Schema for a Cell (execution unit)."""

    cell_id: str = Field(..., description="Unique cell identifier")
    book_id: str = Field(..., description="Parent book identifier")
    title: Optional[str] = Field(None, description="Optional cell title")
    cell_type: str = Field(
        ..., description="Type of cell (code, markdown, prompt, file_reference)"
    )
    content: str = Field(..., description="Cell content")
    state: str = Field(
        ..., description="Cell state (idle, running, completed, failed, cancelled)"
    )
    execution_order: int = Field(..., description="Execution order within book")
    fragments: List[FragmentSchema] = Field(
        default_factory=list, description="Execution fragments"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp (UTC)"
    )
    executed_at: Optional[datetime] = Field(
        None, description="Last execution timestamp (UTC)"
    )
    error: Optional[str] = Field(None, description="Error message if execution failed")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class BookSchema(BaseModel):
    """Schema for a Book (session)."""

    book_id: str = Field(..., description="Unique book identifier")
    title: str = Field(..., description="Book title")
    description: Optional[str] = Field(None, description="Optional description")
    state: str = Field(..., description="Book state (active, archived, deleted)")
    cells: List[CellSchema] = Field(
        default_factory=list, description="Cells within this book"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp (UTC)"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp (UTC)"
    )
    user_id: str = Field(..., description="User ID who owns this book")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    version: int = Field(
        default=1, description="Version number for optimistic concurrency control"
    )

    class Config:
        """Pydantic config."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class SessionMetadataSchema(BaseModel):
    """Minimal metadata about a session for listing/handshake."""

    book_id: str
    title: str
    state: str
    user_id: str
    updated_at: datetime
    version: int


# MongoDB collection names
SESSIONS_COLLECTION = "sessions"
LOGS_COLLECTION = "logs"

# ⚠️  DEPRECATED: Index definitions moved to CentralHub migrations
# These indexes are now managed by centralhub/app/migrations/
# Kept here for reference only - DO NOT USE for schema management
SESSIONS_INDEXES = [
    {
        "keys": [("user_id", 1), ("updated_at", -1)],
        "name": "user_updated_idx",
        "background": True,
    },
    {
        "keys": [("book_id", 1)],
        "name": "book_id_idx",
        "background": True,
    },  # Non-unique: book_id is optional for loading default layout
    {
        "keys": [("state", 1), ("user_id", 1)],
        "name": "state_user_idx",
        "background": True,
    },
]
