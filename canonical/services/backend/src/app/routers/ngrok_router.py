"""
Ngrok Share Router - Dynamic file sharing via ngrok

Provides endpoints for sharing files/folders temporarily via ngrok:
- POST /share/start - Start ngrok tunnel and share selected files
- POST /share/add - Add files to active share
- POST /share/remove - Remove files from active share
- POST /share/stop - Stop ngrok tunnel
- GET /share/status - Get current share status
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..config import SCAREFERA_LAB_DIR
from ..file_utils import validate_and_sanitize_path
from ..models.users import User
from ..permissions import require_admin
from .ngrok.helpers import (
    cleanup_share,
    copy_file_to_share,
    get_temp_share_dir,
    remove_file_from_share,
    start_http_server,
    start_ngrok_tunnel,
)

# Import from ngrok submodules
from .ngrok.models import ShareAddRequest, ShareRemoveRequest, ShareStartRequest
from .ngrok.state import (
    add_shared_file,
    clear_shared_files,
    get_ngrok_state,
    remove_shared_file,
    set_ngrok_active,
    set_ngrok_url,
    set_temp_dir,
)

# Setup logging
logger = logging.getLogger(__name__)

# Create router
ngrok_router = APIRouter()


@ngrok_router.post("/share/start")
async def share_start(
    request: ShareStartRequest, _current_user: User = Depends(require_admin)
):
    """
    Start file sharing via ngrok.

    Required permission: admin role (ngrok sharing is admin-only)

    Creates temporary directory, copies selected files, starts HTTP server,
    and creates ngrok tunnel.

    Args:
        request: Share start request with files list

    Returns:
        Public URL and status
    """
    try:
        state = get_ngrok_state()

        # Check if already active
        if state["active"]:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Share already active. Stop current share first or add files to it.",
                    "url": state["url"],
                },
            )

        if not request.files or len(request.files) == 0:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No files specified"},
            )

        # Define base path
        base_path = str(SCAREFERA_LAB_DIR.parent.parent)

        # Create temp directory
        temp_dir = get_temp_share_dir()
        set_temp_dir(temp_dir)
        clear_shared_files()

        # Validate and copy files
        errors = []
        for file_path in request.files:
            file_path = file_path.strip()
            logger.info("[SHARE] Recebido para compartilhar: '%s' (base: '%s')", file_path, base_path)

            # Validate and sanitize path
            is_valid, sanitized_path, error = validate_and_sanitize_path(
                base_path, file_path
            )

            if not is_valid:
                errors.append(f"{file_path}: {error}")
                continue

            # Copy file to share
            success, copy_error = copy_file_to_share(sanitized_path, base_path)
            if not success:
                errors.append(f"{file_path}: {copy_error}")
            else:
                add_shared_file(file_path)

        state = get_ngrok_state()
        if len(state["shared_files"]) == 0:
            cleanup_share()
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "No valid files to share",
                    "errors": errors,
                },
            )

        # Start HTTP server
        success, server_error = start_http_server()
        if not success:
            cleanup_share()
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Failed to start HTTP server: {server_error}",
                },
            )

        # Start ngrok tunnel
        success, public_url, ngrok_error = start_ngrok_tunnel()
        if not success:
            cleanup_share()
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Failed to start ngrok tunnel: {ngrok_error}",
                },
            )

        # Update state
        set_ngrok_active(True)
        set_ngrok_url(public_url)

        state = get_ngrok_state()
        logger.info("Share started with %s files: %s", len(state['shared_files']), public_url)

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "Share started successfully",
                "url": public_url,
                "shared_files": state["shared_files"],
                "errors": errors if errors else None,
            },
        )

    except Exception as e:
        logger.error("Error in /share/start: %s", e, exc_info=True)
        cleanup_share()
        # Don't expose stack trace details to user
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )


@ngrok_router.post("/share/add")
async def share_add(
    request: ShareAddRequest, _current_user: User = Depends(require_admin)
):
    """
    Add files to active share.

    Required permission: admin role (ngrok sharing is admin-only)

    Args:
        request: Add request with files list

    Returns:
        Updated status and file list
    """
    try:
        state = get_ngrok_state()

        if not state["active"]:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "No active share. Start a share first.",
                },
            )

        if not request.files or len(request.files) == 0:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No files specified"},
            )

        base_path = str(SCAREFERA_LAB_DIR.parent.parent)

        # Validate and copy files
        errors = []
        added = []
        for file_path in request.files:
            file_path = file_path.strip()

            # Skip if already shared
            if file_path in state["shared_files"]:
                continue

            # Validate and sanitize path
            is_valid, sanitized_path, error = validate_and_sanitize_path(
                base_path, file_path
            )

            if not is_valid:
                errors.append(f"{file_path}: {error}")
                continue

            # Copy file to share
            success, copy_error = copy_file_to_share(sanitized_path, base_path)
            if not success:
                errors.append(f"{file_path}: {copy_error}")
            else:
                add_shared_file(file_path)
                added.append(file_path)

        logger.info("Added %s files to share", len(added))

        state = get_ngrok_state()
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": f"Added {len(added)} files to share",
                "url": state["url"],
                "shared_files": state["shared_files"],
                "added": added,
                "errors": errors if errors else None,
            },
        )

    except Exception as e:
        logger.error("Error in /share/add: %s", e, exc_info=True)
        # Don't expose stack trace details to user
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )


@ngrok_router.post("/share/remove")
async def share_remove(
    request: ShareRemoveRequest, _current_user: User = Depends(require_admin)
):
    """
    Remove files from active share.

    Required permission: admin role (ngrok sharing is admin-only)

    Args:
        request: Remove request with files list

    Returns:
        Updated status and file list
    """
    try:
        state = get_ngrok_state()

        if not state["active"]:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No active share"},
            )

        if not request.files or len(request.files) == 0:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No files specified"},
            )

        base_path = str(SCAREFERA_LAB_DIR.parent.parent)

        # Remove files
        errors = []
        removed = []
        for file_path in request.files:
            file_path = file_path.strip()

            if file_path not in state["shared_files"]:
                errors.append(f"{file_path}: Not in share")
                continue

            # Remove file from share directory
            success, remove_error = remove_file_from_share(file_path, base_path)
            if not success:
                errors.append(f"{file_path}: {remove_error}")
            else:
                remove_shared_file(file_path)
                removed.append(file_path)

        logger.info("Removed %s files from share", len(removed))

        state = get_ngrok_state()
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": f"Removed {len(removed)} files from share",
                "url": state["url"],
                "shared_files": state["shared_files"],
                "removed": removed,
                "errors": errors if errors else None,
            },
        )

    except Exception as e:
        logger.error("Error in /share/remove: %s", e, exc_info=True)
        # Don't expose stack trace details to user
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )


@ngrok_router.post("/share/stop")
async def share_stop(_current_user: User = Depends(require_admin)):
    """
    Stop active ngrok share.

    Required permission: admin role (ngrok sharing is admin-only)

    Terminates ngrok tunnel, HTTP server, and cleans up temporary directory.

    Returns:
        Confirmation message
    """
    try:
        state = get_ngrok_state()

        if not state["active"]:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "No active share"},
            )

        cleanup_share()

        logger.info("Share stopped")

        return JSONResponse(
            status_code=200,
            content={"status": "ok", "message": "Share stopped successfully"},
        )

    except Exception as e:
        logger.error("Error in /share/stop: %s", e, exc_info=True)
        # Don't expose stack trace details to user
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )


@ngrok_router.get("/share/status")
async def share_status(_current_user: User = Depends(require_admin)):
    """
    Get current share status.

    Required permission: admin role (ngrok sharing is admin-only)

    Returns:
        Share status including URL and shared files
    """
    try:
        state = get_ngrok_state()

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "active": state["active"],
                "url": state["url"] if state["active"] else None,
                "shared_files": state["shared_files"] if state["active"] else [],
            },
        )

    except Exception as e:
        logger.error("Error in /share/status: %s", e, exc_info=True)
        # Don't expose stack trace details to user
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"},
        )
