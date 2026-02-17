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
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add backend to path for imports
backend_path = Path(__file__).resolve().parents[6] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.content_manager import ContentManager, ContentTypeLoader
from app.models.content_types import CreateContentRequest, ContentQueryFilters
from app.database import db

# Import cell-specific modules (using importlib to avoid sys.path conflicts with backend.utils)
# storage and utils are in the same directory as this script
_this_dir = Path(__file__).parent
_storage_path = _this_dir / "storage.py"
_utils_path = _this_dir / "utils.py"

# Load storage module
_storage_spec = importlib.util.spec_from_file_location("_cell_storage", _storage_path)
_storage = importlib.util.module_from_spec(_storage_spec)
_storage_spec.loader.exec_module(_storage)
get_storage_backend = _storage.get_storage_backend

# Load utils module
_utils_spec = importlib.util.spec_from_file_location("_cell_utils", _utils_path)
_utils = importlib.util.module_from_spec(_utils_spec)
_utils_spec.loader.exec_module(_utils)
decode_base64_binary = _utils.decode_base64_binary
encode_binary_to_base64 = _utils.encode_binary_to_base64
extract_mime_type_from_filename = _utils.extract_mime_type_from_filename

logger = logging.getLogger(__name__)


class PersistenceTransactionError(Exception):
    """
    Raised when persistence fails after partial completion.
    Indicates potential orphaned files in storage.
    """
    pass


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
        all_contents = await content_manager.query_contents(filters)
        
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
        # Log incoming request
        logger.info("[DEBUG] ===== PERSIST ACTION STARTED =====")
        logger.info(f"[DEBUG] cell_data keys: {list(cell_data.keys())}")

        # Extract parameters
        content_type_id = cell_data.get("content_type_id")
        filename = cell_data.get("filename")
        binary_data = cell_data.get("binary")
        fragments = cell_data.get("fragments", {})
        tags = cell_data.get("tags", [])
        metadata = cell_data.get("metadata", {})
        origin_cell_id = cell_data.get("origin_cell_id")
        # Use assignee_id if provided, otherwise use user_id from current user context
        assignee_id = cell_data.get("assignee_id") or cell_data.get("user_id")

        logger.info(f"[DEBUG] Extracted parameters:")
        logger.info(f"[DEBUG]   - content_type_id: {content_type_id}")
        logger.info(f"[DEBUG]   - filename: {filename}")
        logger.info(f"[DEBUG]   - binary_data type: {type(binary_data).__name__}")
        logger.info(f"[DEBUG]   - assignee_id: {assignee_id}")
        
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

        if not assignee_id:
            return {
                "success": False,
                "error": "No assignee_id provided and no user context available"
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
        
        # ======================================================================
        # CRITICAL FIX: Upload to R2 FIRST, then create MongoDB entry with real data_ref
        # This prevents orphaned files by ensuring R2 upload succeeds before DB insert
        # ======================================================================
        
        # Step 1: Upload to storage backend FIRST (get real data_ref)
        logger.info("[DEBUG] ===== STORAGE BACKEND INITIALIZATION =====")
        storage = get_storage_backend()
        logger.info(f"[DEBUG] Storage backend type: {type(storage).__name__}")

        # Log storage configuration
        if hasattr(storage, 'bucket_name'):
            logger.info(f"[DEBUG] R2 Configuration:")
            logger.info(f"[DEBUG]   - bucket_name: {storage.bucket_name}")
            logger.info(f"[DEBUG]   - endpoint_url: {storage.endpoint_url}")
            logger.info(f"[DEBUG]   - public_url: {storage.public_url if hasattr(storage, 'public_url') else 'N/A'}")
        elif hasattr(storage, 'base_path'):
            logger.info(f"[DEBUG] LocalStorage Configuration:")
            logger.info(f"[DEBUG]   - base_path: {storage.base_path}")

        # Generate temporary content ID for upload (will be used if MongoDB succeeds)
        import uuid
        temp_content_id = str(uuid.uuid4())

        # Prepare metadata for integrity and observability
        storage_metadata = {
            "scareverse-content-id": temp_content_id,
            "persistence-status": "awaiting-db-metadata",
            "origin-cell-id": origin_cell_id or "unknown",
            "content-type-id": content_type_id,
            "created-timestamp": datetime.utcnow().isoformat()
        }

        # Log upload details
        logger.info("[DEBUG] ===== UPLOAD DETAILS =====")
        logger.info(f"[DEBUG]   - temp_content_id: {temp_content_id}")
        logger.info(f"[DEBUG]   - filename: {filename}")
        logger.info(f"[DEBUG]   - size_bytes: {size_bytes}")
        logger.info(f"[DEBUG]   - mime_type: {mime_type}")
        logger.info(f"[DEBUG]   - fragments: {fragments}")
        logger.info(f"[DEBUG] Starting upload...")

        try:
            # Upload with metadata for traceability
            data_ref = storage.upload(
                temp_content_id,
                binary,
                filename,
                mime_type,
                metadata=storage_metadata
            )
            logger.info(f"[DEBUG] ✓ Upload successful!")
            logger.info(f"[DEBUG]   - data_ref: {data_ref}")
        except Exception as storage_error:
            # Upload failed - no persistence occurred, no cleanup needed
            logger.error("[DEBUG] ===== STORAGE UPLOAD FAILED =====")
            logger.error(f"[DEBUG] Error Type: {type(storage_error).__name__}")
            logger.error(f"[DEBUG] Error Message: {str(storage_error)}")
            logger.error(f"[DEBUG] Content Type: {content_type_id}")
            logger.error(f"[DEBUG] Filename: {filename}")
            logger.error(f"[DEBUG] Storage Backend: {type(storage).__name__}")
            if hasattr(storage, 'bucket_name'):
                logger.error(f"[DEBUG] R2 Bucket: {storage.bucket_name}")
                logger.error(f"[DEBUG] R2 Endpoint: {storage.endpoint_url}")
            logger.error(f"[DEBUG] Full traceback:", exc_info=True)
            
            # Return detailed error response
            return {
                "success": False,
                "action": "persist",
                "error": "Failed to upload content to R2",
                "error_code": "R2_UPLOAD_FAILED",
                "details": {
                    "content_type_id": content_type_id,
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "r2_error": str(storage_error),
                    "status": "NO_FILES_CREATED",
                    "cleanup": "NONE_NEEDED"
                }
            }
        
        # Step 2: Create MongoDB entry with REAL data_ref (not pending://)
        # Validate fragments first
        content_manager = ContentManager(content_type_loader)
        try:
            # Validate fragments against ContentType schema
            content_manager.validate_content_fragments(content_type, fragments)
        except ValueError as validation_error:
            # Validation failed - cleanup R2 file
            logger.warning(f"Fragment validation failed: {validation_error}")
            try:
                storage.delete(temp_content_id, filename)
                logger.info(f"✓ Cleanup successful: Deleted {data_ref} from R2 after validation failure")
            except Exception as cleanup_err:
                logger.error(f"Cleanup failed: {cleanup_err}")
            
            return {
                "success": False,
                "error": str(validation_error),
                "error_code": "VALIDATION_ERROR"
            }
        
        # Create content request with REAL data_ref
        create_request = CreateContentRequest(
            content_type_id=content_type_id,
            assignee_id=assignee_id,
            data_ref=data_ref,  # REAL data_ref from R2, not pending://
            filename=filename,
            size_bytes=size_bytes,
            fragments=fragments,
            tags=tags,
            metadata=metadata,
            origin_cell_id=origin_cell_id
        )
        
        # Override the auto-generated ID with the one used for R2 upload
        create_request_dict = create_request.dict()
        create_request_dict['id'] = temp_content_id
        
        # Create Content instance
        # Use absolute import (ephemeral cells can't use relative imports)
        from app.models.content_types import Content
        content = Content(**create_request_dict)
        
        # Insert to MongoDB
        try:
            await db.insert("contents", content)
            logger.info(f"✓ Content saved to MongoDB: {content.id}")
        except Exception as db_error:
            # MongoDB failed → Cleanup R2
            logger.error(f"MongoDB insert failed: {db_error}")

            cleanup_success = False
            cleanup_error = None
            try:
                storage.delete(temp_content_id, filename)
                cleanup_success = True
                logger.info(f"✓ Cleanup successful: Deleted {data_ref} from R2")
            except Exception as cleanup_err:
                cleanup_error = str(cleanup_err)
                logger.critical(
                    f"CLEANUP FAILED: Orphaned file {data_ref} remains in R2. "
                    f"Original error: {db_error}. Cleanup error: {cleanup_err}",
                    exc_info=True
                )

            # Return detailed error with cleanup status
            if cleanup_success:
                return {
                    "success": False,
                    "action": "persist",
                    "error": "Failed to save content metadata to MongoDB",
                    "error_code": "MONGODB_INSERT_FAILED",
                    "details": {
                        "content_type_id": content_type_id,
                        "filename": filename,
                        "r2_status": "UPLOADED_SUCCESSFULLY",
                        "r2_data_ref": data_ref,
                        "mongodb_error": str(db_error),
                        "cleanup_attempted": True,
                        "cleanup_status": "SUCCESS",
                        "status": "ORPHANED_FILE_CLEANED_UP",
                        "action_needed": "NONE - file was deleted from R2"
                    }
                }
            else:
                return {
                    "success": False,
                    "action": "persist",
                    "error": "CRITICAL: Orphaned file remains in R2",
                    "error_code": "ORPHANED_FILE_CLEANUP_FAILED",
                    "details": {
                        "content_type_id": content_type_id,
                        "filename": filename,
                        "r2_data_ref": data_ref,
                        "mongodb_error": str(db_error),
                        "cleanup_error": cleanup_error,
                        "status": "ORPHANED_FILE_IN_R2",
                        "action_needed": f"MANUAL - Contact admin: Delete {data_ref} from R2 console",
                        "alert_level": "CRITICAL"
                    }
                }

        # Step 3: Success! Return created content metadata
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
