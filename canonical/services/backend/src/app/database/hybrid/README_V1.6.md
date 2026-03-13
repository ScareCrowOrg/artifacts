---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/backend/architecture/hybrid-database-rbac-api.md
themes:
  - database
  - rbac
  - architecture
  - breaking-changes
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# HybridDatabase - RBAC-Mandatory API (Sub-Issue 1.6)

## ⚠️ BREAKING CHANGES (v1.6.0)

**ALL methods now require `current_user` parameter for RBAC enforcement.**

This is an **intentional breaking change** to enforce security compliance across all endpoints.

### What Changed

#### Before (Old API - DEPRECATED)
```python
# ❌ OLD API (NO LONGER WORKS)
await db.find_one("templates", "tpl-123")
await db.find_many("templates")
await db.insert("templates", template_doc)
```

#### After (New API - REQUIRED)
```python
# ✅ NEW API (MANDATORY)
user = User(id="user1", roles=["admin"])

await db.find_one("templates", "tpl-123", current_user=user)
await db.find_many("templates", current_user=user)
await db.insert("templates", template_doc, current_user=user)
```

### Migration Guide

**Step 1**: Add `current_user` parameter to all HybridDatabase calls

**Step 2**: Handle TypeErrors and PermissionErrors

```python
try:
    result = await db.find_one("templates", "tpl-123", current_user=user)
except TypeError as e:
    # Missing or invalid current_user parameter
    logger.error(f"Invalid user parameter: {e}")
except PermissionError as e:
    # User lacks access to collection
    logger.warning(f"Access denied: {e}")
```

**Step 3**: Update endpoint handlers to pass `current_user`

```python
# In FastAPI endpoints
@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user),  # ← Get from auth
    db: HybridDatabase = Depends(get_db)
):
    template = await db.find_one(
        "templates",
        template_id,
        current_user=current_user  # ← Pass to database
    )
    return template
```

---

## Features (Sub-Issue 1.6)

### 1. RBAC-Mandatory Access Control

All methods validate user permissions before data access:

```python
# Public collections (always accessible)
PUBLIC_COLLECTIONS = {
    "notebook_item_types", "templates", "workflows",
    "permissions", "roles", "ai_models", "content_types",
    "agent_types", "book_types"
}

# Admin role (full access)
user = User(id="admin1", roles=["admin"])

# Collection-specific permission
user = User(id="user1", permissions=["templates.read"])

# Canonical read permission
user = User(id="user1", permissions=["canonical.read"])
```

### 2. Multi-Source Search

Searches across 3 tiers with precedence rules:

```python
results = await db.find(
    "templates",
    {"status": "published"},
    current_user=user,
    resource_owner_id="user123",  # Optional: search sandbox too
)

# Precedence: Sandbox > Canonical > Runtime
# - Sandbox: user-private data (if resource_owner_id provided)
# - Canonical: blueprint/schema data (file-based)
# - Runtime: operational data (MongoDB/CentralHub)
```

### 3. Cache Invalidation

Write operations automatically invalidate caches:

```python
# Insert to sandbox → invalidates SandboxQueryEngine schema cache
await db.insert(
    "templates",
    template_doc,
    current_user=user,
    resource_owner_id="user123"
)
# ↓ Automatically invalidates sandbox schema cache

# Insert to runtime → invalidates L1 Redis cache
await db.insert(
    "notebook_items",
    item_doc,
    current_user=user
)
# ↓ Automatically invalidates L1 Redis query cache
```

### 4. Complex Query Support

Supports MongoDB operators:

```python
# Comparison operators
results = await db.find(
    "templates",
    {"level": {"$gte": 5, "$lte": 10}},
    current_user=user
)

# Logical operators
results = await db.find(
    "templates",
    {
        "$or": [
            {"status": "published"},
            {"status": "featured"}
        ]
    },
    current_user=user
)

# Array operators
results = await db.find(
    "templates",
    {"tags": {"$all": ["featured", "premium"]}},
    current_user=user
)
```

---

## API Reference

### find_one()

Find single document by ID with RBAC + multi-source search.

```python
async def find_one(
    collection: str,
    doc_id: str,
    current_user: User,  # ← MANDATORY
    model_class: Optional[Type[T]] = None,
    resource_owner_id: Optional[str] = None,
) -> Optional[T]
```

