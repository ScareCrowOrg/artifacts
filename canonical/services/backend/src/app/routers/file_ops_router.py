"""
File Operations Router - Migrated from cockpit/backend

⚠️ SECURITY WARNING - LOCAL DEVELOPMENT ONLY ⚠️
This router allows UNRESTRICTED file operations (any extension) within BASE_DIR.
Designed for LOCAL DEVELOPMENT with version control (git).
DO NOT use in production or multi-user environments.

Provides endpoints for file operations:
- POST /files/save - Save file content (any extension)
- GET /files/list - List ALL files in directory
- GET /files/load - Load file content (any extension)
- POST /files/snippet - Load file snippet by line range
- POST /files/move - Move file or folder
- DELETE /files/delete - Delete file or folder (any type)

These endpoints provide comprehensive file operations for development workflows.
"""

from fastapi import APIRouter

from .file_ops_handlers import (
    delete_item,
    list_files,
    load_file,
    load_file_snippet,
    move_item,
    save_file,
)

# Create router with /files prefix for clean organization
file_ops_router = APIRouter(prefix="/files", tags=["files"])

# Register endpoints (paths are relative to /files prefix)
file_ops_router.post("/save")(save_file)
file_ops_router.get("/list")(list_files)
file_ops_router.get("/load")(load_file)
file_ops_router.post("/snippet")(load_file_snippet)  # Changed to POST for robustness
file_ops_router.post("/move")(move_item)
file_ops_router.delete("/delete")(delete_item)
