"""
Global state management for ngrok tunnels.

Manages the state of active ngrok tunnels, including:
- Tunnel activation status
- Public URLs
- Processes (ngrok and HTTP server)
- Temporary directories
- Shared files list
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

# Global state for ngrok tunnel
_ngrok_state: Dict[str, Any] = {
    "active": False,
    "url": None,
    "process": None,
    "temp_dir": None,
    "shared_files": [],
}


def get_ngrok_state() -> Dict[str, Any]:
    """
    Get current ngrok state.

    Returns:
        Dictionary containing ngrok state
    """
    return _ngrok_state


def reset_ngrok_state() -> None:
    """Reset ngrok state to initial values."""
    _ngrok_state["active"] = False
    _ngrok_state["url"] = None
    _ngrok_state["process"] = None
    _ngrok_state["temp_dir"] = None
    _ngrok_state["shared_files"] = []
    if "http_process" in _ngrok_state:
        _ngrok_state["http_process"] = None


def set_ngrok_active(active: bool) -> None:
    """Set active status."""
    _ngrok_state["active"] = active


def set_ngrok_url(url: Optional[str]) -> None:
    """Set public URL."""
    _ngrok_state["url"] = url


def set_ngrok_process(process: Optional[subprocess.Popen]) -> None:
    """Set ngrok process."""
    _ngrok_state["process"] = process


def set_temp_dir(temp_dir: Optional[Path]) -> None:
    """Set temporary directory."""
    _ngrok_state["temp_dir"] = temp_dir


def set_http_process(process: Optional[subprocess.Popen]) -> None:
    """Set HTTP server process."""
    _ngrok_state["http_process"] = process


def add_shared_file(file_path: str) -> None:
    """Add file to shared files list."""
    if file_path not in _ngrok_state["shared_files"]:
        _ngrok_state["shared_files"].append(file_path)


def remove_shared_file(file_path: str) -> None:
    """Remove file from shared files list."""
    if file_path in _ngrok_state["shared_files"]:
        _ngrok_state["shared_files"].remove(file_path)


def get_shared_files() -> List[str]:
    """Get list of shared files."""
    return _ngrok_state["shared_files"].copy()


def clear_shared_files() -> None:
    """Clear shared files list."""
    _ngrok_state["shared_files"] = []
