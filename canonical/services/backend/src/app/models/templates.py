"""
Template and Workflow models for canonical artifacts.

Models for managing template blueprints and workflow definitions used
in the ScareVerse canonical data system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .base import generate_uuid


class TemplateStatus(str, Enum):
    """
    Template status enumeration.

    Defines the lifecycle status of a template:
    - DRAFT: Template is being developed
    - PUBLISHED: Template is available for use
    - ARCHIVED: Template is no longer active but preserved for reference
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class TemplateVisibility(str, Enum):
    """
    Template visibility enumeration.

    Controls who can view and use the template:
    - PUBLIC: Available to all users
    - PRIVATE: Only available to owner
    - TEAM: Available to team members
    """

    PUBLIC = "public"
    PRIVATE = "private"
    TEAM = "team"


class Template(BaseModel):
    """
    Template model for reusable artifact blueprints.

    Templates define reusable patterns and configurations for creating
    notebook items, cells, books, or other artifacts. They serve as
    blueprints that can be instantiated multiple times with different
    parameters.

    Examples:
    - Cell type templates (ingestion, transformation, visualization)
    - Book templates (project structures, workflows)
    - Configuration templates (common setups)
    """

    id: str = Field(
        default_factory=generate_uuid, description="Unique template identifier"
    )
    name: str = Field(..., description="Template display name")
    description: Optional[str] = Field(
        None, description="Template description explaining its purpose and usage"
    )
    kind: Optional[str] = Field(
        None,
        description="Template type/category (e.g., 'cell', 'book', 'workflow', 'config')",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Array of tag strings for categorization and search",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata object (level, category, difficulty, etc.)",
    )
    status: TemplateStatus = Field(
        default=TemplateStatus.DRAFT,
        description="Template status (draft, published, archived)",
    )
    owner: str = Field(..., description="User ID of template owner/creator")
    visibility: TemplateVisibility = Field(
        default=TemplateVisibility.PRIVATE,
        description="Template visibility (public, private, team)",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when template was created",
    )
    updated_at: Optional[datetime] = Field(
        None, description="UTC timestamp of last template update"
    )


class WorkflowStatus(str, Enum):
    """
    Workflow status enumeration.

    Defines the operational status of a workflow:
    - ACTIVE: Workflow is operational and can be executed
    - INACTIVE: Workflow is paused/disabled
    - DRAFT: Workflow is being developed/tested
    """

    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


class Workflow(BaseModel):
    """
    Workflow model for defining execution sequences.

    Workflows define ordered sequences of steps/tasks that orchestrate
    the execution of cells, books, or other operations. They support
    complex automation scenarios and data processing pipelines.

    Examples:
    - Data ingestion workflows
    - Model training pipelines
    - Multi-stage transformations
    - Automated testing sequences
    """

    id: str = Field(
        default_factory=generate_uuid, description="Unique workflow identifier"
    )
    name: str = Field(..., description="Workflow display name")
    description: Optional[str] = Field(
        None, description="Workflow description explaining its purpose and behavior"
    )
    steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Array of workflow step objects. Each step defines an action, "
            "dependencies, inputs, and outputs. Steps are executed in order."
        ),
    )
    status: WorkflowStatus = Field(
        default=WorkflowStatus.DRAFT,
        description="Workflow operational status (active, inactive, draft)",
    )
    owner: str = Field(..., description="User ID of workflow owner/creator")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when workflow was created",
    )
    updated_at: Optional[datetime] = Field(
        None, description="UTC timestamp of last workflow update"
    )


# Request models for Template operations
class CreateTemplateRequest(BaseModel):
    """Request to create a new template."""

    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    kind: Optional[str] = Field(None, description="Template type/category")
    tags: List[str] = Field(default_factory=list, description="Template tags")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Template metadata"
    )
    status: TemplateStatus = Field(
        default=TemplateStatus.DRAFT, description="Template status"
    )
    owner: str = Field(..., description="Owner user ID")
    visibility: TemplateVisibility = Field(
        default=TemplateVisibility.PRIVATE, description="Template visibility"
    )


class UpdateTemplateRequest(BaseModel):
    """Request to update an existing template."""

    name: Optional[str] = Field(None, description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    kind: Optional[str] = Field(None, description="Template type/category")
    tags: Optional[List[str]] = Field(None, description="Template tags")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Template metadata")
    status: Optional[TemplateStatus] = Field(None, description="Template status")
    visibility: Optional[TemplateVisibility] = Field(
        None, description="Template visibility"
    )


# Request models for Workflow operations
class CreateWorkflowRequest(BaseModel):
    """Request to create a new workflow."""

    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    steps: List[Dict[str, Any]] = Field(
        default_factory=list, description="Workflow steps"
    )
    status: WorkflowStatus = Field(
        default=WorkflowStatus.DRAFT, description="Workflow status"
    )
    owner: str = Field(..., description="Owner user ID")


class UpdateWorkflowRequest(BaseModel):
    """Request to update an existing workflow."""

    name: Optional[str] = Field(None, description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    steps: Optional[List[Dict[str, Any]]] = Field(None, description="Workflow steps")
    status: Optional[WorkflowStatus] = Field(None, description="Workflow status")
