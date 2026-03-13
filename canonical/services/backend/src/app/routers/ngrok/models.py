"""
Pydantic models for Ngrok Share API.

Defines request models for:
- Starting file shares
- Adding files to active shares
- Removing files from active shares
"""

from typing import List

from pydantic import BaseModel, Field


class ShareStartRequest(BaseModel):
    """Model for starting file share."""

    files: List[str] = Field(
        ..., description="List of file/folder paths to share (relative)"
    )

    class Config:
        json_schema_extra = {
            "example": {"files": ["backend/app/main.py", "docs/README.md"]}
        }


class ShareAddRequest(BaseModel):
    """Model for adding files to active share."""

    files: List[str] = Field(
        ..., description="List of file/folder paths to add (relative)"
    )

    class Config:
        json_schema_extra = {"example": {"files": ["backend/app/models.py"]}}


class ShareRemoveRequest(BaseModel):
    """Model for removing files from active share."""

    files: List[str] = Field(
        ..., description="List of file/folder paths to remove (relative)"
    )

    class Config:
        json_schema_extra = {"example": {"files": ["backend/app/main.py"]}}
