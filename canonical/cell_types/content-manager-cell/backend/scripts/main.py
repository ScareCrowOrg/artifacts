"""
Content Manager Cell - Main execution script.

Provides:
- list: Query and list contents with filters
- load: Get presigned URL or download binary
- persist: Upload content to storage with validation
"""

import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Add backend to path for imports
backend_path = Path(__file__).resolve().parents[6] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.content_manager import ContentManager, ContentTypeLoader
from app.models.content_types import CreateContentRequest, ContentQueryFilters
from app.database import db

# Import cell-specific modules
from .storage import get_storage_backend
from .utils import decode_base64_binary, encode_binary_to_base64, extract_mime_type_from_filename

logger = logging.getLogger(__name__)


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute content-manager-cell actions.
    
    Args:
        cell_data: Cell execution data with 'action' and parameters
        
    Returns:
        Result dictionary with success flag and data
    """
    action = cell_data.get("action")
    
    if not action:
        return {
            "success": False,
            "error": "Missing 'action' parameter. Must be one of: list, load, persist"
        }
    
    # Route to action handlers
    if action == "list":
        return await handle_list(cell_data)
    elif action == "load":
        return await handle_load(cell_data)
    elif action == "persist":
        return await handle_persist(cell_data)
    else:
        return {
            "success": False,
            "error": f"Unknown action '{action}'. Must be one of: list, load, persist"
        }


async def handle_list(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle list action - query contents with filters.
    
    Args:
        cell_data: Contains filters, limit, offset
        
    Returns:
        List of matching contents with pagination info
    """
    try:
        filters_dict = cell_data.get("filters", {})
        limit = cell_data.get("limit", 20)
        offset = cell_data.get("offset", 0)
        
        # Validate pagination parameters
        if limit < 1 or limit > 100:
            return {
                "success": False,
                "error": "Invalid limit. Must be between 1 and 100."
            }
        
        if offset < 0:
            return {
                "success": False,
                "error": "Invalid offset. Must be >= 0."
            }
        
        # Build query filters
        filters = ContentQueryFilters(
            content_type_id=filters_dict.get("content_type_id"),
            assignee_id=filters_dict.get("assignee_id"),
            origin_cell_id=filters_dict.get("origin_cell_id"),
            tags=filters_dict.get("tags"),
            is_latest=filters_dict.get("is_latest")
        )
        
        # Query contents from ContentManager
        content_manager = ContentManager()
        all_contents = content_manager.query_contents(filters)
        
        # Apply pagination
        total = len(all_contents)
        paginated_contents = all_contents[offset:offset + limit]
        
        # Format response
        contents_data = []
        for content in paginated_contents:
            contents_data.append({
                "id": content.id,
                "content_type_id": content.content_type_id,
                "filename": content.filename,
                "size_bytes": content.size_bytes,
                "created_at": content.created_at.isoformat() if content.created_at else None,
                "fragments": content.fragments,
                "data_ref": content.data_ref,
                "tags": content.tags,
                "version": content.version,
                "is_latest": content.is_latest,
                "origin_cell_id": content.origin_cell_id
            })
        
        return {
            "success": True,
            "action": "list",
            "data": {
                "contents": contents_data,
                "count": len(contents_data),
                "limit": limit,
                "offset": offset,
                "total": total
            }
        }
        
    except Exception as e:
        logger.error(f"Error in list action: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to list contents: {str(e)}"
        }


