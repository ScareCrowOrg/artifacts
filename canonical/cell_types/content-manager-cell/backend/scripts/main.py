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


async def execute_cell(cell_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    Execute content-manager-cell actions.

    Args:
        cell_data: Cell execution data with 'action' and parameters
        **kwargs: Additional keyword arguments (e.g. user_id from router)

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
        cell_data: Contains filters, limit, offset, and '_current_user' (injected by cells_router)

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

        # Get authenticated user injected by cells_router.py
        current_user = cell_data.get('_current_user')

        # Query contents from ContentManager (RBAC enforced)
        content_manager = ContentManager()
        all_contents = await content_manager.query_contents(filters, current_user=current_user)
        
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
        cell_data: Contains content_id, direct_download flag, and '_current_user'

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

        # Get authenticated user injected by cells_router.py
        current_user = cell_data.get('_current_user')

        # Get content metadata from ContentManager (RBAC enforced)
        content_manager = ContentManager()
        content = await content_manager.get_content(content_id, current_user=current_user)
        
        if not content:
            return {
                "success": False,
                "error": f"Content not found: {content_id}"
            }
        
        # Get storage backend (use assignee from content for runtime path)
        assignee = getattr(content, 'assignee_id', None)
        storage = get_storage_backend(assignee_id=assignee)
        
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
        # Get authenticated user injected by cells_router.py
        current_user = cell_data.get('_current_user')

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
        # ATOMIC PERSIST: MongoDB FIRST, then storage upload.
        # This prevents orphaned files: if storage fails after MongoDB insert,
        # we clean up the MongoDB record. If MongoDB insert fails, nothing was
        # created — no cleanup needed.
        # ======================================================================

        # Step 0: Generate content_id upfront (same UUID for MongoDB and storage path)
        import uuid
        content_id = str(uuid.uuid4())
        logger.info(f"[DEBUG] Generated content_id: {content_id}")

        # Step 1: Validate fragments, then create Content instance (MongoDB first)
        content_manager = ContentManager(content_type_loader)
        try:
            content_manager.validate_content_fragments(content_type, fragments)
        except ValueError as validation_error:
            logger.warning(f"Fragment validation failed: {validation_error}")
            return {
                "success": False,
                "error": str(validation_error),
                "error_code": "VALIDATION_ERROR"
            }

        # Create content request with placeholder data_ref
        # (will be updated after storage upload succeeds)
        # NOTE: data_ref="" causes MongoDB unique index conflict (E11000) on 2nd content.
        # Fix: each content_id is a unique UUID, so f"pending:{content_id}" is always unique.
        logger.debug("3DMesh-DEBUG: Creating content request with data_ref placeholder. content_id=%s, data_ref='pending:%s'", content_id, content_id)
        create_request = CreateContentRequest(
            content_type_id=content_type_id,
            assignee_id=assignee_id,
            data_ref=f"pending:{content_id}",
            filename=filename,
            size_bytes=size_bytes,
            fragments=fragments,
            tags=tags,
            metadata=metadata,
            origin_cell_id=origin_cell_id
        )

        # Step 2: Insert to MongoDB FIRST (before storage upload).
        # If this fails, nothing was created — no cleanup needed.
        logger.debug("3DMesh-DEBUG: Inserting to MongoDB: content_id=%s, data_ref=%r, filename=%s", content_id, create_request.data_ref, create_request.filename)
        try:
            content = await content_manager.create_content(
                create_request,
                current_user=current_user,
                content_id=content_id
            )
            logger.info(f"[DEBUG] MongoDB insert OK: content.id={content.id}")
        except Exception as db_error:
            logger.error(f"[DEBUG] MongoDB insert failed: {db_error}", exc_info=True)
            # Detect E11000 duplicate key on unique index (e.g. data_ref empty string conflict)
            if "E11000" in str(db_error):
                logger.warning(
                    "3DMesh-DEBUG: MongoDB E11000 duplicate key detected. "
                    "content_id=%s, data_ref=%r. "
                    "Likely cause: data_ref unique index rejects second '' value. "
                    "Pending fix: use unique placeholder per content_id.",
                    content_id, create_request.data_ref
                )
            return {
                "success": False,
                "action": "persist",
                "error": "Failed to save content metadata to MongoDB",
                "error_code": "MONGODB_INSERT_FAILED",
                "details": {
                    "content_type_id": content_type_id,
                    "filename": filename,
                    "mongodb_error": str(db_error),
                    "status": "NO_STORAGE_OPERATION_ATTEMPTED"
                }
            }

        # Step 3: Upload to storage SECOND
        storage = get_storage_backend(assignee_id=assignee_id)
        logger.info(f"[DEBUG] Storage backend: {type(storage).__name__}")

        storage_metadata = {
            "scareverse-content-id": content_id,
            "content-type-id": content_type_id,
            "created-timestamp": datetime.utcnow().isoformat()
        }

        logger.info(f"[DEBUG] Uploading: content_id={content_id}, filename={filename}, size_bytes={size_bytes}")

        try:
            data_ref = storage.upload(
                content_id,
                binary,
                filename,
                mime_type,
                metadata=storage_metadata
            )
            logger.info(f"[DEBUG] Upload OK: data_ref={data_ref}")
        except Exception as storage_error:
            # Storage failed — clean up MongoDB record
            logger.error(f"[DEBUG] Storage upload failed: {storage_error}", exc_info=True)
            cleanup_ok = False
            try:
                await db.delete("contents", content_id, current_user=current_user)
                cleanup_ok = True
                logger.info(f"[DEBUG] Cleanup: deleted MongoDB record {content_id}")
            except Exception as cleanup_err:
                logger.critical(
                    f"CRITICAL: MongoDB cleanup failed for content {content_id}: {cleanup_err}",
                    exc_info=True
                )

            return {
                "success": False,
                "action": "persist",
                "error": "Failed to upload content to storage",
                "error_code": "STORAGE_UPLOAD_FAILED",
                "details": {
                    "content_type_id": content_type_id,
                    "filename": filename,
                    "size_bytes": size_bytes,
                    "storage_error": str(storage_error),
                    "mongodb_content_id": content_id,
                    "mongodb_cleanup": "SUCCESS" if cleanup_ok else f"FAILED: {str(cleanup_err) if 'cleanup_err' in dir() else 'unknown'}",
                    "status": "MONGODB_RECORD_DELETED" if cleanup_ok else "ORPHANED_MONGODB_RECORD"
                }
            }

        # Step 4: Update MongoDB record with real data_ref from storage
        # NOTE: doc_id is a plain string (the document's _id), NOT a dict filter.
        # HybridDatabase.update() expects doc_id: str, and CentralHubProvider.update()
        # builds query={"_id": doc_id}. Passing {"id": content_id} would produce
        # query={"_id": {"id": "uuid"}} which MongoDB silently matches zero documents.
        logger.debug("3DMesh-DEBUG: Updating MongoDB data_ref: content_id=%s, placeholder -> %s", content_id, data_ref)
        try:
            await db.update(
                "contents",
                content_id,  # plain string, not {"id": content_id}
                {"$set": {"data_ref": data_ref}},
                current_user=current_user
            )
            logger.info(f"[DEBUG] MongoDB data_ref updated to: {data_ref}")
        except Exception as update_err:
            # Non-critical: file exists in storage, MongoDB has empty data_ref
            logger.warning(f"[DEBUG] data_ref update failed (non-critical): {update_err}")

        # Step 5: Success! Return created content metadata
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
