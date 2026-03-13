---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/backend/architecture/hybrid-database-rbac-api.md
themes:
  - database
  - rbac
  - query-engine
  - backend
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# RBAC (Role-Based Access Control) Infrastructure

## Overview

The RBAC module implements a 3-tier access control system for the ScareVerse Query Engine. It validates user permissions before any database access and caches permissions in Redis for performance.

## Architecture

### 3-Tier Access Control

1. **Sandbox Tier**: User-specific data
   - Owner-based access
   - Users can only access their own sandbox data
   - Admin and users with `sandbox.read_any` can access any sandbox

2. **Canonical Tier**: Blueprint/schema data
   - Public collections (9 total) are accessible to everyone
   - Role-based access for protected collections
   - Requires specific collection permissions or `canonical.read`

3. **Runtime Tier**: Operational data
   - Permission-based access
   - Requires collection-specific read permissions
   - Admin always has access

### Public Collections

The following 9 collections are always accessible without authentication:
- `notebook_item_types` - Cell and book type definitions
- `templates` - Template blueprints
- `workflows` - Workflow definitions
- `permissions` - Permission definitions
- `roles` - Role definitions
- `ai_models` - AI model configurations
- `content_types` - Content type schemas
- `agent_types` - Agent type definitions
- `book_types` - Book type definitions

### Protected Collections

The following 4 collections require RBAC validation:
- `cells` - User/agent cell instances
- `books` - User/agent notebooks
- `notebook_items` - Unified items collection
- `contents` - User-generated content with versioning

## Usage

### Basic Usage

```python
from app.database.query_engine.rbac import RBACValidator
from app.models.users import User

# Initialize validator
validator = RBACValidator(redis_client, db_client)

# Validate access (raises PermissionError if denied)
user = User(id="user1", name="Test", email="test@test.com", roles=["user"])
validator.validate_access("cells", user)

# Check access without raising
if validator.check_canonical_access("templates", user):
    # Access granted
    pass
```

### 3-Tier Access Checks

```python
# Check sandbox access (owner-based)
has_access = validator.check_sandbox_access(
    resource_owner_id="user123",
    current_user=user
)

# Check canonical access (role-based)
has_access = validator.check_canonical_access(
    collection="templates",
    current_user=user
)

# Check runtime access (permission-based)
has_access = validator.check_runtime_access(
    collection="notebook_items",
    current_user=user
)
```

### Permission Caching

Permissions are automatically cached in Redis for 5 minutes:

```python
# Permissions are cached on first access
perms = validator._get_user_permissions(user)

# Invalidate cache after user role change
validator.invalidate_user_permissions("user123")

# Invalidate all caches after role definition change
validator.invalidate_all_permissions()
```

## Role Definitions

Roles are defined in JSON files in `artifacts/canonical/roles/`:

### Admin Role
- Has wildcard permission (`*`)
- Bypasses all access checks
- Full system access

### Editor Role
- Can manage templates and workflows
- Can read canonical data
- Can manage own cells and books

### Viewer Role
- Read-only access to public collections
- Cannot modify any data

### User Role (Standard)
- Can manage own cells and books
- Can use AI models
- Cannot access other users' data

## Permission Format

Permissions follow the format: `{collection}.{action}`

Examples:
- `cells.read` - Can read cells
- `templates.write` - Can write templates
- `canonical.read` - Can read all canonical data
- `sandbox.read_any` - Can read any user's sandbox
- `*` - Wildcard (admin only)

## Error Handling

### TypeError

Raised when `current_user` is missing or wrong type:

```python
# Missing user
validator.validate_access("cells", None)
# Raises: TypeError: current_user parameter is required

# Wrong type
validator.validate_access("cells", "not_a_user")
# Raises: TypeError: current_user must be User type
```

### PermissionError

Raised when user lacks permission:

```python
user = User(id="user1", name="Test", email="test@test.com", roles=[])
validator.validate_access("private_collection", user)
# Raises: PermissionError: User 'user1' lacks permission to access collection 'private_collection'
```

## Redis Integration

The RBAC validator supports optional Redis caching:

- If Redis is available, permissions are cached for 5 minutes
- If Redis is unavailable, falls back to DB lookup on every check
- Redis failures are logged but don't break functionality

**Note**: The current implementation uses synchronous Redis methods. When integrating with the async Redis client, either:
1. Use a synchronous Redis client (e.g., `redis.Redis`)
2. Make RBAC methods async and use `await` for Redis calls

## Testing

Comprehensive test suite with 47 test cases covering:
- Basic validation (TypeError handling)
- Public collection access
- Admin role bypass
- Permission checking
- 3-tier access control
- Permission caching
- Cache invalidation
- Role-based permission resolution
- Redis failure handling

Run tests:
```bash
cd backend
poetry run pytest ../tests/unit/backend/query_engine/test_rbac.py -v
```

## Dependencies

- `backend.app.models.users.User` - User model with roles and permissions
- `backend.app.database.connection.JSONDatabase` - Database client
- `redis` (optional) - For permission caching

## Integration with Query Engine

The RBAC validator should be integrated into the HybridDatabase class:

```python
class HybridDatabase:
    def __init__(self, ...):
        self.rbac = RBACValidator(redis_client, db_client)
    
    async def find(self, collection: str, query: dict, current_user: User):
        # Validate access first
        self.rbac.validate_access(collection, current_user)
        
        # Then execute query
        return await self._execute_query(collection, query)
```

## Next Steps

1. Integrate with HybridDatabase class (Sub-Issue 1.6)
2. Add write permission checks (create/update/delete)
3. Add field-level permissions (optional)
4. Add audit logging for access denials
5. Add permission management API endpoints

## References

- Issue: Sub-Issue 1.4 - RBAC Infrastructure
- Parent Epic: database-unified-rbac-access
- Dependencies: Sub-Issue 1.1 (Query Engine Foundation)
