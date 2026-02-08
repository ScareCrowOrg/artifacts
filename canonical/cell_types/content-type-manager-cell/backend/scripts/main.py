"""
Content Type Manager Cell - Main execution script.

Provides:
- list: List all available content types with metadata
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add backend to path for imports
backend_path = Path(__file__).resolve().parents[6] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.content_manager import ContentTypeLoader

logger = logging.getLogger(__name__)


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute content-type-manager-cell actions.
    
    Args:
        cell_data: Cell execution data with 'action' and parameters
        
    Returns:
        Result dictionary with success flag and data
    """
    action = cell_data.get("action")
    
    if not action:
        return {
            "success": False,
            "error": "Missing 'action' parameter. Must be: list"
        }
    
    # Route to action handler
    if action == "list":
        return await handle_list(cell_data)
    else:
        return {
            "success": False,
            "error": f"Unknown action '{action}'. Must be: list"
        }


async def handle_list(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle list action - list all available content types.
    
    Args:
        cell_data: Contains optional limit parameter
        
    Returns:
        List of all content types with metadata
    """
    try:
        limit = cell_data.get("limit", 100)
        
        # Validate limit parameter
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            return {
                "success": False,
                "action": "list",
                "error": "Invalid limit. Must be an integer between 1 and 100."
            }
        
        # Load content types from filesystem
        loader = ContentTypeLoader()
        content_types = loader.list_content_types()
        
        # Convert to dict format and apply limit
        types_list = []
        for ct in content_types[:limit]:
            types_list.append({
                "id": ct.id,
                "name": ct.name,
                "description": ct.description,
                "mime_type": ct.mime_type,
                "version": ct.version,
                "max_size_bytes": ct.max_size_bytes,
                "allowed_extensions": ct.allowed_extensions,
                "render_hints": ct.render_hints if hasattr(ct, 'render_hints') else {}
            })
        
        return {
            "success": True,
            "action": "list",
            "data": {
                "types": types_list,
                "total": len(content_types)
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing content types: {e}", exc_info=True)
        return {
            "success": False,
            "action": "list",
            "error": f"Failed to list content types: {str(e)}"
        }
