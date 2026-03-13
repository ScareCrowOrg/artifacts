---
processed: true
processed_date: 2025-12-08
themes:
  - architecture
  - backend
  - modules
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Models Module - Data Schemas and Adapters

This module defines all Pydantic data models (schemas) for the ScareVerse backend, including adapters for pipeline execution.

## Index

### Files
- `__init__.py` - Module exports
- `adapters.py` - Adapter pattern implementations for pipeline execution
- `agents.py` - Agent and agent type models
- `ai_models.py` - AI model configuration schemas (ModeloIA)
- `artifacts.py` - Canonical and instantiated artifact models
- `auth.py` - Authentication and authorization schemas
- `base.py` - Base models and shared utilities
- `chat.py` - Chat and messaging schemas
- `content.py` - Content models (TipoCelula, Celula, Livro)
- `interfaces.py` - Interface definitions for adapters
- `oauth_config.py` - OAuth configuration schemas
- `permissions.py` - **NEW** RBAC permission models (Permission, Role, UserRole)
- `sessions.py` - Session management models
- `users.py` - User models (now includes roles field for RBAC)

### Documentation
- [README_OLD.md](./README_OLD.md) - Detailed architecture documentation (legacy reference)

## Quick Reference

### New Architecture (Composition Pattern)

**Before (Old - Inheritance):**
```python
# PipelineItem inherited from NotebookItem ❌
item = PipelineItem(
    assignee_id="user-123",
    cell_id="cell-123",
    cell_type_id="type-456"
)
```

**After (New - Composition):**
```python
# PipelineItem COMPOSES NotebookItem ✅
celula = Celula(assignee_id="user-123", tipoCelulaId="type-456")
item = PipelineItem(
    assignee_id=celula.assignee_id,
    notebook_item_id=celula.id,
    notebook_item_data=celula,  # Direct reference
    cell_id=celula.id,
    cell_type_id=celula.tipoCelulaId
)
```

### Execution Flow with Adapters

```python
from app.models import Celula, CellAdapter
from app.core.models import PipelineItem

# 1. Create pure data model
celula = Celula(assignee_id="user-123", tipoCelulaId="ingestion-type")

# 2. Create adapter
adapter = CellAdapter(cell=celula)

# 3. Create execution context
pipeline_item = PipelineItem(
    notebook_item_id=celula.id,
    notebook_item_data=celula,
    cell_id=celula.id,
    cell_type_id=celula.tipoCelulaId,
    assignee_id=celula.assignee_id
)

# 4. Execute
result = adapter.execute_in_pipeline(pipeline_item)
```

## Architecture Overview

```
Pure Data Models (NotebookItem, Celula, Livro)
        ↓
Adapters (CellAdapter, BookAdapter) implement IPipelineExecutable
        ↓
PipelineItem composes NotebookItem + manages execution state
        ↓
Workflow Executor uses IPipelineExecutable interface
```

See [README_OLD.md](./README_OLD.md) for full documentation.

## Tests

### Running Tests

```bash
# Run all model tests
pytest tests/unit/backend/ -k "model" -v

# Run with coverage
pytest tests/unit/backend/ -k "model" --cov=app/models --cov-report=html
```

### Test Coverage

The models module has comprehensive unit tests covering:
- Model validation and constraints
- Adapter pattern implementations
- Data transformation and serialization
- Error handling for invalid data

**Current Coverage**: See `/backend/coverage.json`

**Target**: 90% minimum coverage

### Test Files

- `tests/unit/backend/test_models.py` - Model validation tests
- `tests/unit/backend/test_adapters.py` - Adapter pattern tests

### Related Documentation

- [Unit Tests README](../../tests/unit/backend/README.md)
- [Test Architecture](../../../docs/ARQUITETURA_TESTES.md)

---

## RBAC (Role-Based Access Control) System

**Added**: Sprint 1.1 - November 2025  
**Status**: Foundation Complete

### Overview

ScareVerse now implements a comprehensive RBAC system for fine-grained permission control. The system consists of three core models working together to provide flexible authorization:

1. **Permission**: Granular permissions for specific resources and actions
2. **Role**: Named collections of permissions
3. **UserRole**: Association between users and roles (audit trail)

### Models

#### Permission

Represents a granular permission for a specific resource and action.

```python
from app.models.permissions import Permission

# Example: Permission to create cells
permission = Permission(
    name="cells.create",
    description="Create new cells",
    resource="cells",
    action="create",
    scope=None  # No scope restriction
)

# Example: Permission to read own cells
permission_own = Permission(
    name="cells.read_own",
    description="Read own cells",
    resource="cells",
    action="read",
    scope="own"
)

# Example: Permission to delete any user's cells (admin)
permission_any = Permission(
    name="cells.delete_any",
    description="Delete any user's cells",
    resource="cells",
    action="delete",
    scope="any"
)
```

**Permission Naming Convention**: `{resource}.{action}[_{scope}]`

**Supported Resources**:
- `cells` - Document/artifact cells
- `books` - Collections of cells
- `users` - User management
- `system` - System administration
- `ai_models` - AI model configuration

**Supported Actions**:
- `create`, `read`, `update`, `delete` - CRUD operations
- `use` - Use a resource (e.g., AI models)
- `configure` - Configure a resource
- `manage` - Full management (users, roles)
- `view_logs` - View system logs

**Supported Scopes**:
- `None` - No scope restriction (applies to all)
- `own` - Applies only to user's own resources
- `any` - Applies to any user's resources (admin-level)

#### Role

Represents a named collection of permissions with a priority level.

