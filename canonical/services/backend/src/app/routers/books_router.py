"""
Books API Router - RESTful endpoints for ScareVerse book management.

Implements CRUD endpoints for books and cell association.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
import logging

from ..models import User, Cell, Book, BookType, CreateBookRequest, AddCellToBookRequest
from ..database import db
from ..auth import get_current_user_required
from ..permissions import has_permission, check_resource_ownership, get_user_permissions
from ..core.exceptions import (
    BookNotFoundException,
    CellNotFoundException,
    ValidationException,
    SaveFailedException,
    ServerException,
)

logger = logging.getLogger(__name__)

# Create books router
books_router = APIRouter(prefix="/books", tags=["Books"])


@books_router.post("/create", response_model=Book, status_code=status.HTTP_201_CREATED)
async def create_book(
    request: CreateBookRequest,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox (local-first)
    current_user: User = Depends(has_permission(["books.create"]))
):
    """
    Create a new book.

    Required permission: `books.create`

    **Phase 1B - Local-First Architecture**:
    - `scope="sandbox"` (DEFAULT): Creates book in private sandbox (artifacts/sandbox/{user_id}/)
      - Never auto-published to MongoDB
      - Private, local-only storage
      - User must explicitly publish via POST /{id}/publish
    - `scope="published"`: Creates book directly in MongoDB (shared, not recommended until stable)

    Now supports NotebookItemType for type-driven behavior.

    Example request body:
    ```json
    {
        "name": "My Book",
        "description": "Book description",
        "purpose": "Book purpose",
        "assignee_id": "uuid-optional",
        "notebook_item_type_id": "uuid-optional"
    }
    ```
    """
    try:
        from ..models import NotebookItemType

        # Use provided assignee_id or fallback to current user
        assignee_id = request.assignee_id or current_user.id

        # Build initial_data and refs from type if provided
        book_data = {}
        book_refs = {}

        if request.notebook_item_type_id:
            try:
                notebook_item_type = await db.find_one(
                    "notebook_item_types",
                    request.notebook_item_type_id,
                    current_user=current_user,
                    model_class=NotebookItemType,
                )
            except PermissionError as e:
                raise HTTPException(status_code=403, detail=str(e))

            if notebook_item_type:
                logger.info(f"Using NotebookItemType: {notebook_item_type.name}")

                # Apply default initial_data
                if notebook_item_type.default_initial_data:
                    book_data.update(notebook_item_type.default_initial_data)

                # Apply default refs
                if notebook_item_type.default_refs:
                    book_refs.update(notebook_item_type.default_refs)

                # Check if instance overrides are allowed
                if notebook_item_type.allow_instance_override_refs and request.refs:
                    book_refs.update(request.refs)
            else:
                logger.warning(f"NotebookItemType {request.notebook_item_type_id} not found")
        elif request.refs:
            # No type, use request refs directly
            book_refs = request.refs

        # Create new book
        book = Book(
            assignee_id=assignee_id,
            notebook_item_type_id=request.notebook_item_type_id,
            name=request.name,
            description=request.description,
            type=BookType.VOLATILE,  # Default to VOLATILE for user-created books
            source=None,
            purpose=request.purpose,
            initial_data=book_data,
            refs=book_refs,
        )

        # Unified insert - routing via resource_owner_id
        book_dict = book.model_dump(mode="json")
        result_id = await db.insert(
            collection="books",
            document=book_dict,
            current_user=current_user,
            resource_owner_id=assignee_id if scope == "sandbox" else None,
        )
        if scope == "sandbox":
            logger.info(f"Book {book.id} created in sandbox (local, private)")
        else:
            logger.info(f"Book {book.id} created and persisted in MongoDB (published)")

        # Return book with scope metadata
        book_dict = book.model_dump()
        book_dict["_scope"] = scope
        book_dict["_location"] = "sandbox" if scope == "sandbox" else "mongodb"
        logger.info(f"Book {book.id} created successfully")
        return Book(**book_dict)

    except Exception as e:
        logger.error(f"Error creating book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating book: {str(e)}",
        )


@books_router.get("/list", response_model=List[Book])
async def list_books(
    assignee_id: str = None, current_user: User = Depends(has_permission(["books.read_own"]))
):
    """
    List books for the authenticated user or a specific user.

    Required permission: `books.read_own` (list own) or `books.read_any` (list all)

    By default, filters out canonical system books (is_canonical_system_book=True).
    """
    try:
        user_permissions = await get_user_permissions(current_user)

        # Get all books
        try:
            all_books = await db.find_many("books", current_user=current_user, model_class=Book)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))

        # Admin or viewer can see all books
        if "books.read_any" in user_permissions or "*" in user_permissions:
            # If specific user requested, filter by that user
            if assignee_id:
                filtered_books = [
                    book
                    for book in all_books
                    if book.assignee_id == assignee_id and not book.is_canonical_system_book
                ]
            else:
                # Return all non-system books
                filtered_books = [book for book in all_books if not book.is_canonical_system_book]
        else:
            # Regular user sees only their own books
            user_id = assignee_id or current_user.id
            filtered_books = [
                book
                for book in all_books
                if book.assignee_id == user_id and not book.is_canonical_system_book
            ]

        logger.info(f"Listed {len(filtered_books)} books")
        return filtered_books

    except Exception as e:
        logger.error(f"Error listing books: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing books: {str(e)}",
        )


@books_router.get("/{book_id}", response_model=Book)
async def get_book(book_id: str, current_user: User = Depends(has_permission(["books.read_own"]))):
    """
    Get a book by ID.

    Required permission: `books.read_own` or `books.read_any`

    **Phase 1B - Unified Lookup**:
    - Searches across all storage layers (sandbox → canonical → MongoDB)
    - Uses L1 Redis cache for performance (~5ms cached hits)
    - Returns book from any location transparently
    """
    try:
        # Phase 1B: Use unified lookup (checks sandbox → MongoDB with L1 cache)
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
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Book {book_id} not found"
            )

        # Validate ownership if not admin
        user_permissions = await get_user_permissions(current_user)

        if book.assignee_id != current_user.id:
            if "books.read_any" not in user_permissions and "*" not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only access your own books",
                )

        return book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching book: {str(e)}",
        )


@books_router.post("/{book_id}/add_cell", response_model=Book)
async def add_cell_to_book(
    book_id: str,
    request: AddCellToBookRequest,
    current_user: User = Depends(has_permission(["books.update_own"])),
):
    """
    Add a cell to a book.

    Required permission: `books.update_own` or `books.update_any`

    Note: Canonical books cannot have cells added directly.
    For canonical books, use the source_book_id field in the cell.
    """
    try:
        # Verify book exists
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
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Book {book_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=book.assignee_id,
            current_user=current_user,
            admin_permission="books.update_any",
        )

        # Check if book is canonical
        if book.is_canonical_system_book:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Canonical book '{book.name}' cannot have cells added directly to the array. "
                f"Use the source_book_id field in the cell to reference this book.",
            )

        # Verify cell exists
        try:
            cells = await db.find_many("cells", current_user=current_user, model_class=Cell)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        cell_exists = any(c.id == request.cell_id for c in cells)

        if not cell_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Cell {request.cell_id} not found"
            )

        # Add cell to book
        if request.cell_id not in book.cells:
            book.cells.append(request.cell_id)

            updates = {"cells": book.cells}

            await db.update("books", book_id, updates, is_canonical=False)

        # Retrieve updated book
        updated_book = await db.find_one("books", book_id, Book)

        logger.info(f"Cell {request.cell_id} added to book {book_id}")
        return updated_book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding cell to book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding cell to book: {str(e)}",
        )


@books_router.put("/{book_id}", response_model=Book)
async def update_book(
    book_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    purpose: Optional[str] = None,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox
    current_user: User = Depends(has_permission(["books.update_own"])),
):
    """
    Update a book.

    Required permission: `books.update_own` (own) or `books.update_any` (any)

    **Phase 1B - Scope-Aware Update**:
    - `scope="sandbox"` (DEFAULT): Updates book in sandbox only
    - `scope="published"`: Updates book in MongoDB (requires explicit choice)

    Can update name, description and/or purpose.
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
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Book {book_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=book.assignee_id,
            current_user=current_user,
            admin_permission="books.update_any",
        )

        # Prepare updates
        updates = {}
        if name is not None:
            updates["name"] = name
        if description is not None:
            updates["description"] = description
        if purpose is not None:
            updates["purpose"] = purpose

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update provided"
            )

        logger.info(f"Updating book {book_id} with updates: {updates}, scope: {scope}")

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
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update book"
            )

        logger.info(f"Book {book_id} updated successfully in {scope}")

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

        logger.info(f"Book {book_id} updated")
        return updated_book

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating book: {str(e)}",
        )


