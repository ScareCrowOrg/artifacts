"""
Content API router for managing typed content assets.

Provides REST endpoints for:
- Creating content with ContentType validation
- Retrieving content and metadata
- Querying contents with filters
- Creating new versions
- Managing ContentTypes
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..auth import get_current_user
from ..models.content_types import (
    Content,
    ContentQueryFilters,
    ContentType,
    CreateContentRequest,
    UpdateContentMetadataRequest,
)
from ..models.users import User
from ..services.content_manager import ContentManager
from ..services.storage_adapters import StorageFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contents", tags=["contents"])


# Initialize services
content_manager = ContentManager()


@router.post("/", response_model=Content)
async def create_content(
    request: CreateContentRequest, current_user: User = Depends(get_current_user)
):
    """
    Create new content with ContentType validation.

    The content must conform to the schema defined by its ContentType.
    """
    try:
        content = await content_manager.create_content(request, current_user)
        return content
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Error creating content: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/upload", response_model=Content)
async def upload_content(
    file: UploadFile = File(...),
    content_type_id: str = Form(...),
    assignee_id: str = Form(...),
    origin_cell_id: Optional[str] = Form(None),
    fragments: str = Form("{}"),  # JSON string
    current_user: User = Depends(get_current_user),
):
    """
    Upload content file with automatic storage handling.

    This endpoint handles the full workflow:
    1. Receive file upload
    2. Load ContentType and validate
    3. Store file using appropriate StorageAdapter
    4. Create Content with data_ref
    """
    import json

    try:
        # Parse fragments JSON
        fragments_dict = json.loads(fragments)

        # Load ContentType to get storage policy
        content_type = content_manager.loader.load_content_type(content_type_id)
        if not content_type:
            raise HTTPException(
                status_code=404, detail=f"ContentType not found: {content_type_id}"
            )

        # Read file data
        file_data = await file.read()

        # Get storage adapter for ContentType
        storage = StorageFactory.get_adapter(content_type.storage_policy)

        # Generate content ID
        from ..models.base import generate_uuid

        content_id = generate_uuid()

        # Store file and get data_ref
        data_ref = storage.store(
            content_id=content_id, data=file_data, filename=file.filename
        )

        # Calculate file metadata
        size_bytes = len(file_data)
        checksum = storage.calculate_checksum(file_data)

        # Create content
        request = CreateContentRequest(
            content_type_id=content_type_id,
            assignee_id=assignee_id,
            data_ref=data_ref,
            origin_cell_id=origin_cell_id,
            fragments=fragments_dict,
            filename=file.filename,
            size_bytes=size_bytes,
            checksum=checksum,
        )

        content = await content_manager.create_content(request, current_user)
        return content

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid fragments JSON")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Error uploading content: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{content_id}", response_model=Content)
async def get_content(content_id: str, _current_user: User = Depends(get_current_user)):
    """
    Retrieve content by ID.
    """
    content = content_manager.get_content(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return content


@router.get("/", response_model=List[Content])
async def query_contents(
    content_type_id: Optional[str] = None,
    assignee_id: Optional[str] = None,
    origin_cell_id: Optional[str] = None,
    is_latest: Optional[bool] = None,
    _current_user: User = Depends(get_current_user),
):
    """
    Query contents with filters.
    """
    filters = ContentQueryFilters(
        content_type_id=content_type_id,
        assignee_id=assignee_id,
        origin_cell_id=origin_cell_id,
        is_latest=is_latest,
    )

    contents = await content_manager.query_contents(filters)
    return contents


@router.post("/{content_id}/versions", response_model=Content)
async def create_content_version(
    content_id: str,
    request: UpdateContentMetadataRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Create a new version of content with updated metadata.

    This implements immutable versioning: the old version is marked as
    not latest, and a new version is created.
    """
    try:
        new_version = await content_manager.create_new_version(
            content_id, request, current_user
        )
        return new_version
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("Error creating content version: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{content_id}/history", response_model=List[Content])
async def get_content_history(
    content_id: str, _current_user: User = Depends(get_current_user)
):
    """
    Get version history for content.

    Returns all versions in chronological order.
    """
    history = await content_manager.get_content_history(content_id)
    return history


# ContentType management endpoints


@router.get("/types/", response_model=List[ContentType], tags=["content-types"])
async def list_content_types(_current_user: User = Depends(get_current_user)):
    """
    List all available ContentTypes.
    """
    content_types = content_manager.loader.list_content_types()
    return content_types


@router.get(
    "/types/{content_type_id}", response_model=ContentType, tags=["content-types"]
)
async def get_content_type(
    content_type_id: str, _current_user: User = Depends(get_current_user)
):
    """
    Get a specific ContentType definition.
    """
    content_type = content_manager.loader.load_content_type(content_type_id)
    if not content_type:
        raise HTTPException(status_code=404, detail="ContentType not found")

    return content_type


@router.post("/types/reload", tags=["content-types"])
async def reload_content_types(_current_user: User = Depends(get_current_user)):
    """
    Reload ContentType cache from disk.

    Useful after updating ContentType definitions in Git.
    """
    content_manager.loader.reload_cache()
    return {"status": "ok", "message": "ContentType cache reloaded"}
