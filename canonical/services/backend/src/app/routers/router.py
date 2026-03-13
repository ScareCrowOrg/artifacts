"""
Main API router with all endpoints for staging backend.

Implements:
- GET /ScareFeraLab/{file_path} - Serve files
- POST /tree-refresh - Force rebuild of directory tree
- GET /tree - Return directory tree with filters
- POST /persist/{path}/{filename} - Save single file
- POST /persist-batch - Save multiple files
"""

import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi import Path as PathParam
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..config import DEBUG, SCAREFERA_LAB_DIR
from ..file_utils import (
    decode_base64_content,
    ensure_directory_exists,
    validate_and_sanitize_path,
    validate_filename_extension,
    write_file_atomically,
)
from ..tree_builder import ROOT_PATH_INDICATORS, TreeBuilder

# Setup logging
logger = logging.getLogger(__name__)

# Initialize tree builder
tree_builder = TreeBuilder(str(SCAREFERA_LAB_DIR))

# Create router
router = APIRouter()


def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error messages for external users.
    In DEBUG mode, shows full error. In production, shows generic message.
    """
    if DEBUG:
        return str(error)
    else:
        # In production, don't expose internal errors but include timestamp for support
        import datetime

        timestamp = datetime.datetime.utcnow().isoformat()
        return f"An internal error occurred. Please contact support with timestamp: {timestamp}"


# Pydantic models for request validation


class FileContent(BaseModel):
    """Model for single file content."""

    content: str = Field(..., description="Base64-encoded file content")

    class Config:
        json_schema_extra = {
            "example": {"content": "Y29uc29sZS5sb2coJ0hlbGxvIFdvcmxkJyk7"}
        }


class BatchFileItem(BaseModel):
    """Model for batch file upload item."""

    path: str = Field(..., description="Relative path within ScareFeraLab")
    filename: str = Field(..., description="Filename with extension")
    content: str = Field(..., description="Base64-encoded file content")

    class Config:
        json_schema_extra = {
            "example": {
                "path": "scripts",
                "filename": "hello.js",
                "content": "Y29uc29sZS5sb2coJ0hlbGxvIFdvcmxkJyk7",
            }
        }


class BatchUploadRequest(BaseModel):
    """Model for batch upload request."""

    files: List[BatchFileItem] = Field(..., description="List of files to upload")

    class Config:
        json_schema_extra = {
            "example": {
                "files": [
                    {
                        "path": "scripts",
                        "filename": "hello.js",
                        "content": "Y29uc29sZS5sb2coJ0hlbGxvIFdvcmxkJyk7",
                    }
                ]
            }
        }


# Endpoints


@router.get("/ScareFeraLab/{file_path:path}")
async def serve_file(file_path: str):
    """
    Serve a file from the ScareFeraLab directory.

    Args:
        file_path: Relative path to the file within ScareFeraLab

    Returns:
        File content with appropriate media type

    Raises:
        HTTPException: If file not found or path invalid
    """
    # Validate and sanitize path to prevent path traversal attacks
    # CodeQL Warning: Path injection - This is a false positive as we validate
    # the path with validate_and_sanitize_path() which prevents traversal
    is_valid, safe_path, error = validate_and_sanitize_path(
        str(SCAREFERA_LAB_DIR), file_path
    )

    if not is_valid:
        logger.warning("Invalid path access attempt: %s - %s", file_path, error)
        raise HTTPException(status_code=400, detail=error)

    # Safe to use path after validation
    file_obj = Path(safe_path)
    if not file_obj.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_obj.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    # Return file
    return FileResponse(
        safe_path, media_type="application/octet-stream", filename=file_obj.name
    )


@router.post("/tree-refresh")
async def refresh_tree():
    """
    Force a rebuild of the directory tree cache.

    This endpoint should be called after file operations to ensure
    the tree reflects the latest state.

    Returns:
        Success message with new tree
    """
    # Clear cache
    tree_builder.refresh_cache()

    # Build fresh tree
    tree = tree_builder.build_tree(include_hidden=True, use_cache=False)

    logger.info("Directory tree cache refreshed")

    return {"success": True, "message": "Tree cache refreshed", "tree": tree}


@router.get("/tree")
async def get_tree(
    format: str = Query("tree", description="Response format: 'tree' or 'flat'"),
    path: str = Query("", description="Relative path to start from (empty = root)"),
    include_hidden: bool = Query(False, description="Include hidden files"),
    max_depth: Optional[int] = Query(None, description="Maximum depth to traverse"),
    file_type: Optional[str] = Query(
        None, description="Filter by type: 'file' or 'directory'"
    ),
):
    """
    Get directory tree with various filters and formats.

    Args:
        format: Response format ('tree' for nested, 'flat' for list)
        path: Relative path to start from (empty = root, maintains backward compatibility)
        include_hidden: Include hidden files (starting with .)
        max_depth: Maximum depth to traverse (None = unlimited)
        file_type: Filter by type ('file' or 'directory', None = all)

    Returns:
        Directory tree in requested format

    Raises:
        HTTPException: If invalid parameters
    """
    # Validate format
    if format not in ["tree", "flat"]:
        raise HTTPException(
            status_code=400, detail="Invalid format. Use 'tree' or 'flat'"
        )

    # Validate file_type
    if file_type and file_type not in ["file", "directory"]:
        raise HTTPException(
            status_code=400, detail="Invalid file_type. Use 'file' or 'directory'"
        )

    try:
        if format == "flat":
            # For flat format, always use full tree (can be filtered by file_type)
            result = tree_builder.get_flat_list(
                include_hidden=include_hidden, file_type=file_type
            )
            # If path is specified for flat format, filter results
            if path and path not in ROOT_PATH_INDICATORS:
                clean_path = path.strip("/")
                result = [
                    item
                    for item in result
                    if item["path"].startswith(clean_path + "/")
                    or item["path"] == clean_path
                ]
        else:
            # For tree format, use subtree if path is specified
            if path and path not in ROOT_PATH_INDICATORS:
                result = tree_builder.build_subtree(
                    path, include_hidden=include_hidden, max_depth=max_depth
                )
            else:
                result = tree_builder.build_tree(
                    include_hidden=include_hidden, max_depth=max_depth, use_cache=True
                )
            # Wrap tree result in array for consistent response format
            # Tree format returns a single root node dict, but for API consistency
            # and easier client-side handling, we return it as an array.
            # Empty dict {} is returned if directory is empty/inaccessible,
            # which we convert to empty array [] for consistent typing
            result = [result] if result else []

        return {
            "status": "ok",
            "success": True,
            "format": format,
            "path": path if path else "",
            "root": str(SCAREFERA_LAB_DIR),
            "data": result,
        }

    except Exception as e:
        logger.error("Error building tree: %s", str(e))
        raise HTTPException(status_code=500, detail=sanitize_error_message(e)) from e


@router.post("/persist/{path:path}/{filename}")
async def persist_file(
    path: str = PathParam(
        ..., description="Relative directory path within ScareFeraLab"
    ),
    filename: str = PathParam(..., description="Filename with extension"),
    file_content: FileContent = Body(...),
):
    """
    Save a single file to the specified path.

    Args:
        path: Relative directory path within ScareFeraLab
        filename: Filename with extension
        file_content: Request body with base64-encoded content

    Returns:
        Success message with file path

    Raises:
        HTTPException: If validation fails or write error occurs
    """
    # Validate filename
    is_valid_name, name_error = validate_filename_extension(filename)
    if not is_valid_name:
        raise HTTPException(status_code=400, detail=name_error)

    # Validate and sanitize directory path
    is_valid_path, safe_dir, path_error = validate_and_sanitize_path(
        str(SCAREFERA_LAB_DIR), path
    )

    if not is_valid_path:
        raise HTTPException(status_code=400, detail=path_error)

    # Ensure directory exists
    success, dir_error = ensure_directory_exists(safe_dir)
    if not success:
        raise HTTPException(status_code=500, detail=dir_error)

    # Construct full file path
    full_path = Path(safe_dir) / filename

    # Decode content
    success, decoded_content, decode_error = decode_base64_content(file_content.content)
    if not success:
        raise HTTPException(status_code=400, detail=decode_error)

    # Write file atomically
    success, write_error = write_file_atomically(str(full_path), decoded_content)
    if not success:
        raise HTTPException(status_code=500, detail=write_error)

    # Refresh tree cache
    tree_builder.refresh_cache()

    logger.info("File saved: %s", full_path)

    return {
        "success": True,
        "message": "File saved successfully",
        "path": str(full_path.relative_to(SCAREFERA_LAB_DIR)),
        "size": len(decoded_content),
    }


@router.post("/persist-batch")
async def persist_batch(request: BatchUploadRequest):
    """
    Save multiple files in a single batch operation.

    This is more efficient than calling persist_file multiple times
    as it only refreshes the tree cache once at the end.

    Args:
        request: Batch upload request with list of files

    Returns:
        Success message with list of saved files and any errors

    Raises:
        HTTPException: If no files provided or all files failed
    """
    if not request.files:
        raise HTTPException(status_code=400, detail="No files provided")

    results = []
    success_count = 0
    error_count = 0

    for file_item in request.files:
        result = {
            "path": file_item.path,
            "filename": file_item.filename,
            "success": False,
            "error": None,
        }

        try:
            # Validate filename
            is_valid_name, name_error = validate_filename_extension(file_item.filename)
            if not is_valid_name:
                result["error"] = name_error
                error_count += 1
                results.append(result)
                continue

            # Validate and sanitize directory path
            is_valid_path, safe_dir, path_error = validate_and_sanitize_path(
                str(SCAREFERA_LAB_DIR), file_item.path
            )

            if not is_valid_path:
                result["error"] = path_error
                error_count += 1
                results.append(result)
                continue

            # Ensure directory exists
            success, dir_error = ensure_directory_exists(safe_dir)
            if not success:
                result["error"] = dir_error
                error_count += 1
                results.append(result)
                continue

            # Construct full file path
            full_path = Path(safe_dir) / file_item.filename

            # Decode content
            success, decoded_content, decode_error = decode_base64_content(
                file_item.content
            )
            if not success:
                result["error"] = decode_error
                error_count += 1
                results.append(result)
                continue

            # Write file atomically
            success, write_error = write_file_atomically(
                str(full_path), decoded_content
            )
            if not success:
                result["error"] = write_error
                error_count += 1
                results.append(result)
                continue

            # Success!
            result["success"] = True
            result["full_path"] = str(full_path.relative_to(SCAREFERA_LAB_DIR))
            result["size"] = len(decoded_content)
            success_count += 1
            results.append(result)

            logger.info("Batch file saved: %s", full_path)

        except Exception as e:
            result["error"] = sanitize_error_message(e)
            error_count += 1
            results.append(result)
            logger.error("Batch save error for %s: %s", file_item.filename, str(e))

    # Refresh tree cache once at the end
    if success_count > 0:
        tree_builder.refresh_cache()

    # Check if all failed
    if success_count == 0:
        raise HTTPException(
            status_code=500,
            detail={"message": "All files failed to save", "results": results},
        )

    return {
        "success": True,
        "message": f"Batch upload completed: {success_count} succeeded, {error_count} failed",
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
    }