async def handle_load(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle load action - get presigned URL or download binary.
    
    Args:
        cell_data: Contains content_id, direct_download flag
        
    Returns:
        Presigned URL or binary data
    """
    try:
        content_id = cell_data.get("content_id")
        direct_download = cell_data.get("direct_download", False)
        
        if not content_id:
            return {
                "success": False,
                "error": "Missing 'content_id' parameter"
            }
        
        # Get content metadata from ContentManager
        content_manager = ContentManager()
        content = content_manager.get_content(content_id)
        
        if not content:
            return {
                "success": False,
                "error": f"Content not found: {content_id}"
            }
        
        # Get storage backend
        storage = get_storage_backend()
        
        # Get presigned URL expiry from env or default to 3600
        presigned_expiry = int(os.getenv("R2_PRESIGNED_URL_EXPIRY", "3600"))
        
        if not direct_download:
            # Try to get presigned URL first (recommended)
            presigned_url = storage.get_presigned_url(
                content_id,
                content.filename,
                expires_in=presigned_expiry
            )
            
            if presigned_url:
                # Return presigned URL response
                return {
                    "success": True,
                    "action": "load",
                    "data": {
                        "content_id": content.id,
                        "filename": content.filename,
                        "presigned_url": presigned_url,
                        "presigned_expires_in": presigned_expiry,
                        "size_bytes": content.size_bytes,
                        "mime_type": extract_mime_type_from_filename(content.filename),
                        "fragments": content.fragments
                    }
                }
        
        # Fallback to direct download
        binary = storage.download(content_id, content.filename)
        
        if binary is None:
            return {
                "success": False,
                "error": f"Failed to download content: {content_id}"
            }
        
        # Encode binary to Base64 for JSON transport
        mime_type = extract_mime_type_from_filename(content.filename)
        encoded_binary = encode_binary_to_base64(binary, mime_type)
        
        return {
            "success": True,
            "action": "load",
            "data": {
                "content_id": content.id,
                "filename": content.filename,
                "binary": encoded_binary,
                "size_bytes": content.size_bytes,
                "mime_type": mime_type,
                "fragments": content.fragments
            }
        }
        
    except Exception as e:
        logger.error(f"Error in load action: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to load content: {str(e)}"
        }


async def handle_persist(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle persist action - upload content to storage.
    
    Args:
        cell_data: Contains content_type_id, filename, binary, fragments, etc.
        
    Returns:
        Created content metadata
    """
    try:
        # Extract parameters
        content_type_id = cell_data.get("content_type_id")
        filename = cell_data.get("filename")
        binary_data = cell_data.get("binary")
        fragments = cell_data.get("fragments", {})
        tags = cell_data.get("tags", [])
        metadata = cell_data.get("metadata", {})
        origin_cell_id = cell_data.get("origin_cell_id")
        assignee_id = cell_data.get("assignee_id")
        
        # Validate required parameters
        if not content_type_id:
            return {
                "success": False,
                "error": "Missing 'content_type_id' parameter"
            }
        
        if not filename:
            return {
                "success": False,
                "error": "Missing 'filename' parameter"
            }
        
        if not binary_data:
            return {
                "success": False,
                "error": "Missing 'binary' parameter"
            }
        
        # Decode binary data
        if isinstance(binary_data, str):
            binary, detected_mime = decode_base64_binary(binary_data)
            mime_type = detected_mime
        elif isinstance(binary_data, bytes):
            binary = binary_data
            mime_type = extract_mime_type_from_filename(filename)
        else:
            return {
                "success": False,
                "error": "Invalid binary data format. Must be Base64 string or bytes."
            }
        
        size_bytes = len(binary)
        
        # Validate ContentType and check size limits
        content_type_loader = ContentTypeLoader()
        content_type = content_type_loader.load_content_type(content_type_id)
        
        if not content_type:
            return {
                "success": False,
                "error": f"ContentType not found: {content_type_id}"
            }
        
        # Check max size
        max_size = content_type.max_size_bytes
        if max_size and size_bytes > max_size:
            return {
                "success": False,
                "error": f"File too large. Max size for {content_type_id}: {max_size} bytes, got: {size_bytes} bytes"
            }
        
        # Create Content instance with ContentManager (validates fragments)
        content_manager = ContentManager(content_type_loader)
        
        # Generate a temporary data_ref (will be updated after upload)
        temp_data_ref = f"pending://{content_type_id}"
        
        # Create content request
        create_request = CreateContentRequest(
            content_type_id=content_type_id,
            assignee_id=assignee_id,
            data_ref=temp_data_ref,
            filename=filename,
            size_bytes=size_bytes,
            fragments=fragments,
            tags=tags,
            metadata=metadata,
            origin_cell_id=origin_cell_id
        )
        
        # Validate and create content in database
        content = content_manager.create_content(create_request)
        
        # Upload to storage backend
        storage = get_storage_backend()
        data_ref = storage.upload(content.id, binary, filename, mime_type)
        
        # Update data_ref in database
        db.update(
            "contents",
            {"id": content.id},
            {"$set": {"data_ref": data_ref}}
        )
        
        # Return created content metadata
        return {
            "success": True,
            "action": "persist",
            "data": {
                "id": content.id,
                "content_type_id": content.content_type_id,
                "filename": content.filename,
                "size_bytes": content.size_bytes,
                "data_ref": data_ref,
                "version": content.version,
                "created_at": content.created_at.isoformat() if content.created_at else None,
                "fragments": content.fragments,
                "tags": content.tags,
                "origin_cell_id": content.origin_cell_id
            }
        }
        
    except ValueError as e:
        # Validation errors (fragments, file size, etc.)
        logger.warning(f"Validation error in persist action: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Error in persist action: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to persist content: {str(e)}"
        }
