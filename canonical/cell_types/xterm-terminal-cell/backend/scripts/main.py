"""
Main execution logic for xterm-terminal-cell.

This is a UI-only cell. The terminal session is managed by the frontend
View.vue component via WebSocket. The backend script exists only to satisfy
the plug-and-play cell architecture contract.

Execution returns a no-op success response with the WebSocket endpoint
configuration so that headless callers can discover the connection details.
"""

from typing import Dict, Any


def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the xterm-terminal-cell (no-op).

    The actual terminal interaction happens in the Vue frontend via the
    Node-PTY service WebSocket. This function documents the cell's
    connection parameters for headless/programmatic consumers.

    Args:
        cell_data: Cell instance data containing optional WebSocket config.

    Returns:
        Dict with ui_only flag and WebSocket connection parameters.

    Example:
        >>> execute_cell({})
        {
            "success": True,
            "ui_only": True,
            "ws_url": "",
            "message": "xterm-terminal-cell is a UI-only cell..."
        }
    """
    ws_url = cell_data.get("ws_url", "")

    return {
        "success": True,
        "ui_only": True,
        "ws_url": ws_url,
        "message": (
            "xterm-terminal-cell is a UI-only cell. "
            "Connect to the Node-PTY service WebSocket to start a terminal session."
        ),
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        cell_data = json.loads(sys.argv[1])
    else:
        cell_data = {}

    result = execute_cell(cell_data)
    print(json.dumps(result, indent=2))
