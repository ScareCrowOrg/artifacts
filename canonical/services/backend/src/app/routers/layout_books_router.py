"""
Layout Books API Router - RESTful endpoints for workspace layout management.

Implements CRUD endpoints for Layout Books - saved workspace configurations
that include cell positions, grid settings, and initialization data.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from ..models import User, Book, BookType, NotebookItemType
from ..database import db
from ..auth import get_current_user_required
from ..permissions import has_permission, check_resource_ownership, get_user_permissions

logger = logging.getLogger(__name__)

# Create layout books router
layout_books_router = APIRouter(prefix="/layout-books", tags=["Layout Books"])


# Request/Response Models
class CellPosition(BaseModel):
    """Grid position for a cell."""

    x: int = Field(..., description="X coordinate on grid")
    y: int = Field(..., description="Y coordinate on grid")
    w: int = Field(..., description="Width in grid columns")
    h: int = Field(..., description="Height in grid rows")


class CellState(BaseModel):
    """Cell display state."""

    isMinimized: bool = Field(default=False, description="Whether cell is minimized")
    isMaximized: bool = Field(default=False, description="Whether cell is maximized")


class CellReference(BaseModel):
    """Reference to a cell in a layout book."""

    cellId: Optional[str] = Field(None, description="UUID of persistent cell (omit for ephemeral)")
    category: str = Field(..., description="Cell category: 'persistent' or 'ephemeral'")
    type: str = Field(..., description="Cell type identifier")
    title: str = Field(..., description="Cell display title")
    position: CellPosition = Field(..., description="Grid position")
    state: CellState = Field(..., description="Cell display state")
    initialization_data: Optional[Dict[str, Any]] = Field(
        None, description="Init data for ephemeral cells"
    )


class GridConfig(BaseModel):
    """Grid layout configuration."""

    cols: int = Field(default=12, description="Number of columns")
    rowHeight: int = Field(default=30, description="Height of each row in pixels")
    margin: List[int] = Field(default=[10, 10], description="Margin [horizontal, vertical]")


class LayoutBookMetadata(BaseModel):
    """Metadata for layout book."""

    cell_count: int = Field(default=0, description="Total number of cells")
    persistent_count: int = Field(default=0, description="Number of persistent cells")
    ephemeral_count: int = Field(default=0, description="Number of ephemeral cells")
    last_applied: Optional[str] = Field(None, description="ISO timestamp of last application")
    created_from_layout: bool = Field(default=True, description="Created from existing layout")


class CreateLayoutBookRequest(BaseModel):
    """Request to create a new layout book."""

    name: str = Field(..., description="Layout book name", min_length=1, max_length=100)
    description: str = Field(default="", description="Layout book description", max_length=500)
    cells: List[CellReference] = Field(default_factory=list, description="Cell references")
    grid_config: GridConfig = Field(default_factory=GridConfig, description="Grid configuration")


class UpdateLayoutBookRequest(BaseModel):
    """Request to update a layout book."""

    name: Optional[str] = Field(None, description="New name", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="New description", max_length=500)
    cells: Optional[List[CellReference]] = Field(None, description="Updated cell references")
    grid_config: Optional[GridConfig] = Field(None, description="Updated grid configuration")


class LayoutBookListItem(BaseModel):
    """Lightweight layout book item for list responses."""

    id: str
    name: str
    description: str
    cell_count: int
    persistent_count: int
    ephemeral_count: int
    created_at: datetime
    updated_at: datetime


class LayoutBookListResponse(BaseModel):
    """Paginated list of layout books."""

    items: List[LayoutBookListItem]
    total: int
    skip: int
    limit: int


class ApplyLayoutBookResponse(BaseModel):
    """Response from apply validation endpoint."""

    success: bool
    book_id: str
    cells_found: int
    cells_missing: int
    validation_errors: List[str] = Field(default_factory=list)


# Helper function to get or create layout-book NotebookItemType
async def get_layout_book_type(current_user: User) -> NotebookItemType:
    """Get or create the layout-book NotebookItemType."""
    # Try to find existing layout-book type
    try:
        all_types = await db.find_many(
            "notebook_item_types",
            current_user=current_user,
            model_class=NotebookItemType,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    layout_book_type = next(
        (t for t in all_types if t.id == "layout-book" or t.name == "Layout Book"), None
    )

    if layout_book_type:
        return layout_book_type

    # Create new layout-book type if not found
    logger.info("Creating layout-book NotebookItemType")
    layout_book_type = NotebookItemType(
        id="layout-book",
        name="Layout Book",
        description="Save and restore complete workspace layouts",
        default_refs={"docs": ["docs/README.md"]},
        default_initial_data={
            "layout_version": "1.0.0",
            "cells": [],
            "grid_config": {"cols": 12, "rowHeight": 30, "margin": [10, 10]},
            "metadata": {
                "cell_count": 0,
                "persistent_count": 0,
                "ephemeral_count": 0,
                "last_applied": None,
                "created_from_layout": True,
            },
        },
        allow_instance_override_refs=True,
        can_render_dynamically=False,
    )

    await db.insert("notebook_item_types", layout_book_type, current_user=current_user)
    return layout_book_type


@layout_books_router.post(
    "", response_model=Book, response_model_by_alias=False, status_code=status.HTTP_201_CREATED
)
async def create_layout_book(
    request: CreateLayoutBookRequest,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox (local-first)
    current_user: User = Depends(has_permission(["books.create"]))
):
    """
    Create a new layout book.

    Required permission: `books.create`

    **Phase 1B - Local-First Architecture**:
    - `scope="sandbox"` (DEFAULT): Creates layout book in private sandbox (artifacts/sandbox/{user_id}/)
      - Never auto-published to MongoDB
      - Private, local-only storage
      - User must explicitly publish via POST /{id}/publish
    - `scope="published"`: Creates layout book directly in MongoDB (shared, not recommended until stable)

    Captures the current workspace layout including cell positions,
    grid configuration, and initialization data for ephemeral cells.
    """
    try:
        # Get or create layout-book type
        layout_book_type = await get_layout_book_type(current_user)

        # Calculate metadata
        persistent_count = sum(1 for cell in request.cells if cell.category == "persistent")
        ephemeral_count = sum(1 for cell in request.cells if cell.category == "ephemeral")

        metadata = LayoutBookMetadata(
            cell_count=len(request.cells),
            persistent_count=persistent_count,
            ephemeral_count=ephemeral_count,
            last_applied=None,
            created_from_layout=True,
        )

        # Prepare initial_data
        initial_data = {
            "layout_version": "1.0.0",
            "cells": [cell.model_dump(exclude_none=True) for cell in request.cells],
            "grid_config": request.grid_config.model_dump(),
            "metadata": metadata.model_dump(exclude_none=True),
        }

        # Create book
        book = Book(
            assignee_id=current_user.id,
            notebook_item_type_id=layout_book_type.id,
            name=request.name,
            description=request.description,
            type=BookType.VOLATILE,
            source=None,
            purpose="Workspace layout template",
            initial_data=initial_data,
            refs={},
            cells=[],  # Layout books don't use the cells array
            children=[],
        )

        # Unified insert - routing via resource_owner_id
        book_dict = book.model_dump(mode="json")
        result_id = await db.insert(
            collection="books",
            document=book_dict,
            current_user=current_user,
            resource_owner_id=current_user.id if scope == "sandbox" else None,
        )
        if scope == "sandbox":
            logger.info(f"Layout book {book.id} created in sandbox (local, private)")
        else:
            logger.info(f"Layout book {book.id} created and persisted in MongoDB (published)")

        # Return book with scope metadata
        book_dict = book.model_dump()
        book_dict["_scope"] = scope
        book_dict["_location"] = "sandbox" if scope == "sandbox" else "mongodb"
        logger.info(f"Layout book {book.id} created: {request.name} ({len(request.cells)} cells)")
        return Book(**book_dict)

    except Exception as e:
        logger.error(f"Error creating layout book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating layout book: {str(e)}",
        )


@layout_books_router.get("", response_model=LayoutBookListResponse)
async def list_layout_books(
    skip: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=20, ge=1, le=100, description="Max results per page"),
    name: Optional[str] = Query(default=None, description="Filter by name (partial match)"),
    current_user: User = Depends(has_permission(["books.read_own"])),
):
    """
    List layout books for the authenticated user.

    Required permission: `books.read_own`

    Returns paginated list with summary information (not full cell data).
    """
    try:
        # Get layout-book type
        layout_book_type = await get_layout_book_type(current_user)

        # Get all books
        try:
            all_books = await db.find_many("books", current_user=current_user, model_class=Book)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        # Filter for user's layout books only
        layout_books = [
            book
            for book in all_books
            if book.assignee_id == current_user.id
            and book.notebook_item_type_id == layout_book_type.id
            and not book.is_canonical_system_book
        ]

        # Apply name filter if provided
        if name:
            layout_books = [book for book in layout_books if name.lower() in book.name.lower()]

        # Sort by updated_at descending
        layout_books.sort(key=lambda b: b.updated_at, reverse=True)

        total = len(layout_books)

        # Apply pagination
        paginated_books = layout_books[skip : skip + limit]

        # Convert to list items
        items = []
        for book in paginated_books:
            metadata = book.initial_data.get("metadata", {})
            items.append(
                LayoutBookListItem(
                    id=book.id,
                    name=book.name,
                    description=book.description,
                    cell_count=metadata.get("cell_count", 0),
                    persistent_count=metadata.get("persistent_count", 0),
                    ephemeral_count=metadata.get("ephemeral_count", 0),
                    created_at=book.created_at,
                    updated_at=book.updated_at,
                )
            )

        logger.info(f"Listed {len(items)} of {total} layout books for user {current_user.id}")
        return LayoutBookListResponse(items=items, total=total, skip=skip, limit=limit)

    except Exception as e:
        logger.error(f"Error listing layout books: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing layout books: {str(e)}",
        )


@layout_books_router.get("/{book_id}", response_model=Book, response_model_by_alias=False)
async def get_layout_book(
    book_id: str, current_user: User = Depends(has_permission(["books.read_own"]))
):
    """
    Get a layout book by ID with full cell data.

    Required permission: `books.read_own`

    **Phase 1B - Unified Lookup**:
    - Checks L1 cache → sandbox → MongoDB automatically
    - Returns layout book from any location
    """
    try:
        # Phase 1B: Use unified lookup
        try:
            book = await db.find_one(
                "books",
                book_id,
                current_user=current_user,
                model_class=Book,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Layout book {book_id} not found"
            )

        # Validate ownership
        if book.assignee_id != current_user.id:
            user_permissions = await get_user_permissions(current_user)
            if "books.read_any" not in user_permissions and "*" not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only access your own layout books",
                )

        # Verify it's a layout book
        layout_book_type = await get_layout_book_type(current_user)
        if book.notebook_item_type_id != layout_book_type.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified book is not a layout book",
            )

        logger.info(f"Retrieved layout book {book_id}: {book.name}")
        return book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching layout book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching layout book: {str(e)}",
        )


@layout_books_router.put("/{book_id}", response_model=Book, response_model_by_alias=False)
async def update_layout_book(
    book_id: str,
    request: UpdateLayoutBookRequest,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox (local-first)
    current_user: User = Depends(has_permission(["books.update_own"])),
):
    """
    Update a layout book.

    Required permission: `books.update_own`

    **Phase 1B - Scope-Aware Update**:
    - `scope="sandbox"` (DEFAULT): Updates layout book in sandbox only
    - `scope="published"`: Updates layout book in MongoDB (requires explicit choice)

    Can update name, description, cells, and/or grid configuration.
    """
    try:
        # Phase 1B: Use unified lookup
        try:
            book = await db.find_one(
                "books",
                book_id,
                current_user=current_user,
                model_class=Book,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Layout book {book_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=book.assignee_id,
            current_user=current_user,
            admin_permission="books.update_any",
        )

        # Verify it's a layout book
        layout_book_type = await get_layout_book_type(current_user)
        if book.notebook_item_type_id != layout_book_type.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified book is not a layout book",
            )

        # Prepare updates
        updates = {}

        if request.name is not None:
            updates["name"] = request.name

        if request.description is not None:
            updates["description"] = request.description

        # Update initial_data if cells or grid_config changed
        if request.cells is not None or request.grid_config is not None:
            initial_data = book.initial_data.copy()

            if request.cells is not None:
                # Recalculate metadata
                persistent_count = sum(1 for cell in request.cells if cell.category == "persistent")
                ephemeral_count = sum(1 for cell in request.cells if cell.category == "ephemeral")

                initial_data["cells"] = [
                    cell.model_dump(exclude_none=True) for cell in request.cells
                ]
                initial_data["metadata"]["cell_count"] = len(request.cells)
                initial_data["metadata"]["persistent_count"] = persistent_count
                initial_data["metadata"]["ephemeral_count"] = ephemeral_count

            if request.grid_config is not None:
                initial_data["grid_config"] = request.grid_config.model_dump()

            updates["initial_data"] = initial_data

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update provided"
            )

        # Unified update - routing via resource_owner_id
        success = await db.update(
            collection="books",
            doc_id=book_id,
            updates=updates,
            current_user=current_user,
            resource_owner_id=current_user.id if scope == "sandbox" else None,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update layout book from {scope}",
            )

        # Retrieve updated book
        try:
            updated_book = await db.find_one(
                "books",
                book_id,
                current_user=current_user,
                model_class=Book,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        logger.info(f"Layout book {book_id} updated in {scope}: {updated_book.name}")
        return updated_book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating layout book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating layout book: {str(e)}",
        )


@layout_books_router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_layout_book(
    book_id: str,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox (local-first)
    current_user: User = Depends(has_permission(["books.delete_own"]))
):
    """
    Delete a layout book.

    Required permission: `books.delete_own`

    **Phase 1B - Scope-Aware Delete**:
    - `scope="sandbox"` (DEFAULT): Deletes layout book from sandbox only
    - `scope="published"`: Deletes layout book from MongoDB (requires explicit choice)
    """
    try:
        # Phase 1B: Find book using unified lookup
        try:
            book = await db.find_one(
                "books",
                book_id,
                current_user=current_user,
                model_class=Book,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Layout book {book_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=book.assignee_id,
            current_user=current_user,
            admin_permission="books.delete_any",
        )

        # Verify it's a layout book
        layout_book_type = await get_layout_book_type(current_user)
        if book.notebook_item_type_id != layout_book_type.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified book is not a layout book",
            )

        # Phase 1B: Use scope-aware delete
        if scope == "sandbox":
            # Delete from sandbox (local, private)
            success = db._sandbox.delete_from_sandbox(current_user.id, book_id)
            if success:
                await db._invalidate_l1_cache("books", current_user.id)
        else:
            # Delete from MongoDB (published)
            success = await db.delete(
                "books",
                book_id,
                user_id=None,
                session_id=None,
                is_canonical=False,
            )
            if success:
                await db._invalidate_l1_cache("books", current_user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete layout book from {scope}",
            )

        logger.info(f"Layout book {book_id} deleted from {scope}: {book.name}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting layout book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting layout book: {str(e)}",
        )


@layout_books_router.post("/{book_id}/publish", status_code=200)
async def publish_layout_book(
    book_id: str,
    current_user: User = Depends(has_permission(["books.update_own"])),
):
    """
    Publish layout book from sandbox to MongoDB (EXPLICIT user action).

    Required permission: `books.update_own` (own) or `books.update_any` (any)

    **Phase 1B - Explicit Publication Workflow**:
    1. Finds layout book in sandbox (user's private workspace)
    2. Validates ownership and permissions
    3. Moves layout book from sandbox to MongoDB (shared, persistent)
    4. Optionally keeps sandbox copy (for local reference)

    **Privacy Guarantee**:
    - Only explicitly published layout books reach MongoDB
    - Sandbox layout books NEVER auto-sync
    - Users choose when to share their layouts
    """
    try:
        # Phase 1B: Find book in sandbox first
        try:
            book = await db.find_one(
                "books",
                book_id,
                current_user=current_user,
                model_class=Book,
                resource_owner_id=current_user.id,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Layout book {book_id} not found in sandbox",
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=book.assignee_id,
            current_user=current_user,
            admin_permission="books.update_any",
        )

        # Verify it's a layout book
        layout_book_type = await get_layout_book_type(current_user)
        if book.notebook_item_type_id != layout_book_type.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified book is not a layout book",
            )

        # Publish to MongoDB: read from sandbox → insert to runtime
        try:
            # Read from sandbox
            sandbox_book = await db.find_one(
                "books",
                book_id,
                current_user=current_user,
                model_class=Book,
                resource_owner_id=current_user.id,
            )

            if not sandbox_book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Layout book not found in sandbox",
                )

            # Insert into MongoDB (without resource_owner_id → runtime)
            published_id = await db.insert(
                "books",
                sandbox_book.model_dump(mode="json"),
                current_user=current_user,
                resource_owner_id=None,  # ← Routes to runtime/MongoDB
            )

            if not published_id:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to publish layout book to MongoDB",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error publishing layout book: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to publish layout book to MongoDB",
            )

        logger.info(
            f"Layout book {book_id} published to MongoDB by user {current_user.id}"
        )

        return {
            "id": published_id,
            "status": "published",
            "location": "mongodb",
            "message": f"Layout book '{book.name}' published successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing layout book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error publishing layout book: {str(e)}",
        )


@layout_books_router.put("/{book_id}/apply", response_model=ApplyLayoutBookResponse)
async def apply_layout_book(
    book_id: str, current_user: User = Depends(has_permission(["books.read_own"]))
):
    """
    Validate layout book before applying.

    Required permission: `books.read_own`

    Checks that persistent cells still exist in the database.
    Actual cell restoration happens on the frontend.
    """
    try:
        # Get the layout book
        try:
            book = await db.find_one(
                "books",
                book_id,
                current_user=current_user,
                model_class=Book,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Layout book {book_id} not found"
            )

        # Validate ownership
        if book.assignee_id != current_user.id:
            user_permissions = await get_user_permissions(current_user)
            if "books.read_any" not in user_permissions and "*" not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only apply your own layout books",
                )

        # Verify it's a layout book
        layout_book_type = await get_layout_book_type(current_user)
        if book.notebook_item_type_id != layout_book_type.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified book is not a layout book",
            )

        # Extract cell references
        cells = book.initial_data.get("cells", [])
        persistent_cells = [cell for cell in cells if cell.get("category") == "persistent"]

        # Check which persistent cells still exist
        validation_errors = []
        cells_found = 0
        cells_missing = 0

        from ..models import Cell

        try:
            all_user_cells = await db.find_many("cells", current_user=current_user, model_class=Cell)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        user_cell_ids = {cell.id for cell in all_user_cells if cell.assignee_id == current_user.id}

        for cell_ref in persistent_cells:
            cell_id = cell_ref.get("cellId")
            if cell_id in user_cell_ids:
                cells_found += 1
            else:
                cells_missing += 1
                validation_errors.append(
                    f"Persistent cell '{cell_ref.get('title', cell_id)}' (ID: {cell_id}) not found"
                )

        # Update last_applied timestamp
        initial_data = book.initial_data.copy()
        initial_data["metadata"]["last_applied"] = datetime.utcnow().isoformat()

        await db.update(
            "books",
            book_id,
            {"initial_data": initial_data},
            user_id=None,
            session_id=None,
            is_canonical=False,
        )

        logger.info(
            f"Layout book {book_id} apply validation: "
            f"{cells_found} found, {cells_missing} missing"
        )

        return ApplyLayoutBookResponse(
            success=(cells_missing == 0),
            book_id=book_id,
            cells_found=cells_found,
            cells_missing=cells_missing,
            validation_errors=validation_errors,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying layout book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error applying layout book: {str(e)}",
        )
