"""
Content Manager Cell - Main execution script.

Provides:
- list: Query and list contents with filters
- load: Get presigned URL or download binary
- persist: Upload content to storage with validation
"""

import asyncio
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
            "error": "Missing 'action' parameter. Must be one of: list, load, persist, delete"
        }
    
    # Route to action handlers
    if action == "list":
        return await handle_list(cell_data)
    elif action == "load":
        return await handle_load(cell_data)
    elif action == "persist":
        # DIAG: Log kwargs to verify user_id is present but was NOT forwarded to handle_persist
        logger.debug("DIAG [execute_cell] action=persist: kwargs=%s, cell_data keys=%s, user_id_in_kwargs=%s",
                     kwargs,
                     list(cell_data.keys()),
                     'user_id' in kwargs)
        # FIX Bug #2a: Forward **kwargs (with user_id) to handle_persist()
        return await handle_persist(cell_data, **kwargs)
    elif action == "delete":
        # FIX Bug #1: Forward delete action to handle_delete()
        logger.debug("DIAG [execute_cell] action=delete: content_id=%s",
                     cell_data.get("content_id", "MISSING"))
        return await handle_delete(cell_data, **kwargs)
    else:
        logger.warning("PERMANENTE [execute_cell] Unknown action discarded: action=%s, cell_data keys=%s",
                       action, list(cell_data.keys()))
        return {
            "success": False,
            "error": f"Unknown action '{action}'. Must be one of: list, load, persist, delete"
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

        logger.debug("DIAG [handle_list] incoming: filters_dict=%s, limit=%s, offset=%s",
                     filters_dict, limit, offset)

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
        logger.debug("DIAG [handle_list] ContentQueryFilters built: content_type_id=%s, assignee_id=%s, origin_cell_id=%s, tags=%s, is_latest=%s",
                     filters.content_type_id, filters.assignee_id, filters.origin_cell_id, filters.tags, filters.is_latest)

        # Get authenticated user injected by cells_router.py
        current_user = cell_data.get('_current_user')

        # Query contents from ContentManager (RBAC enforced)
        content_manager = ContentManager()
        all_contents = await content_manager.query_contents(filters, current_user=current_user)

        # Apply pagination
        total = len(all_contents)
        logger.debug("DIAG [handle_list] query result: total=%s, offset=%s, limit=%s, returned_count=%s",
                     total, offset, limit, min(limit, max(0, total - offset)))
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


async def handle_persist(cell_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    Handle persist action - upload content to storage.

    Args:
        cell_data: Contains content_type_id, filename, binary, fragments, etc.
        **kwargs: Additional keyword arguments (e.g. user_id from router)

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
        source_path = cell_data.get("source_path")
        fragments = cell_data.get("fragments", {})
        tags = cell_data.get("tags", [])
        metadata = cell_data.get("metadata", {})
        origin_cell_id = cell_data.get("origin_cell_id")
        # Get authenticated user injected by cells_router.py
        current_user = cell_data.get('_current_user')
        # Use assignee_id if provided, otherwise user_id from kwargs, then _current_user.id as ultimate fallback
        # FIX Bug #2b: _current_user.id now used as ultimate fallback for assignee_id
        assignee_id = cell_data.get("assignee_id") or cell_data.get("user_id") or (current_user.id if current_user else None)

        # DIAG: Log complete assignee_id fallback chain status
        logger.debug("DIAG [handle_persist] assignee_id fallback chain: "
                     "cell_data.assignee_id=%s, cell_data.user_id=%s, "
                     "_current_user=%s, _current_user.id=%s, "
                     "final_assignee_id=%s",
                     cell_data.get("assignee_id"),
                     cell_data.get("user_id"),
                     'EXISTS' if current_user else 'MISSING',
                     current_user.id if current_user else 'N/A',
                     assignee_id)

        logger.info(f"[DEBUG] Extracted parameters:")
        logger.info(f"[DEBUG]   - content_type_id: {content_type_id}")
        logger.info(f"[DEBUG]   - filename: {filename}")
        logger.info(f"[DEBUG]   - binary_data type: {type(binary_data).__name__}")
        logger.info(f"[DEBUG]   - source_path: {source_path}")
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

        if not binary_data and not source_path:
            return {
                "success": False,
                "error": "Missing 'binary' or 'source_path' parameter: provide at least one"
            }

        if not assignee_id:
            return {
                "success": False,
                "error": "No assignee_id provided and no user context available"
            }

        # ======================================================================
        # REDIS MAGRO: Decide how to obtain the binary data.
        # Option A (source_path): Asset is already on disk — read from runtime dir.
        #   Example: "artifacts/runtime/user/{assignee}/contents/{content_id}/{filename}.png"
        #   After os.path.join("/app", source_path) → "/app/artifacts/runtime/user/.../file.png"
        # Option B (binary): Legacy mode — decode from base64 string.
        # ======================================================================
        if source_path and not binary_data:
            # Redis Magro: read asset from disk instead of decoding base64
            # Ensure path starts with artifacts/ for Docker volume mount at /app/
            if source_path.startswith('/'):
                source_path = source_path.lstrip('/')
            # 🛡️ SECURITY: Anti-path-traversal. Resolve the absolute path to strip
            # any "../" or symlink tricks, then verify it stays within the allowed
            # runtime directory. This prevents authenticated users from reading
            # arbitrary files (e.g. /etc/passwd) via a crafted source_path.
            abs_source = os.path.realpath(os.path.join("/app", source_path))
            allowed_base = os.path.realpath("/app/artifacts/runtime/")
            if not abs_source.startswith(allowed_base + os.sep):
                logger.error("REDIS MAGRO: Path traversal attempt blocked: source_path=%s resolved=%s",
                             source_path, abs_source)
                return {
                    "success": False,
                    "error": "Invalid source_path: path must be within runtime directory",
                    "error_code": "SOURCE_PATH_INVALID"
                }
            logger.info("REDIS MAGRO: Reading asset from disk for persist: %s", abs_source)
            try:
                with open(abs_source, "rb") as f:
                    binary = f.read()
                logger.info("REDIS MAGRO: Read %d bytes from %s", len(binary), abs_source)
                mime_type = extract_mime_type_from_filename(filename)
            except FileNotFoundError:
                logger.error("REDIS MAGRO: Source file not found: %s", abs_source)
                return {
                    "success": False,
                    "error": f"Source file not found on disk: {source_path}",
                    "error_code": "SOURCE_PATH_NOT_FOUND"
                }
            except Exception as read_err:
                logger.error("REDIS MAGRO: Failed to read source file %s: %s",
                             abs_source, read_err, exc_info=True)
                return {
                    "success": False,
                    "error": f"Failed to read source file: {str(read_err)}",
                    "error_code": "SOURCE_PATH_READ_ERROR"
                }
        elif source_path and binary_data:
            # Both provided — log warning, prefer binary as the explicit upload
            logger.warning("REDIS MAGRO: Both source_path and binary provided for persist; "
                          "using binary (explicit upload). source_path=%s", source_path)
        elif binary_data:
            # Legacy: decode from base64
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
        else:
            return {
                "success": False,
                "error": "No binary or source_path provided: cannot obtain asset data"
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
            # PERMANENTE: Confirm content was actually persisted (has real content_id, version, created_at)
            logger.warning(
                "[PERSIST-PERMANENTE] Content persisted: id=%s, version=%s, created_at=%s, "
                "data_ref=%s, assignee_id=%s, filename=%s, content_type_id=%s",
                content.id, content.version,
                content.created_at.isoformat() if content.created_at else "NODATE",
                content.data_ref, content.assignee_id,
                content.filename, content.content_type_id,
            )
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
        #
        # RETRY: CentralHub proxy may be temporarily unavailable (transient 500).
        # We retry up to 3 times with exponential backoff before accepting the failure.
        _update_ok = False
        _last_update_err = None
        _max_retries = 3
        for _attempt in range(1, _max_retries + 1):
            try:
                logger.info("[DIAG] handle_persist: calling db.update (attempt %d/%d) collection='contents', doc_id='%s', updates={'$set': {'data_ref': '%s'}}",
                            _attempt, _max_retries, content_id, data_ref)
                await db.update(
                    "contents",
                    content_id,  # plain string, not {"id": content_id}
                    {"$set": {"data_ref": data_ref}},
                    current_user=current_user
                )
                logger.info(f"[DEBUG] MongoDB data_ref updated to: {data_ref}")
                _update_ok = True
                break
            except Exception as update_err:
                _last_update_err = update_err
                # DIAG: Capture HTTP-level details from CentralHub error
                _http_status = getattr(update_err, 'response', None)
                _resp_body = ""
                if _http_status is not None:
                    try:
                        _resp_body = _http_status.text[:500]
                    except Exception:
                        _resp_body = "<could not read>"
                    logger.warning(
                        "DIAG [handle_persist] CentralHub HTTP error details (attempt %d/%d): "
                        "content_id=%s, status_code=%s, response_body=%s",
                        _attempt, _max_retries, content_id, _http_status.status_code, _resp_body
                    )
                if _attempt < _max_retries:
                    _backoff = 0.5 * (2 ** (_attempt - 1))  # 0.5s, 1s
                    logger.warning(
                        "DIAG [handle_persist] data_ref update failed (attempt %d/%d, retrying in %.1fs): "
                        "content_id=%s, error=%s",
                        _attempt, _max_retries, _backoff, content_id, update_err
                    )
                    await asyncio.sleep(_backoff)
                else:
                    logger.warning(
                        "DIAG [handle_persist] data_ref update FAILED after %d attempts: "
                        "content_id=%s, new_data_ref=%s, error=%s",
                        _max_retries, content_id, data_ref, update_err
                    )

        if not _update_ok:
            # Non-critical: file exists in storage, MongoDB still has pending:{uuid}
            # The file WAS saved to disk by LocalStorage. Only the MongoDB data_ref
            # update failed. Include the correct data_ref in response metadata so
            # a recovery mechanism can reconcile.
            logger.warning(
                "PERSIST-RECOVERY: data_ref for content_id=%s is '%s' (disk path). "
                "MongoDB has 'pending:%s'. To recover: run "
                "db.update('contents', '%s', {'$set': {'data_ref': '%s'}})",
                content_id, data_ref, content_id, content_id, data_ref
            )

        # Step 5: Success! Return created content metadata
        # If the MongoDB data_ref update failed, include a warning + recovery info
        # so the caller knows the disk file exists but MongoDB still has pending:{id}
        _response = {
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
        # If MongoDB data_ref update failed, add recovery metadata
        if not _update_ok:
            _response["warning"] = (
                f"Content saved to disk but MongoDB data_ref update failed. "
                f"data_ref='{data_ref}' is the correct disk path. "
                f"MongoDB still has 'pending:{content_id}'."
            )
            _response["recovery"] = {
                "content_id": content_id,
                "correct_data_ref": data_ref,
                "pending_data_ref": f"pending:{content_id}",
                "recovery_command": (
                    f"db.update('contents', '{content_id}', "
                    "{'$set': {'data_ref': '" + data_ref + "'}})"
                )
            }
        return _response
        
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


async def handle_delete(cell_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """
    Handle delete action - remove content from MongoDB and storage.

    Args:
        cell_data: Contains content_id and '_current_user' (injected by cells_router)
        **kwargs: Additional keyword arguments (e.g. user_id from router)

    Returns:
        Result dictionary with success flag
    """
    try:
        # --- Entrada ---
        content_id = cell_data.get("content_id")
        current_user = cell_data.get('_current_user')

        # DIAG: Log de entrada com parametros
        logger.debug("DIAG [handle_delete] entry: content_id=%s, current_user=%s",
                     content_id, current_user.id if current_user else 'MISSING')

        if not content_id:
            return {
                "success": False,
                "error": "Missing 'content_id' parameter"
            }

        # --- Busca do Content no MongoDB ---
        content_manager = ContentManager()
        content = await content_manager.get_content(content_id, current_user=current_user)

        if not content:
            # PERMANENTE: Content_id valido mas nao encontrado — pode ser ID inexistente
            # ou problema de permissao (RBAC silencioso)
            logger.warning("PERMANENTE [handle_delete] Content not found: content_id=%s, user_id=%s",
                           content_id, current_user.id if current_user else 'N/A')
            return {
                "success": False,
                "error": f"Content not found: {content_id}"
            }

        # DIAG: Content encontrado com detalhes
        filename = getattr(content, 'filename', None)
        assignee = getattr(content, 'assignee_id', None)
        logger.debug("DIAG [handle_delete] content found: id=%s, filename=%s, assignee_id=%s",
                     content.id, filename, assignee)

        # --- Delete do Storage ---
        # Se o filename nao existir, pula storage delete e vai direto para MongoDB delete
        storage_deleted = True
        if filename:
            storage = get_storage_backend(assignee_id=assignee)
            storage_deleted = storage.delete(content_id, filename)
            # DIAG: Resultado do storage delete
            logger.debug("DIAG [handle_delete] storage.delete result: content_id=%s, filename=%s, success=%s",
                         content_id, filename, storage_deleted)

            if not storage_deleted:
                # PERMANENTE: Arquivo nao encontrado no storage — pode ser orphan
                logger.warning("PERMANENTE [handle_delete] storage delete returned False: content_id=%s, filename=%s",
                               content_id, filename)
                # Continua mesmo assim para deletar do MongoDB (consistencia)
        else:
            # PERMANENTE: filename ausente — pula storage delete
            logger.warning("PERMANENTE [handle_delete] filename is None for content_id=%s, skipping storage delete",
                           content_id)

        # --- Delete do MongoDB ---
        db_deleted = await db.delete("contents", content_id, current_user=current_user)

        # PERMANENTE: Confirma se o registro foi deletado do DB
        logger.warning("PERMANENTE [handle_delete] db.delete result: content_id=%s, success=%s",
                       content_id, db_deleted)

        if not db_deleted:
            logger.error("PERMANENTE [handle_delete] db.delete returned False: content_id=%s", content_id)
            return {
                "success": False,
                "error": f"Failed to delete content record: {content_id}"
            }

        # --- Sucesso ---
        logger.debug("DIAG [handle_delete] success: content_id=%s deleted", content_id)
        return {
            "success": True,
            "action": "delete"
        }

    except Exception as e:
        logger.error("PERMANENTE [handle_delete] unexpected error: content_id=%s, error=%s",
                     cell_data.get("content_id", "UNKNOWN"), str(e), exc_info=True)
        return {
            "success": False,
            "error": f"Failed to delete content: {str(e)}"
        }
