"""
NotebookItemType API Router - RESTful endpoints for NotebookItemType management.

Implements CRUD endpoints for managing NotebookItemType definitions which serve
as blueprints for notebook items (cells and books).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import get_current_user_required
from ..database import db
from ..models import NotebookItemType, User
from ..services.notebook_item_type_registry import get_registry

logger = logging.getLogger(__name__)

# Create notebook_item_types router
notebook_item_types_router = APIRouter(
    prefix="/notebook-item-types", tags=["NotebookItemTypes"]
)


async def _list_notebook_item_types_impl(
    name: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = None,
):
    """
    Internal implementation for listing NotebookItemType definitions.

    Supports filtering by name and pagination via skip/limit parameters.
    """
    try:
        # Get all notebook item types (canonical artifacts)
        try:
            all_types = await db.find_many(
                "notebook_item_types",
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        # Filter by name if provided
        if name:
            all_types = [t for t in all_types if name.lower() in t.name.lower()]

        # Apply pagination
        paginated_types = all_types[skip : skip + limit]

        logger.info(
            "Listed %s notebook item types (total: %s, skip: %s, limit: %s)",
            len(paginated_types), len(all_types), skip, limit
        )

        return paginated_types

    except Exception as e:
        logger.error("Error listing notebook item types: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing notebook item types: {str(e)}",
        )


@notebook_item_types_router.get("", response_model=List[NotebookItemType])
async def list_notebook_item_types(
    name: Optional[str] = Query(None, description="Filter by name (partial match)"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int = Query(
        100, ge=1, le=100, description="Maximum number of items to return"
    ),
    current_user: User = Depends(get_current_user_required),
):
    """
    List all NotebookItemType definitions.

    Supports filtering by name and pagination via skip/limit parameters.
    """
    return await _list_notebook_item_types_impl(name, skip, limit, current_user)


@notebook_item_types_router.get("/listar", response_model=List[NotebookItemType])
async def listar_notebook_item_types(
    name: Optional[str] = Query(None, description="Filter by name (partial match)"),
    skip: int = Query(0, ge=0, description="Number of items to skip for pagination"),
    limit: int = Query(
        100, ge=1, le=100, description="Maximum number of items to return"
    ),
    current_user: User = Depends(get_current_user_required),
):
    """
    List all NotebookItemType definitions (Portuguese alias for compatibility).

    This is an alias endpoint for backward compatibility with frontend code
    that uses /listar pattern. Delegates to the main list implementation.

    Supports filtering by name and pagination via skip/limit parameters.
    """
    return await _list_notebook_item_types_impl(name, skip, limit, current_user)


@notebook_item_types_router.get("/{type_id}", response_model=NotebookItemType)
async def get_notebook_item_type(
    type_id: str, current_user: User = Depends(get_current_user_required)
):
    """
    Get a specific NotebookItemType by ID.
    """
    try:
        try:
            notebook_item_type = await db.find_one(
                "notebook_item_types",
                type_id,
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not notebook_item_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NotebookItemType {type_id} not found",
            )

        logger.info("Retrieved notebook item type: %s", type_id)
        return notebook_item_type

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting notebook item type %s: %s", type_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting notebook item type: {str(e)}",
        )


@notebook_item_types_router.post(
    "", response_model=NotebookItemType, status_code=status.HTTP_201_CREATED
)
async def create_notebook_item_type(
    notebook_item_type: NotebookItemType,
    _scope: str = "published",  # Phase 1B: Type definitions ALWAYS go to MongoDB (canonical)
    current_user: User = Depends(get_current_user_required),
):
    """
    Create a new NotebookItemType.

    **Phase 1B - Special Case**:
    - NotebookItemType definitions are ALWAYS stored in MongoDB (scope="published" is forced)
    - These are canonical type definitions, not user artifacts
    - Sandbox is not used for type definitions

    The ID will be auto-generated if not provided.
    created_at and updated_at timestamps are set automatically.

    Example request body:
    ```json
    {
        "name": "Ingestion Cell",
        "description": "Cell type for data ingestion workflows",
        "default_refs": {
            "workflow_graph": ["workflows/ingestion.py"],
            "docs": ["docs/ingestion.md"]
        },
        "default_initial_data": {
            "source_type": "api",
            "batch_size": 100
        },
        "allow_instance_override_refs": true
    }
    ```
    """
    try:
        # Check if a type with the same name already exists
        try:
            existing_types = await db.find_many(
                "notebook_item_types",
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        for existing in existing_types:
            if existing.name == notebook_item_type.name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"NotebookItemType with name '{notebook_item_type.name}' already exists",
                )

        # Insert the new type
        # Phase 1B: Type definitions ALWAYS go to MongoDB (canonical, not sandbox)
        await db.insert(
            "notebook_item_types", notebook_item_type, current_user=current_user
        )

        logger.info("Created notebook item type: %s (scope=published)", notebook_item_type.id)
        return notebook_item_type

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating notebook item type: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating notebook item type: {str(e)}",
        )


@notebook_item_types_router.put("/{type_id}", response_model=NotebookItemType)
async def update_notebook_item_type(
    type_id: str,
    updated_type: NotebookItemType,
    _scope: str = "published",  # Phase 1B: Type definitions ALWAYS go to MongoDB (canonical)
    current_user: User = Depends(get_current_user_required),
):
    """
    Update an existing NotebookItemType.

    **Phase 1B - Special Case**:
    - NotebookItemType definitions are ALWAYS stored in MongoDB (scope="published" is forced)
    - These are canonical type definitions, not user artifacts
    - Sandbox is not used for type definitions

    The type_id in the path takes precedence over the ID in the request body.
    The updated_at timestamp is automatically updated.
    """
    try:
        # Check if type exists
        try:
            existing_type = await db.find_one(
                "notebook_item_types",
                type_id,
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not existing_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NotebookItemType {type_id} not found",
            )

        # Update the type (ensure ID matches path parameter)
        updated_type_dict = updated_type.model_dump()
        updated_type_dict["id"] = type_id

        # Update timestamp
        from datetime import datetime

        updated_type_dict["updated_at"] = datetime.utcnow()

        final_type = NotebookItemType(**updated_type_dict)

        # Persist the update
        # Phase 1B: Type definitions ALWAYS go to MongoDB (canonical, not sandbox)
        await db.update("notebook_item_types", type_id, final_type, is_canonical=True)

        logger.info("Updated notebook item type: %s (scope=published)", type_id)
        return final_type

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating notebook item type %s: %s", type_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating notebook item type: {str(e)}",
        )


@notebook_item_types_router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook_item_type(
    type_id: str,
    _scope: str = "published",  # Phase 1B: Type definitions ALWAYS go to MongoDB (canonical)
    current_user: User = Depends(get_current_user_required),
):
    """
    Delete a NotebookItemType.

    **Phase 1B - Special Case**:
    - NotebookItemType definitions are ALWAYS stored in MongoDB (scope="published" is forced)
    - These are canonical type definitions, not user artifacts
    - Sandbox is not used for type definitions

    Note: This will not delete cells or books that reference this type.
    Consider the implications before deleting types that are in use.
    """
    try:
        # Check if type exists
        try:
            existing_type = await db.find_one(
                "notebook_item_types",
                type_id,
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not existing_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"NotebookItemType {type_id} not found",
            )

        # Delete the type
        # Phase 1B: Type definitions ALWAYS go to MongoDB (canonical, not sandbox)
        await db.delete("notebook_item_types", type_id, is_canonical=True)

        logger.info("Deleted notebook item type: %s (scope=published)", type_id)
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting notebook item type %s: %s", type_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting notebook item type: {str(e)}",
        )


# ============================================================================
# Registry-based Endpoints (Plug and Play Cell Types Discovery)
# ============================================================================


@notebook_item_types_router.get("/registry/list", response_model=List[NotebookItemType])
async def list_registered_cell_types(
    _current_user: User = Depends(get_current_user_required),
):
    """
    List all cell types discovered from the registry.

    This endpoint uses the plug-and-play registry to discover types from
    artifacts/canonical/cell_types/ directory.
    """
    registry = get_registry()
    return registry.list_types()


@notebook_item_types_router.get(
    "/registry/{type_id}/validate", response_model=Dict[str, bool]
)
async def validate_cell_type_refs(
    type_id: str, _current_user: User = Depends(get_current_user_required)
):
    """
    Validate that all referenced files exist for a cell type.

    Args:
        type_id: ID of the cell type to validate

    Returns:
        Dict mapping ref paths to existence status
    """
    registry = get_registry()
    cell_type = registry.get_type(type_id)

    if not cell_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cell type '{type_id}' not found in registry",
        )

    return registry.validate_refs(type_id)


@notebook_item_types_router.post("/registry/discover", response_model=Dict[str, Any])
async def discover_cell_types(_current_user: User = Depends(get_current_user_required)):
    """
    Trigger re-discovery of cell types from the filesystem.

    This endpoint automatically syncs discovered types to the database,
    making them immediately available via standard API endpoints.

    Useful for development when adding new types without restarting server.

    Returns:
        Dict with discovery statistics
    """
    registry = get_registry()
    discovered_types = await registry.discover_types(sync_to_db=True)

    return {
        "discovered_count": len(discovered_types),
        "type_ids": [t.id for t in discovered_types],
        "synced_to_database": True,
    }
