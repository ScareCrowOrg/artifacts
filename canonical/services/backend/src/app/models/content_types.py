"""
Content and ContentType models for typed asset persistence.

This module implements the Content & ContentTypes layer that provides:
- ContentType: Canonical blueprints (JSON in Git) defining asset schemas
- Content: Typed instances (MongoDB) with versioning and storage references

Key principles:
- Zero-Raw-in-DB: MongoDB stores only metadata and references, not raw bytes
- Typed Assets: All content must conform to a ContentType schema
- Versioning: Immutable content with version tracking and is_latest flag
- Lineage: Optional origin_cell_id for traceability
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from .base import generate_uuid


class StoragePolicy(str, Enum):
    """
    Storage policy for content data.

    Defines where the raw content bytes should be stored:
    - LOCAL: Local filesystem storage (for development/testing)
    - CLOUD: Cloud storage (S3, GCS, etc.)
    - REPO: Repository storage (Git LFS for canonical assets)
    """

    LOCAL = "local"
    CLOUD = "cloud"
    REPO = "repo"


class RenderHints(BaseModel):
    """
    Rendering hints for frontend visualization.

    Provides instructions to Vue.js/Babylon.js on how to render the content:
    - component: Vue component name to use
    - viewport_params: Camera/viewport configuration
    - interaction_mode: User interaction capabilities
    """

    component: Optional[str] = Field(
        None,
        description="Vue component name for rendering (e.g., 'ImageViewer', 'BabylonViewer')",
    )
    viewport_params: Optional[Dict[str, Any]] = Field(
        None, description="Viewport configuration (camera position, lighting, etc.)"
    )
    interaction_mode: Optional[str] = Field(
        None,
        description="User interaction mode (e.g., 'view-only', 'orbit', 'manipulate')",
    )
    additional_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional rendering configuration"
    )


class ContentType(BaseModel):
    """
    ContentType: Canonical blueprint for content assets.

    Defines the contract that Content instances must follow:
    - Identity: Unique id, name, mime_type
    - Expected Fragments: Required metadata keys in Content.fragments
    - Render Hints: Frontend rendering instructions
    - Storage Policy: Where raw data should be stored

    ContentTypes are stored as JSON files in artifacts/canonical/content_types/
    and loaded at runtime to validate Content instances.
    """

    id: str = Field(
        ..., description="Unique identifier (e.g., 'image-png', '3d-glb', 'vector-svg')"
    )
    name: str = Field(
        ..., description="Human-readable name (e.g., 'PNG Image Asset', '3D Model GLB')"
    )
    description: Optional[str] = Field(
        None, description="Detailed description of this content type"
    )
    mime_type: str = Field(
        ...,
        description="MIME type for the content (e.g., 'image/png', 'model/gltf-binary')",
    )
    version: str = Field(default="1.0.0", description="ContentType schema version")

    # Schema definition
    expected_fragments: Union[List[str], Dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Expected metadata keys in Content.fragments. "
            "Can be a list of required keys (simple) or a dict with JSON Schema (advanced)"
        ),
    )

    # Rendering configuration
    render_hints: Optional[RenderHints] = Field(
        None,
        description="Hints for frontend rendering (component, viewport, interactions)",
    )

    # Storage configuration
    storage_policy: StoragePolicy = Field(
        default=StoragePolicy.LOCAL,
        description="Where raw content data should be stored",
    )
    storage_base_path: Optional[str] = Field(
        None,
        description="Base path/bucket for storage (e.g., '/data/content', 's3://bucket/content')",
    )

    # Validation rules
    max_size_bytes: Optional[int] = Field(
        None, description="Maximum allowed file size in bytes"
    )
    allowed_extensions: Optional[List[str]] = Field(
        None, description="Allowed file extensions (e.g., ['.png', '.jpg'])"
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when type was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="UTC timestamp of last update"
    )

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: str) -> str:
        """Ensure mime_type follows the type/subtype format."""
        if "/" not in v:
            raise ValueError(f"Invalid MIME type format: {v}. Expected 'type/subtype'")
        return v


class Content(BaseModel):
    """
    Content: Typed, versioned asset instance.

    Represents a single asset produced by a cell execution:
    - data_ref: URL/Path to raw data (NEVER stores raw bytes in MongoDB)
    - content_type_id: Reference to ContentType for validation
    - version & is_latest: Immutable versioning
    - origin_cell_id: Lineage tracking (optional)
    - fragments: Metadata following ContentType.expected_fragments

    Content instances are immutable. To update, create a new version.
    """

    id: str = Field(
        default_factory=generate_uuid,
        description="Unique identifier for this content instance",
    )

    # Type and ownership
    content_type_id: str = Field(
        ..., description="ID of the ContentType this content conforms to"
    )
    assignee_id: str = Field(
        ..., description="UUID of the user/agent who owns this content"
    )

    # Data reference (CRITICAL: No raw bytes in DB)
    data_ref: str = Field(
        ...,
        description=(
            "Reference to raw data. NEVER store raw bytes here. "
            "Examples: 'file:///data/content/abc123.png', 's3://bucket/content/abc123.glb'"
        ),
    )

    # Versioning (immutable)
    version: int = Field(
        default=1, description="Version number (1, 2, 3, ...). Immutable."
    )
    is_latest: bool = Field(
        default=True, description="Flag indicating if this is the latest version"
    )
    previous_version_id: Optional[str] = Field(
        None, description="ID of the previous version (for version chain)"
    )

    # Lineage tracking
    origin_cell_id: Optional[str] = Field(
        None, description="UUID of the cell that generated this content (optional)"
    )

    # Metadata (must conform to ContentType.expected_fragments)
    fragments: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Metadata for this content. Must include keys defined in "
            "ContentType.expected_fragments. Examples: resolution, poly_count, duration"
        ),
    )

    # File metadata
    filename: Optional[str] = Field(
        None, description="Original filename (if applicable)"
    )
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    checksum: Optional[str] = Field(
        None, description="File checksum (SHA-256) for integrity verification"
    )

    # Additional metadata
    tags: List[str] = Field(
        default_factory=list, description="Tags for categorization and search"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional custom metadata"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when content was created",
    )

    @model_validator(mode="after")
    def validate_no_raw_data_in_fragments(self) -> "Content":
        """
        CRITICAL: Ensure fragments don't contain large raw data.

        This validator prevents storing base64-encoded images, binary blobs,
        or other large data in the fragments field. All raw data must be
        referenced via data_ref.
        """
        for key, value in self.fragments.items():
            if isinstance(value, str) and len(value) > 10000:
                raise ValueError(
                    f"Fragment '{key}' contains suspiciously large string ({len(value)} chars). "
                    "Raw data must be stored via data_ref, not in fragments."
                )

            # Check for base64-encoded data
            if isinstance(value, str) and (
                value.startswith("data:")
                or (
                    len(value) > 100
                    and value.replace("+", "")
                    .replace("/", "")
                    .replace("=", "")
                    .isalnum()
                )
            ):
                raise ValueError(
                    f"Fragment '{key}' appears to contain base64-encoded data. "
                    "Use data_ref instead."
                )

        return self


# Request models for Content operations
class CreateContentRequest(BaseModel):
    """Request to create new content."""

    content_type_id: str = Field(..., description="ContentType ID")
    assignee_id: str = Field(..., description="Owner user UUID")
    data_ref: str = Field(..., description="Reference to raw data (URL/Path)")
    origin_cell_id: Optional[str] = Field(None, description="Source cell UUID")
    fragments: Dict[str, Any] = Field(
        default_factory=dict, description="Content metadata"
    )
    filename: Optional[str] = Field(None, description="Original filename")
    size_bytes: Optional[int] = Field(None, description="File size in bytes")
    checksum: Optional[str] = Field(None, description="File checksum (SHA-256)")
    tags: List[str] = Field(default_factory=list, description="Content tags")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class UpdateContentMetadataRequest(BaseModel):
    """Request to update content metadata (creates new version)."""

    fragments: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")
    tags: Optional[List[str]] = Field(None, description="Updated tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class ContentQueryFilters(BaseModel):
    """Filters for querying content."""

    content_type_id: Optional[str] = Field(None, description="Filter by content type")
    assignee_id: Optional[str] = Field(None, description="Filter by owner")
    origin_cell_id: Optional[str] = Field(None, description="Filter by source cell")
    is_latest: Optional[bool] = Field(None, description="Filter by latest version")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
