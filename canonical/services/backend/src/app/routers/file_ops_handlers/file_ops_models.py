"""
Pydantic Models for File Operations Router

Request validation models for file operation endpoints.
"""

from pydantic import BaseModel, Field


class SaveFileRequest(BaseModel):
    """Model for save file request."""

    folder: str = Field(default="", description="Relative folder path")
    filename: str = Field(..., description="Filename with extension")
    content: str = Field(..., description="File content as plain text")

    class Config:
        json_schema_extra = {
            "example": {
                "folder": "scripts",
                "filename": "hello.js",
                "content": "console.log('Hello World');",
            }
        }


class MoverItemRequest(BaseModel):
    """Model for move item request."""

    source: str = Field(..., description="Source path (relative)")
    destination: str = Field(..., description="Destination path (relative)")

    class Config:
        json_schema_extra = {
            "example": {
                "source": "old_folder/file.txt",
                "destination": "new_folder/file.txt",
            }
        }


class DeleteRequest(BaseModel):
    """Model for delete file/directory request."""

    path: str = Field(..., description="Path to delete (relative)")

    class Config:
        json_schema_extra = {"example": {"path": "temp/old_file.txt"}}


class FileSnippetRequest(BaseModel):
    """Model for file snippet request."""

    path: str = Field(..., description="Relative file path")
    start_line: int = Field(..., description="Starting line number (1-indexed)", ge=1)
    end_line: int = Field(..., description="Ending line number (1-indexed)", ge=1)
    context_lines: int = Field(
        default=0, description="Additional context lines before/after", ge=0
    )

    class Config:
        json_schema_extra = {
            "example": {
                "path": "src/main.py",
                "start_line": 10,
                "end_line": 20,
                "context_lines": 3,
            }
        }
