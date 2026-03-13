"""
Configuration models for system configuration.

Models for OAuth and other system configuration settings.
"""

from typing import Optional

from pydantic import BaseModel, Field


class OAuthConfiguration(BaseModel):
    """OAuth2 Google configuration."""

    googleClientId: Optional[str] = Field(None, description="Google Client ID")
    googleClientSecret: Optional[str] = Field(None, description="Google Client Secret")
    authEnabled: bool = Field(
        default=False, description="Whether authentication is enabled"
    )


class UpdateOAuthConfigRequest(BaseModel):
    """Request to update OAuth configuration."""

    googleClientId: Optional[str] = Field(None, description="Google Client ID")
    googleClientSecret: Optional[str] = Field(None, description="Google Client Secret")
