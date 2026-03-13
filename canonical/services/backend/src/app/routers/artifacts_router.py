"""
Artifacts Router for ScareVerse Backend.

Provides REST API endpoints for artifacts discovery:
- GET /local/cell-types/ - List cell types
- GET /local/cell-types/{type_id}/type.json - Get cell definition
- GET /local/book-types/ - List book types
- GET /local/book-types/{type_id}/type.json - Get book definition
- GET /local/import-map.json - Dynamic import map for frontend
- GET /local/canonical/cell_types/{type_id}/type.json - Legacy endpoint

Integrated from ScareRunner into Backend as part of architecture fix.
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..config import CANONICAL_DIR
from ..database.hybrid.sandbox_ops import SANDBOX_DIR
from ..discovery_service import discover_types, get_type_definition

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/local/cell-types/")
async def list_cell_types():
    """
    List all available cell types.

    **Authentication**: Not required (local development)

    Discovers cell types from canonical directory structure.

    Returns:
        dict: List of cell type IDs with metadata
    """
    try:
        cell_types = discover_types(
            CANONICAL_DIR / "cell_types", SANDBOX_DIR / "cell_types", "cell"
        )
        return {"cell_types": cell_types}
    except Exception as e:
        logger.error("Error listing cell types: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to list cell types: {str(e)}"
        )


@router.get("/local/cell-types/{type_id}/type.json")
async def get_cell_type(type_id: str):
    """
    Get cell type definition.

    **Authentication**: Not required (local development)

    Args:
        type_id: Cell type identifier

    Returns:
        dict: Cell type definition JSON

    Raises:
        HTTPException: If cell type not found
    """
    try:
        definition = get_type_definition(
            type_id, CANONICAL_DIR / "cell_types", SANDBOX_DIR / "cell_types"
        )

        if definition is None:
            raise HTTPException(
                status_code=404, detail=f"Cell type not found: {type_id}"
            )

        return JSONResponse(content=definition)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting cell type %s: %s", type_id, e)
        raise HTTPException(
            status_code=500, detail=f"Failed to get cell type: {str(e)}"
        )


@router.get("/local/book-types/")
async def list_book_types():
    """
    List all available book types.

    **Authentication**: Not required (local development)

    Discovers book types from canonical directory structure.

    Returns:
        dict: List of book type IDs with metadata
    """
    try:
        book_types = discover_types(
            CANONICAL_DIR / "book_types", SANDBOX_DIR / "book_types", "book"
        )
        return {"book_types": book_types}
    except Exception as e:
        logger.error("Error listing book types: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to list book types: {str(e)}"
        )


@router.get("/local/book-types/{type_id}/type.json")
async def get_book_type(type_id: str):
    """
    Get book type definition.

    **Authentication**: Not required (local development)

    Args:
        type_id: Book type identifier

    Returns:
        dict: Book type definition JSON

    Raises:
        HTTPException: If book type not found
    """
    try:
        definition = get_type_definition(
            type_id, CANONICAL_DIR / "book_types", SANDBOX_DIR / "book_types"
        )

        if definition is None:
            raise HTTPException(
                status_code=404, detail=f"Book type not found: {type_id}"
            )

        return JSONResponse(content=definition)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting book type %s: %s", type_id, e)
        raise HTTPException(
            status_code=500, detail=f"Failed to get book type: {str(e)}"
        )


@router.get("/local/import-map.json")
async def get_import_map():
    """
    Generate dynamic import map for frontend.

    **Authentication**: Not required (local development)

    Creates an import map that allows the frontend to dynamically
    import cell and book type components.

    Returns:
        dict: Import map JSON with imports and scopes
    """
    try:
        # Discover all cell types and book types
        cell_types = discover_types(
            CANONICAL_DIR / "cell_types", SANDBOX_DIR / "cell_types", "cell"
        )
        book_types = discover_types(
            CANONICAL_DIR / "book_types", SANDBOX_DIR / "book_types", "book"
        )

        # Build import map
        imports = {}

        # Map #artifacts/ prefix to Vite dev server (for dynamic imports)
        # Browser resolves #artifacts/ → http://localhost:5052/
        # Vite root is /app/artifacts, so #artifacts/canonical/... resolves to:
        # http://localhost:5052/canonical/... which serves /app/artifacts/canonical/...
        imports["#artifacts/"] = "http://localhost:5052/"

        # Add cell type imports
        for cell_type in cell_types:
            type_id = cell_type["id"]
            # Map to frontend View component (e.g., frontend/View.vue)
            imports[f"@scareverse/cell-{type_id}"] = (
                f"/local/canonical/cell_types/{type_id}/frontend/View.vue"
            )

        # Add book type imports
        for book_type in book_types:
            type_id = book_type["id"]
            # Map to frontend View component (e.g., frontend/View.vue)
            imports[f"@scareverse/book-{type_id}"] = (
                f"/local/canonical/book_types/{type_id}/frontend/View.vue"
            )

        import_map = {"imports": imports, "scopes": {}}

        return JSONResponse(content=import_map)
    except Exception as e:
        logger.error("Error generating import map: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate import map: {str(e)}"
        )


@router.get("/local/canonical/cell_types/{type_id}/type.json")
async def get_cell_type_canonical(type_id: str):
    """
    Get cell type definition (legacy endpoint).

    **Authentication**: Not required (local development)

    This is a legacy endpoint for backwards compatibility.
    Redirects to /local/cell-types/{type_id}/type.json

    Args:
        type_id: Cell type identifier

    Returns:
        dict: Cell type definition JSON
    """
    return await get_cell_type(type_id)


@router.get("/local/canonical/book_types/{type_id}/type.json")
async def get_book_type_canonical(type_id: str):
    """
    Get book type definition (legacy endpoint).

    **Authentication**: Not required (local development)

    This is a legacy endpoint for backwards compatibility.
    Redirects to /local/book-types/{type_id}/type.json

    Args:
        type_id: Book type identifier

    Returns:
        dict: Book type definition JSON
    """
    return await get_book_type(type_id)
