"""
Agent models for AI agent management.

Models for defining agent types and runtime agent instances.
"""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from .base import generate_uuid


class AgentType(BaseModel):
    """Pydantic model for a canonical AI agent type."""

    id: str = Field(
        default_factory=generate_uuid, description="Unique UUID for the agent type"
    )
    name: str = Field(..., description="Short, human-readable name for the agent type")
    description: str = Field(
        ...,
        description="Detailed description of the purpose and general capabilities of this agent type",
    )
    base_capabilities: List[str] = Field(
        default_factory=list,
        description="List of core functionalities that any agent of this type should possess (e.g., 'generate_text', 'analyze_code')",
    )
    default_persona_traits: Dict[str, Any] = Field(
        default_factory=dict,
        description="Default persona characteristics for agents of this type (e.g., {'concise': True, 'analytical': True})",
    )
    version: str = Field(
        default="1.0.0", description="Version of the agent type definition"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="UTC datetime of creation"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="UTC datetime of last update"
    )


class Agent(BaseModel):
    """Pydantic model for a runtime AI agent instance."""

    id: str = Field(
        default_factory=generate_uuid, description="Unique UUID for the agent instance"
    )
    name: str = Field(
        ...,
        description="Name of the agent instance (e.g., 'Mistral Document Ingestor')",
    )
    description: str = Field(
        ..., description="Specific description of this agent instance and its purpose"
    )
    agent_type_id: str = Field(
        ..., description="UUID of the canonical agent type to which this agent belongs"
    )
    ia_model_id: str = Field(
        ...,
        description="The 'modelId' from the AIModel that this agent will use (e.g., 'mistral', 'deepseek-coder')",
    )
    persona_definitions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Specific persona characteristics for this agent (e.g., a system_prompt or set of traits)",
    )
    agent_specific_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional operational configurations specific to this agent, complementing or overriding those in AIModel",
    )
    is_active: bool = Field(
        default=True,
        description="Indicates if the agent is active and available for processing",
    )
    version: str = Field(
        default="1.0.0", description="Version of the agent instance definition"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="UTC datetime of creation"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="UTC datetime of last update"
    )
