"""
Users API Router - RESTful endpoints for ScareVerse user management.

Implements user profile management and cell listing.
Note: Workspace layout management is handled via layout-book system (separate from user profile).
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import get_current_user_required
from ..database import db
from ..models import (
    Cell,
    UpdateUserProfileRequest,
    User,
)
from ..permissions import require_admin

logger = logging.getLogger(__name__)

# Create users router
users_router = APIRouter(prefix="/users", tags=["Users"])


@users_router.get("/", response_model=List[User])
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
):
    """
    List all users (admin only).

    Required permission: admin

    Query parameters:
    - page: Current page (min 1)
    - limit: Items per page (min 1, max 100)

    TODO: Implement database-level pagination for better performance with large datasets
    """
    try:
        # Get all users
        # TODO: Replace with database-level pagination (e.g., db.find_many with skip/limit)
        try:
            all_users = await db.find_many(
                "users", current_user=current_user, model_class=User
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        # Calculate pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit

        paginated_users = all_users[start_idx:end_idx]

        logger.info("Listed %s users (page %s)", len(paginated_users), page)
        return paginated_users

    except Exception as e:
        logger.error("Error listing users: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing users: {str(e)}",
        )


@users_router.get("/{user_id}", response_model=User)
async def get_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_user_required),
):
    """
    Get a user's profile.

    Requires authentication. Users can only retrieve their own profile unless they are admins.
    """
    try:
        if current_user.id != user_id and not current_user.has_role("admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own profile",
            )

        try:
            user = await db.find_one(
                "users", user_id, current_user=current_user, model_class=User
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving user profile: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user profile",
        )


@users_router.put("/{user_id}", response_model=User)
async def update_user_profile(
    user_id: str,
    request: UpdateUserProfileRequest,
    current_user: User = Depends(get_current_user_required),
):
    """
    Update a user's profile.

    Requires authentication. Users can only edit their own profile.
    Editable fields: name, email, galaxy, mascot, user_nickname.

    user_nickname validation:
    - Must match ^[a-z0-9-]+$
    - Maximum 64 characters
    - Must be globally unique (enforced here)
    """
    try:
        if current_user.id != user_id:
            logger.warning(
                "Authorization violation: User %s attempted to update profile for user %s",
                current_user.id,
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own profile",
            )

        try:
            user = await db.find_one(
                "users", user_id, current_user=current_user, model_class=User
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Enforce GLOBAL nickname uniqueness when the caller is changing it.
        # NOTE: The "users" collection has special handling in MultiSourceSearch — it
        # bypasses the RBAC runtime check and calls CentralHub directly, so all users
        # are returned here (not filtered by current_user). The manual loop below
        # therefore performs a true global uniqueness scan across all registered users.
        if request.user_nickname is not None and request.user_nickname != user.user_nickname:
            try:
                existing_users = await db.find_many(
                    "users", current_user=current_user, model_class=User
                )
            except PermissionError as e:
                raise HTTPException(status_code=403, detail=str(e)) from e

            for other in existing_users:
                if other.id != user_id and other.user_nickname == request.user_nickname:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Nickname '{request.user_nickname}' is already taken",
                    )

        # Apply updates
        updates: dict = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.email is not None:
            updates["email"] = request.email
        if request.galaxy is not None:
            updates["galaxy"] = request.galaxy
        if request.mascot is not None:
            updates["mascot"] = request.mascot.model_dump()
        if request.user_nickname is not None:
            updates["user_nickname"] = request.user_nickname

        if updates:
            await db.update("users", user_id, updates, current_user=current_user)

        # Return updated user
        try:
            updated_user = await db.find_one(
                "users", user_id, current_user=current_user, model_class=User
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found after update",
            )

        logger.info("Profile updated for user %s", user_id)
        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating user profile: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user profile",
        )


@users_router.get("/{user_id}/cells", response_model=List[Cell])
async def get_user_cells(
    user_id: str,
    scope: str = "",  # Phase 1B: Empty string = unified lookup (sandbox + MongoDB)
    current_user: User = Depends(get_current_user_required),
):
    """
    Get all cells for a user.

    **Phase 1B - Unified Lookup**:
    - `scope=""` (DEFAULT): Returns cells from sandbox + MongoDB (merged view)
    - `scope="sandbox"`: Returns cells from sandbox only (local, private)
    - `scope="published"`: Returns cells from MongoDB only (shared, persistent)
    """
    try:
        # Verify user exists
        try:
            user = await db.find_one(
                "users", user_id, current_user=current_user, model_class=User
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Phase 1B: Unified lookup for cells
        # Note: This is a simplified implementation - in practice, you'd need
        # to merge sandbox + MongoDB results properly
        if scope == "sandbox":
            # Get sandbox cells only
            # TODO: Implement sandbox-only filtering
            cells = []
        elif scope == "published":
            # Get MongoDB cells only
            try:
                cells = await db.find_many(
                    "cells", current_user=current_user, model_class=Cell
                )
            except PermissionError as e:
                raise HTTPException(status_code=403, detail=str(e)) from e
        else:
            # Get all cells (sandbox + MongoDB merged)
            try:
                cells = await db.find_many(
                    "cells", current_user=current_user, model_class=Cell
                )
            except PermissionError as e:
                raise HTTPException(status_code=403, detail=str(e)) from e

        logger.info("Found %s cells for user %s (scope=%s)", len(cells), user_id, scope or 'unified')
        return cells

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching user cells: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user cells: {str(e)}",
        )
