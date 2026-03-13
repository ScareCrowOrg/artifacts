"""
Artifact models for canonical and instantiated artifacts.

Models for managing artifact templates and runtime artifact instances.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .base import ArtifactState, generate_uuid
from .content import Scripts


class Metadata(BaseModel):
    """Metadata for a canonical artifact."""

    author: str = Field(
        default="Equipe ScareVerse", description="Author of the artifact"
    )
    license: str = Field(default="MIT", description="License of the artifact")
    type: str = Field(..., description="Type of artifact (cell, book, etc)")
    language: Optional[str] = Field(None, description="Primary language")


class ArtifactContent(BaseModel):
    """Content of a canonical artifact."""

    markup: Optional[str] = Field(None, description="Markdown or HTML")
    scripts: Scripts = Field(default_factory=Scripts, description="Artifact scripts")
    workflows: Optional[str] = Field(None, description="Workflow YAML")


class CanonicalArtifact(BaseModel):
    """Canonical artifact model (base template)."""

    id: str = Field(
        default_factory=generate_uuid, description="UUID of the canonical artifact"
    )
    name: str = Field(..., description="Name of the artifact")
    description: str = Field(..., description="Detailed description")
    version: str = Field(default="1.0.0", description="Version of the artifact")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Metadata = Field(..., description="Artifact metadata")
    content: ArtifactContent = Field(..., description="Artifact content")


class ExecutionResult(BaseModel):
    """Result of artifact execution."""

    output: Optional[str] = Field(None, description="Execution output")
    logs: List[str] = Field(default_factory=list, description="Execution logs")


class InstantiatedArtifact(BaseModel):
    """Instantiated artifact model (runtime)."""

    id: str = Field(
        default_factory=generate_uuid, description="UUID of the instantiated artifact"
    )
    name: str = Field(..., description="Name of the instance")
    baseId: str = Field(..., description="UUID of the base canonical artifact")
    userId: str = Field(..., description="UUID of the user")
    sessionId: str = Field(..., description="UUID of the session")
    state: ArtifactState = Field(
        default=ArtifactState.PENDING, description="Execution state"
    )
    result: Optional[ExecutionResult] = Field(None, description="Execution result")
    executedAt: Optional[datetime] = Field(None, description="Execution date")