**Parameters:**
- `collection`: Collection name (e.g., "templates", "notebook_items")
- `doc_id`: Document ID
- `current_user`: User making request (MANDATORY)
- `model_class`: Pydantic model class for deserialization (optional)
- `resource_owner_id`: Resource owner ID for sandbox access check (optional)

**Returns:** Document instance or None if not found

**Raises:**
- `TypeError`: If current_user is missing or wrong type
- `PermissionError`: If user lacks access to collection

**Example:**
```python
user = User(id="user1", roles=["admin"])
template = await db.find_one("templates", "tpl-123", current_user=user)
```

### find_many()

Find multiple documents with RBAC + multi-source search.

```python
async def find_many(
    collection: str,
    current_user: User,  # ← MANDATORY
    query: Optional[Dict] = None,
    limit: Optional[int] = None,
    model_class: Optional[Type[T]] = None,
) -> List[T]
```

**Parameters:**
- `collection`: Collection name
- `current_user`: User making request (MANDATORY)
- `query`: Query filter (default: {})
- `limit`: Maximum number of documents to return (optional)
- `model_class`: Pydantic model class for deserialization (optional)

**Returns:** List of document instances

**Raises:**
- `TypeError`: If current_user is missing or wrong type
- `PermissionError`: If user lacks access to collection

**Example:**
```python
user = User(id="user1", roles=["admin"])
templates = await db.find_many(
    "templates",
    current_user=user,
    query={"status": "published"},
    limit=10
)
```

### find()

Find with complex query, RBAC, and multi-source search.

```python
async def find(
    collection: str,
    query: Dict,
    current_user: User,  # ← MANDATORY
    limit: Optional[int] = None,
    resource_owner_id: Optional[str] = None,
) -> List[Dict]
```

**Parameters:**
- `collection`: Collection name
- `query`: MongoDB-style query dict
- `current_user`: User making request (MANDATORY)
- `limit`: Maximum number of documents to return (optional)
- `resource_owner_id`: Resource owner ID for sandbox access (optional)

**Returns:** List of matching documents (as dicts)

**Raises:**
- `TypeError`: If current_user is missing or wrong type
- `PermissionError`: If user lacks access to collection

**Example:**
```python
user = User(id="user1", roles=["admin"])
templates = await db.find(
    "templates",
    {
        "status": "published",
        "level": {"$gte": 5},
        "$or": [{"featured": True}, {"premium": True}]
    },
    current_user=user,
    limit=10
)
```

### insert()

Unified insert with RBAC and cache invalidation.

```python
async def insert(
    collection: str,
    document: Dict,
    current_user: User,  # ← MANDATORY
    resource_owner_id: Optional[str] = None,
) -> str
```

**Parameters:**
- `collection`: Collection name
- `document`: Document to insert (dict)
- `current_user`: User making request (MANDATORY)
- `resource_owner_id`: Resource owner ID for sandbox insert (optional)

**Returns:** Inserted document ID

**Raises:**
- `TypeError`: If current_user is missing or wrong type
- `PermissionError`: If user lacks access to collection

**Example:**
```python
user = User(id="user1", roles=["admin"])
doc_id = await db.insert(
    "templates",
    {"name": "New Template", "status": "draft"},
    current_user=user
)
```

### update()

Unified update with RBAC and cache invalidation.

```python
async def update(
    collection: str,
    doc_id: str,
    updates: Dict,
    current_user: User,  # ← MANDATORY
    resource_owner_id: Optional[str] = None,
) -> bool
```

**Parameters:**
- `collection`: Collection name
- `doc_id`: Document ID
- `updates`: Dictionary of field updates
- `current_user`: User making request (MANDATORY)
- `resource_owner_id`: Resource owner ID for sandbox update (optional)

**Returns:** True if update successful, False otherwise

**Raises:**
- `TypeError`: If current_user is missing or wrong type
- `PermissionError`: If user lacks access to collection

**Example:**
```python
user = User(id="user1", roles=["admin"])
success = await db.update(
    "templates",
    "tpl-123",
    {"status": "published"},
    current_user=user
)
```

### delete()

Unified delete with RBAC and cache invalidation.

