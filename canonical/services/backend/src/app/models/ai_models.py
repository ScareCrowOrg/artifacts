"""
AI model configuration models.

Models for managing AI model registrations, configurations, and providers.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .base import AIModelProvider, generate_uuid


class AIModel(BaseModel):
    """AI model registered as artifact."""

    id: str = Field(default_factory=generate_uuid, description="Model UUID")
    name: str = Field(..., description="Model name (e.g., Mistral, Gemini)")
    description: str = Field(..., description="Model description")
    type: str = Field(..., description="Model type (cloud, local, byok, etc)")
    provider: AIModelProvider = Field(
        ..., description="Model provider (openai, gemini, ollama, groq)"
    )
    modelId: str = Field(
        ..., description="Model ID in provider (e.g., mistral, gemini-pro)"
    )
    apiKey: Optional[str] = Field(
        None, description="Model API Key (encrypted in storage, decrypted on read)"
    )
    version: str = Field(default="1.0.0", description="Model version")
    active: bool = Field(
        default=True, description="Whether the model is active/available"
    )
    configuration: Dict[str, Any] = Field(
        default_factory=dict, description="Model-specific configurations"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    createdAt: datetime = Field(
        default_factory=datetime.utcnow, description="Creation date"
    )
    updatedAt: datetime = Field(
        default_factory=datetime.utcnow, description="Update date"
    )


class CreateAIModelRequest(BaseModel):
    """Request to create a new AI model."""

    name: str = Field(..., description="Model name")
    description: str = Field(..., description="Model description")
    type: AIModelProvider = Field(..., description="Model type")
    provider: str = Field(..., description="Model provider")
    modelId: str = Field(..., description="Model ID in provider")
    apiKey: Optional[str] = Field(None, description="Model API Key (will be encrypted)")
    version: str = Field(default="1.0.0", description="Version")
    active: bool = Field(default=True, description="Whether it is active")
    configuration: Dict[str, Any] = Field(
        default_factory=dict, description="Configurations"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata")


class UpdateAIModelRequest(BaseModel):
    """
    Request to update an AI model.

    Note: The 'id' field should not be sent in the body, but will be ignored if present
    (for frontend compatibility). The model ID must be passed only in the endpoint URL:
    PUT /ai-models/{id}/update

    Pydantic v2 ignores extra fields by default, ensuring compatibility.
    """

    name: Optional[str] = Field(None, description="Model name")
    description: Optional[str] = Field(None, description="Model description")
    type: Optional[AIModelProvider] = Field(None, description="Model type")
    provider: Optional[str] = Field(None, description="Model provider")
    modelId: Optional[str] = Field(None, description="Model ID in provider")
    apiKey: Optional[str] = Field(None, description="Model API Key (will be encrypted)")
    version: Optional[str] = Field(None, description="Version")
    active: Optional[bool] = Field(None, description="Whether it is active")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Configurations")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata")
