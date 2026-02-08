"""
Content Explorer Cell - Main execution script.

Composes ContentTypeManagerCell and ContentManagerCell to provide
a unified asset browsing experience.

Actions:
- list: Get content types and optionally filter assets by type
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add backend to path for imports
backend_path = Path(__file__).resolve().parents[6] / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.content_manager import ContentManager, ContentTypeLoader
from app.models.content_types import ContentQueryFilters

logger = logging.getLogger(__name__)


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute content-explorer-cell actions.
    
    Args:
        cell_data: Cell execution data with 'action' and parameters
        
    Returns:
        Result dictionary with success flag and data
    """
    action = cell_data.get("action", "list")
    
    if action == "list":
        return await handle_list(cell_data)
    else:
        return {
            "success": False,
            "error": f"Unknown action '{action}'. Only 'list' is supported."
        }


async def handle_list(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle list action - get content types and optionally assets.
    
    Composes:
    1. ContentTypeLoader.list_content_types() -> get all types
    2. If selected_type_id provided: ContentManager.list_contents() -> get assets
    
    Args:
        cell_data: Contains optional selected_type_id, filters, limit, offset
        
    Returns:
        Combined response with types and assets
    """
    try:
        # Step 1: Get all content types
        content_type_loader = ContentTypeLoader()
        all_types = content_type_loader.list_content_types()
        
        types_response = {
            "types": [
                {
                    "id": ct.id,
                    "name": ct.name,
                    "description": ct.description,
                    "mime_type": ct.mime_type,
                    "version": ct.version,
                    "max_size_bytes": ct.max_size_bytes,
                    "allowed_extensions": ct.allowed_extensions,
                    "render_hints": ct.render_hints or {}
                }
                for ct in all_types
            ],
            "total": len(all_types)
        }
        
        # Step 2: Get assets if type is selected
        selected_type_id = cell_data.get("selected_type_id")
        assets_response = None
        
        if selected_type_id:
            filters_dict = cell_data.get("filters", {})
            # Add content_type_id to filters
            filters_dict["content_type_id"] = selected_type_id
            
            limit = cell_data.get("limit", 20)
            offset = cell_data.get("offset", 0)
            
            # Validate pagination
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
            
            # Build ContentQueryFilters
            content_filters = ContentQueryFilters(
                content_type_id=filters_dict.get("content_type_id"),
                assignee_id=filters_dict.get("assignee_id"),
                origin_cell_id=filters_dict.get("origin_cell_id"),
                tags=filters_dict.get("tags", []),
                is_latest=filters_dict.get("is_latest", True)
            )
            
            # Query assets (get all matching, then paginate)
            content_manager = ContentManager()
            all_contents = content_manager.query_contents(content_filters)
            
            # Apply pagination
            total = len(all_contents)
            paginated_contents = all_contents[offset:offset + limit]
            
            assets_response = {
                "items": [
                    {
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
                        "assignee_id": content.assignee_id,
                        "origin_cell_id": content.origin_cell_id
                    }
                    for content in paginated_contents
                ],
                "total": total,
                "limit": limit,
                "offset": offset
            }
        
        # Compose response
        return {
            "success": True,
            "output": {
                "types": types_response,
                "assets": assets_response,
                "selected_type_id": selected_type_id
            }
        }
        
    except Exception as e:
        logger.error(f"Error in content-explorer-cell list: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to execute content explorer: {str(e)}"
        }