```python
async def delete(
    collection: str,
    doc_id: str,
    current_user: User,  # ← MANDATORY
    resource_owner_id: Optional[str] = None,
) -> bool
```

**Parameters:**
- `collection`: Collection name
- `doc_id`: Document ID
- `current_user`: User making request (MANDATORY)
- `resource_owner_id`: Resource owner ID for sandbox delete (optional)

**Returns:** True if delete successful, False otherwise

**Raises:**
- `TypeError`: If current_user is missing or wrong type
- `PermissionError`: If user lacks access to collection

**Example:**
```python
user = User(id="user1", roles=["admin"])
success = await db.delete("templates", "tpl-123", current_user=user)
```

---

## Supported Collections

**All 11 collections** are supported (from Sub-Issue 1.6 spec):

1. `permissions` - Permission definitions
2. `cells` - Cell instances (legacy, routed to notebook_items)
3. `books` - Book instances (legacy, routed to notebook_items)
4. `ai_models` - AI model configurations
5. `content_types` - Content type schemas
6. `notebook_items` - Unified cell/book collection
7. `contents` - Generated content (images, assets)
8. `templates` - Template blueprints
9. `roles` - Role definitions
10. `workflows` - Workflow definitions
11. `notebook_item_types` - Cell and book type definitions

---

## Architecture

```
HybridDatabase (Sub-Issue 1.6)
├── RBAC Validation (Sub-Issue 1.4)
│   ├── validate_access() - Mandatory for all operations
│   ├── check_sandbox_access() - Owner or admin
│   ├── check_canonical_access() - Public or role-based
│   └── check_runtime_access() - Permission-based
├── Query Engines (Sub-Issues 1.1-1.3)
│   ├── CanonicalQueryEngine - Schema-aware SQLite (Sub-Issue 1.2)
│   ├── SandboxQueryEngine - Dynamic schema inference (Sub-Issue 1.3)
│   └── MongoDBOperations - Direct MongoDB access
├── Cache Manager (Sub-Issue 1.5)
│   ├── L1 Redis caching - Query result caching
│   └── Cache invalidation - On writes
└── Multi-Source Search
    ├── Sandbox tier - User-private data
    ├── Canonical tier - Blueprint/schema data
    └── Runtime tier - Operational data (MongoDB/CentralHub)
```

---

## Performance

- Multi-source query: **<100ms** target
- L1 Redis cache: **5 min TTL**
- Schema cache: **1 hour TTL** (sandbox)
- Permission cache: **5 min TTL** (RBAC)

---

## Testing

See `backend/tests/unit/backend/database/test_hybrid_database_rbac.py` for comprehensive test suite:

- ✅ current_user mandatory validation (TypeError)
- ✅ RBAC permission checks (PermissionError)
- ✅ Multi-source search and merging
- ✅ Cache invalidation on writes
- ✅ Sandbox access control
- ✅ Public collection access
- ✅ Complex query support (MongoDB operators)
- ✅ Performance (<100ms target)

**Coverage Target:** >90% for critical paths

---

## Dependencies

- Sub-Issue 1.1: Query Engine Foundation
- Sub-Issue 1.2: CanonicalQueryEngine
- Sub-Issue 1.3: SandboxQueryEngine
- Sub-Issue 1.4: RBAC Infrastructure
- Sub-Issue 1.5: Cache Manager

---

## Next Steps (Phase 2)

After this breaking change, **Phase 2 must start immediately** to fix affected endpoints:

- Sub-Issue 2.1: Audit All Endpoints
- Sub-Issue 2.2: Fix Critical Endpoints (Batch 1)
- Sub-Issue 2.3: Fix Remaining Endpoints (Batch 2)

**Timeline:** ~1 week sprint to unblock application

---

## Version History

- **v1.6.0** (2026-02-24): BREAKING - RBAC-mandatory API
  - All methods require `current_user` parameter
  - Multi-source search with precedence rules
  - Cache invalidation integration
  - Support for all 11 collections

- **v1.5.0** (Phase 1B): Sandbox operations + unified L1 cache
- **v1.0.0**: Initial hybrid database router

---

**Status:** ⚠️ BREAKING CHANGE - Application will break until Phase 2 completes  
**Created:** 2026-02-24  
**Last Updated:** 2026-02-24
