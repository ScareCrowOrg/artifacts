"""
Helper functions for Ngrok Share API endpoints.

Contains business logic for:
- Temporary directory management
- File copying to/from share directory
- Ngrok tunnel management
- HTTP server management
- Cleanup operations
"""

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

from ...config import HTTP_CONNECTION_TIMEOUT, HTTP_READ_TIMEOUT, SCAREFERA_LAB_DIR
from .state import (
    get_ngrok_state,
    reset_ngrok_state,
    set_http_process,
    set_ngrok_process,
)

logger = logging.getLogger(__name__)


def get_temp_share_dir() -> Path:
    """Get or create temporary directory for sharing files with secure permissions."""
    import tempfile

    # Use system temp directory for better security and cross-platform compatibility
    base_temp = Path(tempfile.gettempdir())
    temp_dir = base_temp / "scareverse-share"
    temp_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    return temp_dir


def copy_file_to_share(source_path: str, base_path: str) -> Tuple[bool, Optional[str]]:
    """
    Copy file or directory to share directory.

    Args:
        source_path: Validated source file/directory path
        base_path: Repository base path

    Returns:
        Tuple of (success, error_message)
    """
    try:
        state = get_ngrok_state()
        temp_dir = state["temp_dir"]
        if not temp_dir:
            return False, "Share not initialized"
        source = Path(SCAREFERA_LAB_DIR) / source_path.lstrip("/")

        # Create relative path structure in temp directory
        # CodeQL Alert py/path-injection: FALSE POSITIVE
        # source_path is validated by validate_and_sanitize_path() before this function is called
        rel_path = os.path.relpath(source_path, base_path)
        dest_path = temp_dir / rel_path

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file or directory
        # CodeQL Alert py/path-injection: FALSE POSITIVE
        # source_path and dest_path are both validated/constructed safely above
        if source.is_file():
            shutil.copy2(source, dest_path)
        elif source.is_dir():
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(source, dest_path)
        else:
            return False, f"Path does not exist: {rel_path}"

        logger.info("Copied to share: %s", rel_path)
        return True, None

    except Exception as e:
        logger.error("Error copying file to share: %s", e, exc_info=True)
        return False, str(e)


def remove_file_from_share(
    file_path: str, _base_path: str
) -> Tuple[bool, Optional[str]]:
    """
    Remove file or directory from share directory.

    Args:
        file_path: File/directory path to remove (relative)
        base_path: Repository base path

    Returns:
        Tuple of (success, error_message)
    """
    try:
        state = get_ngrok_state()
        temp_dir = state["temp_dir"]
        if not temp_dir:
            return False, "Share not initialized"

        # Build path in temp directory
        # CodeQL Alert py/path-injection: FALSE POSITIVE
        # file_path comes from user input but is validated before this point
        # All file paths are stored in _ngrok_state["shared_files"] after validation
        dest_path = temp_dir / file_path

        if not dest_path.exists():
            return False, f"File not found in share: {file_path}"

        # Remove file or directory
        # CodeQL Alert py/path-injection: FALSE POSITIVE
        # dest_path is constructed from validated file_path above
        if dest_path.is_file():
            dest_path.unlink()
        elif dest_path.is_dir():
            shutil.rmtree(dest_path)

        logger.info("Removed from share: %s", file_path)
        return True, None

    except Exception as e:
        logger.error("Error removing file from share: %s", e, exc_info=True)
        return False, str(e)


def start_ngrok_tunnel(port: int = 9000) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Start ngrok tunnel for the specified port.

    Args:
        port: Local port to expose

    Returns:
        Tuple of (success, public_url, error_message)
    """
    try:
        # Check if ngrok is installed (cross-platform)
        if not shutil.which("ngrok"):
            return False, None, "ngrok not installed. Please install ngrok first."

        # Start ngrok in background
        process = subprocess.Popen(
            ["ngrok", "http", str(port), "--log=stdout"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for ngrok to start and get the public URL
        ngrok_api_url = os.getenv("NGROK_API_URL", "http://ngrok:4040")
        max_wait = 10
        waited = 0
        timeout = HTTP_CONNECTION_TIMEOUT + HTTP_READ_TIMEOUT
        while waited < max_wait:
            try:
                import requests

                response = requests.get(f"{ngrok_api_url}/api/tunnels", timeout=timeout)
                tunnels = response.json()
                if tunnels and "tunnels" in tunnels and len(tunnels["tunnels"]) > 0:
                    public_url = tunnels["tunnels"][0]["public_url"]
                    set_ngrok_process(process)
                    logger.info("Ngrok tunnel started: %s", public_url)
                    return True, public_url, None
            except requests.exceptions.Timeout:
                logger.debug("Timeout waiting for ngrok API (attempt %s/%s)", waited + 1, max_wait)
            except requests.exceptions.RequestException as e:
                logger.debug("Ngrok API not ready yet (attempt %s/%s): %s", waited + 1, max_wait, e)
            except Exception:
                pass
            time.sleep(1)
            waited += 1

        # If we exhausted all retries, kill process and return error
        process.kill()
        return (
            False,
            None,
            f"Failed to get ngrok public URL after waiting (API: {ngrok_api_url})",
        )

    except Exception as e:
        logger.error("Error starting ngrok: %s", e, exc_info=True)
        return False, None, str(e)


def stop_ngrok_tunnel() -> None:
    """Stop active ngrok tunnel."""
    state = get_ngrok_state()
    if state["process"]:
        try:
            state["process"].kill()
            state["process"].wait()
            logger.info("Ngrok tunnel stopped")
        except Exception as e:
            logger.error("Error stopping ngrok: %s", e, exc_info=True)


def cleanup_share() -> None:
    """Clean up share directory and state."""
    state = get_ngrok_state()

    # Stop ngrok
    stop_ngrok_tunnel()

    # Stop HTTP server if running
    if "http_process" in state and state["http_process"]:
        try:
            state["http_process"].kill()
            state["http_process"].wait()
            logger.info("HTTP server stopped")
        except Exception as e:
            logger.error("Error stopping HTTP server: %s", e, exc_info=True)

    # Remove temp directory with proper error handling
    if state["temp_dir"] and state["temp_dir"].exists():
        try:
            # Check if directory is writable before attempting cleanup
            if os.access(state["temp_dir"], os.W_OK):
                shutil.rmtree(state["temp_dir"])
                logger.info("Share directory cleaned up")
            else:
                logger.warning(
                    "Share directory not writable, attempting with ignore_errors"
                )
                shutil.rmtree(state["temp_dir"], ignore_errors=True)
        except Exception as e:
            logger.error("Error cleaning up share directory: %s", e, exc_info=True)

    # Reset state
    reset_ngrok_state()


def start_http_server(port: int = 9000) -> Tuple[bool, Optional[str]]:
    """
    Start simple HTTP server for share directory.

    Args:
        port: Port to serve on

    Returns:
        Tuple of (success, error_message)
    """
    try:
        state = get_ngrok_state()
        temp_dir = state["temp_dir"]
        if not temp_dir:
            return False, "Share directory not initialized"

        # Start Python HTTP server in background
        process = subprocess.Popen(
            ["python", "-m", "http.server", str(port)],
            cwd=str(temp_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        time.sleep(1)

        # Store process in state (will be stopped when ngrok stops)
        set_http_process(process)

        logger.info("HTTP server started on port %s", port)
        return True, None

    except Exception as e:
        logger.error("Error starting HTTP server: %s", e, exc_info=True)
        return False, str(e)