@books_router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: str,
    scope: str = "sandbox",  # Phase 1B: DEFAULT is sandbox (local-first)
    current_user: User = Depends(has_permission(["books.delete_own"]))
):
    """
    Delete a book.

    Required permission: `books.delete_own` (own) or `books.delete_any` (any)

    **Phase 1B - Scope-Aware Delete**:
    - `scope="sandbox"` (DEFAULT): Deletes book from sandbox only
    - `scope="published"`: Deletes book from MongoDB (requires explicit choice)
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
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Book {book_id} not found"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=book.assignee_id,
            current_user=current_user,
            admin_permission="books.delete_any",
        )

        # Prevent deletion of system canonical books
        if hasattr(book, 'is_canonical_system_book') and book.is_canonical_system_book:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete system books or master templates",
            )
        if hasattr(book, 'is_unclassified_master_template') and book.is_unclassified_master_template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete system books or master templates",
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
                detail=f"Failed to delete book from {scope}"
            )

        logger.info(f"Book {book_id} deleted from {scope}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting book: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting book: {str(e)}",
        )
# Phase 1B: Publish endpoint for books

@books_router.post("/{book_id}/publish", status_code=200)
async def publish_book(
    book_id: str,
    current_user: User = Depends(has_permission(["books.update_own"])),
):
    """
    Publish book from sandbox to MongoDB (EXPLICIT user action).

    Required permission: `books.update_own` (own) or `books.update_any` (any)

    **Phase 1B - Explicit Publication Workflow**:
    1. Finds book in sandbox (user's private workspace)
    2. Validates ownership and permissions
    3. Moves book from sandbox to MongoDB (shared, persistent)
    4. Optionally keeps sandbox copy (for local reference)

    **Privacy Guarantee**:
    - Only explicitly published books reach MongoDB
    - Sandbox books NEVER auto-sync
    - User controls what gets shared

    Returns:
        dict: Publication status with IDs and locations
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
                status_code=404,
                detail=f"Book {book_id} not found in sandbox"
            )

        # Validate ownership
        await check_resource_ownership(
            resource_user_id=book.assignee_id,
            current_user=current_user,
            admin_permission="books.update_any",
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
                    detail="Book not found in sandbox",
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
                    status_code=500,
                    detail="Failed to publish book"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error publishing book: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to publish book"
            )

        logger.info(f"Book {book_id} published successfully (user={current_user.id})")

        return {
            "id": published_id,
            "status": "published",
            "location": "mongodb",
            "sandbox_copy_kept": True,
            "message": f"Book {book_id} successfully published to MongoDB"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing book: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error publishing book: {str(e)}",
        )
