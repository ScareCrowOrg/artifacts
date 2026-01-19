"""
Redis Explorer Cell - Main execution script.

This script provides programmatic access to Redis exploration functionality
for ephemeral Redis Explorer cells.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute Redis Explorer cell.
    
    This is an ephemeral cell type primarily used for UI-based exploration.
    Programmatic execution is minimal as most functionality is frontend-driven.
    
    Args:
        cell_data: Cell instance data containing:
            - current_prefix: Current Redis key prefix
            - delimiter: Hierarchical delimiter
            - max_depth: Maximum depth for scanning
            
    Returns:
        Dict with execution results
    """
    try:
        from app.services.redis_explorer_service import RedisExplorerService
        
        service = RedisExplorerService()
        
        # Get parameters from cell data
        prefix = cell_data.get('current_prefix', '')
        delimiter = cell_data.get('delimiter', ':')
        max_depth = cell_data.get('max_depth', 1)
        
        # Scan keys at current level
        result = await service.scan_keys_by_prefix(
            prefix=prefix,
            delimiter=delimiter,
            max_depth=max_depth
        )
        
        logger.info(
            f"Redis Explorer cell executed: "
            f"prefix='{prefix}', "
            f"nodes={len(result['nodes'])}, "
            f"keys={len(result['keys'])}"
        )
        
        return {
            "success": True,
            "scan_result": result,
            "message": f"Found {len(result['nodes'])} branches and {len(result['keys'])} keys"
        }
        
    except Exception as e:
        logger.error(f"Error executing Redis Explorer cell: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to execute Redis Explorer cell"
        }
