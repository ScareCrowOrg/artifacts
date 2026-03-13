---
processed: true
processed_date: 2025-12-08
themes:
  - rbac
  - permissions
  - authorization
  - security
  - middleware
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# RBAC Permissions Middleware - Usage Examples

## Overview

This document provides practical examples of using the RBAC permissions middleware implemented in `app/permissions.py`.

## Basic Usage

### 1. Protecting Endpoints with Specific Permissions

```python
from fastapi import APIRouter, Depends
from app.permissions import has_permission
from app.models.users import Usuario

router = APIRouter()

@router.post("/cells")
async def create_cell(
    cell_data: dict,
    current_user: Usuario = Depends(has_permission(["cells.create"]))
):
    """
    Create a new cell.
    Requires: cells.create permission
    """
    # User is automatically authenticated and authorized
    # current_user contains the authenticated Usuario object
    return {"message": "Cell created", "user": current_user.nome}
```

### 2. Requiring Multiple Permissions (AND logic)

```python
@router.put("/cells/{cell_id}/publish")
async def publish_cell(
    cell_id: str,
    current_user: Usuario = Depends(
        has_permission(["cells.update_own", "cells.publish"], require_all=True)
    )
):
    """
    Publish a cell.
    Requires: BOTH cells.update_own AND cells.publish permissions
    """
    return {"message": "Cell published"}
```

### 3. Requiring Any Permission (OR logic)

```python
@router.get("/cells/{cell_id}")
async def get_cell(
    cell_id: str,
    current_user: Usuario = Depends(
        has_permission(["cells.read_own", "cells.read_any"], require_all=False)
    )
):
    """
    Read a cell.
    Requires: EITHER cells.read_own OR cells.read_any permission
    """
    return {"cell_id": cell_id}
```

### 4. Admin-Only Endpoints

```python
from app.permissions import require_admin

@router.post("/system/config")
async def update_system_config(
    config: dict,
    current_user: Usuario = Depends(require_admin)
):
    """
    Update system configuration.
    Admin only - no specific permission check needed
    """
    return {"message": "Config updated"}
```

### 5. Resource Ownership Validation

```python
from app.permissions import has_permission, check_resource_ownership
from app.database import db
from app.models import Cell

@router.delete("/cells/{cell_id}")
async def delete_cell(
    cell_id: str,
    current_user: Usuario = Depends(has_permission(["cells.delete_own"]))
):
    """
    Delete a cell.
    User must own the cell OR have cells.delete_any permission
    """
    # Fetch the cell
    cell = db.find_one("cells", cell_id, Cell)
    
    # Check ownership (or admin permission)
    check_resource_ownership(
        resource_user_id=cell.usuarioId,
        current_user=current_user,
        admin_permission="cells.delete_any"
    )
    
    # Delete the cell
    db.delete("cells", cell_id)
    return {"message": "Cell deleted"}
```

## Permission Names Convention

Permissions follow the pattern: `{resource}.{action}[_{scope}]`

### Examples:

- `cells.create` - Create own cells
- `cells.read_own` - Read own cells
- `cells.read_any` - Read any user's cells (admin)
- `cells.update_own` - Update own cells
- `cells.update_any` - Update any cells (admin)
- `cells.delete_own` - Delete own cells
- `cells.delete_any` - Delete any cells (admin)
- `books.create` - Create books
- `books.read_own` - Read own books
- `users.manage` - Manage users (admin)
- `system.configure` - Configure system settings (admin)

## Error Responses

### Insufficient Permissions (403)

When a user lacks required permissions:

```json
{
  "error": "insufficient_permissions",
  "message": "Você não tem permissões suficientes para esta ação",
  "required": ["cells.delete_any"],
  "missing": ["cells.delete_any"]
}
```

### Resource Forbidden (403)

When a user tries to access someone else's resource:

```json
{
  "error": "resource_forbidden",
  "message": "Você só pode acessar seus próprios recursos"
}
```

### Admin Required (403)

When a non-admin tries to access an admin endpoint:

```json
{
  "error": "admin_required",
  "message": "Acesso restrito a administradores do sistema"
}
```

## Cache Management

### Automatic Caching

Permissions are automatically cached for 5 minutes to reduce database queries.

### Manual Cache Invalidation

When a user's roles or permissions change:

```python
from app.permissions import invalidate_user_cache

# After updating user roles
invalidate_user_cache(user_id)
```

## Testing Examples

### Unit Test Example

```python
import pytest
from app.permissions import has_permission
from app.models.users import Usuario

@pytest.mark.asyncio
async def test_permission_check():
    user = Usuario(
        id="user-1",
        nome="Test User",
        email="test@test.com",
        roles=["user"]
    )
    
    checker = has_permission(["cells.create"])
    result = await checker(user)
    
    assert result == user
```

### Integration Test Example

```python
from fastapi.testclient import TestClient

def test_create_cell_with_permission(client: TestClient, auth_token: str):
    response = client.post(
        "/cells",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"type": "text", "content": "test"}
    )
    assert response.status_code == 201

def test_create_cell_without_permission(client: TestClient, viewer_token: str):
    response = client.post(
        "/cells",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"type": "text", "content": "test"}
    )
    assert response.status_code == 403
    assert "insufficient_permissions" in response.json()["error"]
```

## Best Practices

1. **Always use the most specific permission**: Prefer `cells.delete_own` over `cells.delete_any` when only owner access is needed.

2. **Combine with ownership checks**: For resource-specific endpoints, first check permission, then validate ownership.

3. **Use require_admin for system operations**: Don't create system-level permissions when admin check is sufficient.

4. **Invalidate cache on role changes**: Always call `invalidate_user_cache()` after modifying user roles.

5. **Test both success and failure cases**: Ensure endpoints are properly protected with tests.

## Performance Considerations

- **Cache Hit Rate**: Aim for >80% cache hit rate
- **First Request**: ~50ms (database query for roles)
- **Cached Requests**: <10ms (in-memory lookup)
- **TTL**: 5 minutes (configurable via `_CACHE_TTL`)

## Migration from Simple Auth

### Before (Only Authentication)

```python
from app.auth import get_current_user_required

@router.delete("/cells/{cell_id}")
async def delete_cell(
    cell_id: str,
    current_user: Usuario = Depends(get_current_user_required)
):
    # Any authenticated user can delete any cell
    db.delete("cells", cell_id)
    return {"message": "Cell deleted"}
```

### After (With Authorization)

```python
from app.permissions import has_permission, check_resource_ownership

@router.delete("/cells/{cell_id}")
async def delete_cell(
    cell_id: str,
    current_user: Usuario = Depends(has_permission(["cells.delete_own"]))
):
    # Fetch cell
    cell = db.find_one("cells", cell_id, Cell)
    
    # Validate ownership or admin permission
    check_resource_ownership(
        resource_user_id=cell.usuarioId,
        current_user=current_user,
        admin_permission="cells.delete_any"
    )
    
    # Only owner or admin can delete
    db.delete("cells", cell_id)
    return {"message": "Cell deleted"}
```

## Related Documentation

- [Authentication Module](./auth.py) - JWT authentication
- [User Models](./models/users.py) - User and role models
- [Permission Models](./models/permissions.py) - Role and permission definitions