```python
from app.models.permissions import Role, RoleEnum

# Example: Admin role with all permissions
admin_role = Role(
    name=RoleEnum.ADMIN,
    description="Administrator with full system access",
    permissions=["*"],  # Wildcard grants all permissions
    priority=100
)

# Example: User role with standard permissions
user_role = Role(
    name=RoleEnum.USER,
    description="Standard user",
    permissions=[
        "cells.create",
        "cells.read_own",
        "cells.update_own",
        "cells.delete_own",
        "books.create",
        "ai_models.use"
    ],
    priority=10
)
```

**Available Roles** (RoleEnum):
- `ADMIN` (priority=100): Full system access
- `USER` (priority=10): Standard user permissions
- `VIEWER` (priority=5): Read-only access
- `GUEST` (priority=1): Minimal/no permissions

**Priority**: Higher number = more powerful. Used for permission resolution in conflicts.

#### UserRole

Represents an association between a user and a role, with audit trail.

```python
from app.models.permissions import UserRole

# Example: Assign admin role to user
user_role = UserRole(
    userId="user-123",
    roleId="role-admin-456",
    assignedBy="admin-789"  # Who assigned the role
)

# assignedAt is automatically set to current timestamp
print(user_role.assignedAt)  # 2025-11-25 22:00:00
```

#### Usuario (Updated)

The existing Usuario model now includes a `roles` field for RBAC integration.

```python
from app.models.users import Usuario

# New users automatically get 'user' role
usuario = Usuario(
    nome="Test User",
    email="test@example.com"
)
print(usuario.roles)  # ["user"]

# Admin users can have multiple roles
admin = Usuario(
    nome="Admin User",
    email="admin@example.com",
    roles=["admin", "user"]
)
print(admin.roles)  # ["admin", "user"]
```

### Database Collections

RBAC data is stored in the following collections:

- `artifacts/canonical/permissions/` - Permission documents
- `artifacts/canonical/roles/` - Role documents
- `artifacts/runtime/usuarios/` or `artifacts/canonical/usuarios/` - User documents (with roles field)

### Seed and Migration Scripts

#### Seed Permissions and Roles

Populate the database with initial permissions and roles:

```bash
cd backend
python -m scripts.seed_permissions
```

This creates:
- ~20 permissions covering all resources
- 4 roles: admin, user, viewer, guest

**Idempotent**: Can be run multiple times safely without creating duplicates.

#### Migrate Users

Add roles field to existing users:

```bash
cd backend
python -m scripts.migrate_user_roles
```

This:
- Adds `roles` field to users without it
- Assigns "admin" role to user with email matching `ADMIN_EMAIL` env var
- Assigns "user" role to all other users

**Idempotent**: Can be run multiple times safely, skips users who already have roles.

### Configuration

Set the admin email in environment variables:

```bash
# .env
ADMIN_EMAIL=admin@scareverse.com
```

Or in `backend/app/config.py`:

```python
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@scareverse.com")
```

### Permission Mapping

| Role | Permissions | Priority |
|------|------------|----------|
| **admin** | `["*"]` (all permissions) | 100 |
| **user** | `cells.*_own`, `books.*_own`, `users.read_own`, `ai_models.use` | 10 |
| **viewer** | `cells.read_any`, `books.read_any`, `users.read_own` | 5 |
| **guest** | `[]` (no permissions) | 1 |

### Usage Examples

#### Check if User Has Permission

```python
from app.models.users import Usuario
from app.models.permissions import Role

def user_has_permission(usuario: Usuario, permission_name: str, roles: list[Role]) -> bool:
    """Check if user has a specific permission."""
    user_roles = [r for r in roles if r.name.value in usuario.roles]
    
    for role in user_roles:
        # Admin role has wildcard
        if "*" in role.permissions:
            return True
        
        # Check specific permission
        if permission_name in role.permissions:
            return True
    
    return False

# Example usage
usuario = Usuario(nome="Test", email="test@example.com", roles=["user"])
# Assume roles are fetched from database
has_create = user_has_permission(usuario, "cells.create", roles)
```

#### Assign Role to User

```python
from app.models.permissions import UserRole
from app.database import db

def assign_role_to_user(user_id: str, role_id: str, assigned_by: str):
    """Assign a role to a user."""
    user_role = UserRole(
        userId=user_id,
        roleId=role_id,
        assignedBy=assigned_by
    )
    
    # Save to database
    db.insert("user_roles", user_role, is_canonical=True)
    
    return user_role
```

### Testing

Run RBAC tests:

```bash
# Unit tests for models
pytest backend/tests/unit/test_permissions_models.py -v

# Integration tests for scripts
pytest backend/tests/integration/test_seed_permissions.py -v

# With coverage
pytest backend/tests/unit/test_permissions_models.py \
       backend/tests/integration/test_seed_permissions.py \
       --cov=app/models/permissions \
       --cov=scripts/seed_permissions \
       --cov=scripts/migrate_user_roles \
       --cov-report=html
```

**Coverage Target**: ≥90%

### Next Steps (Future Sprints)

1. **Sprint 1.2**: Implement authorization middleware and decorators
2. **Sprint 1.3**: Add permission checking to API endpoints
3. **Sprint 1.4**: Create admin UI for role management
4. **Sprint 2.x**: Implement attribute-based access control (ABAC) for advanced scenarios

### References

- [PERMISSION_CONTROL_SURVEY.md](../../../docs/PERMISSION_CONTROL_SURVEY.md) - Complete RBAC survey
- [RULESET.md](../../../RULESET.md) - Project rules and conventions
- [Backend README](../../README.md) - Backend architecture overview
