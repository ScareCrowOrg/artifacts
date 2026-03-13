"""
Ngrok Share Module - Dynamic file sharing via ngrok.

This module provides functionality for temporarily sharing files and folders
via ngrok tunnels.

Submodules:
- models: Pydantic request/response models
- state: Global state management for ngrok tunnels
- helpers: Helper functions for file operations and tunnel management
"""

from .helpers import (
    cleanup_share,
    copy_file_to_share,
    get_temp_share_dir,
    remove_file_from_share,
    start_http_server,
    start_ngrok_tunnel,
    stop_ngrok_tunnel,
)
from .models import ShareAddRequest, ShareRemoveRequest, ShareStartRequest
from .state import get_ngrok_state, reset_ngrok_state

__all__ = [
    # Models
    "ShareStartRequest",
    "ShareAddRequest",
    "ShareRemoveRequest",
    # State
    "get_ngrok_state",
    "reset_ngrok_state",
    # Helpers
    "get_temp_share_dir",
    "copy_file_to_share",
    "remove_file_from_share",
    "start_ngrok_tunnel",
    "stop_ngrok_tunnel",
    "cleanup_share",
    "start_http_server",
]
