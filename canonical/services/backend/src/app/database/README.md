---
processed: true
processed_date: 2025-12-08
themes:
  - backend
  - database
  - architecture
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Database Module

MongoDB-based database layer for ScareVerse backend, providing document storage, caching, and encryption utilities.

## Configuration

All database-related configuration (MongoDB, Redis, paths) is centralized in the **[Configuration Module](../config/README.md)**.

See [`backend/app/config/database.py`](../config/database.py) for:
- MongoDB connection settings (host, port, database, credentials)
- Redis connection and cache settings (host, port, TTL values)
- Path configuration (ARTIFACTS_DIR, CANONICAL_DIR, RUNTIME_DIR)
- Collection-specific settings and TTL mappings
- Configuration validation functions

**Important**: Always import database configuration from `app.config.database` to maintain centralization (RULESET.md Rule 4.1):

```python
from app.config.database import (
    MONGODB_CONFIG,
    REDIS_CONFIG,
    ARTIFACTS_DIR,
    get_mongodb_uri,
    get_cache_ttl
)
```

## Index

### Files
- `__init__.py` - Module exports and database instance management
- `connection.py` - MongoDB connection and initialization
- `operations.py` - CRUD operations (insert, find, update, delete, queries)
- `config_ops.py` - Configuration get/set operations
- `encryption.py` - Encryption/decryption of sensitive fields (API keys)
- `redis_cache.py` - Redis cache facade with lazy loading and invalidation

## Purpose

Database layer for ScareVerse with MongoDB document storage and optional Redis caching for optimized read performance.

## File Index

| File | Lines | Description |
|------|-------|-------------|
| `__init__.py` | 17 | Module exports (JSONDatabase, RedisCachedJSONDatabase, get_db_instance, db) |
| `connection.py` | 208 | Core JSONDatabase class, initialization, path management |
| `operations.py` | 395 | CRUD operations (insert, find, update, delete, queries) |
| `config_ops.py` | 69 | Configuration get/set operations |
| `encryption.py` | 100 | Encryption/decryption of sensitive fields (API keys) |
| `redis_cache.py` | 550 | Redis cache facade with lazy loading and smart invalidation |
| `README.md` | This file | Module documentation |

**Total**: ~1339 lines across 7 files (modularized for maintainability)

## Architecture

### Storage Structure

```
artifacts/
├── runtime/              # Runtime artifacts (user-specific data)
│   ├── cells/
│   │   └── {usuario_id}/
│   │       └── {sessao_id}/
│   │           └── {id}.json
│   ├── books/
│   ├── memoria/
│   ├── usuarios/
│   └── sessoes/
├── canonical/            # Canonical artifacts (shared resources)
│   ├── cells/
│   │   └── {id}.json
│   ├── books/
│   ├── templates/
│   ├── cell_types/
│   └── ai_models/
└── config/               # Configuration files
    └── {key}.json
```

**Note**: Directory names use English (e.g., `artifacts/canonical/books`), but MongoDB collection names 
and API endpoints retain Portuguese names (e.g., `livros`, `/api/celulas`) for API contract stability.

### Class Hierarchy

```
JSONDatabase
├── CRUDOperations (operations.py)
│   ├── insert()
│   ├── find_one()
│   ├── find_many()
│   ├── find_by_field()
│   ├── find_by_fields()
│   ├── update()
│   └── delete()
└── ConfigOperations (config_ops.py)
    ├── get_config()
    └── set_config()

RedisCachedJSONDatabase (extends JSONDatabase)
├── Async Read Operations (redis_cache.py)
│   ├── find_one_async()      # Cached read
│   ├── find_many_async()     # Cached list read
│   ├── find_by_field_async() # Cached field query
│   └── find_by_fields_async() # Cached multi-field query
├── Async Write Operations (redis_cache.py)
│   ├── insert_async()  # Write + invalidate cache
│   ├── update_async()  # Write + invalidate cache
│   └── delete_async()  # Write + invalidate cache
└── Cache Management
    ├── _get_cache_key()           # Generate unique cache keys
    ├── _get_ttl()                 # Collection-specific TTL
    ├── _invalidate_cache_pattern() # Pattern-based invalidation
    └── _invalidate_collection_cache() # Smart invalidation
```

## Redis Caching Layer

### Overview

The `RedisCachedJSONDatabase` class provides an optional caching layer that wraps `JSONDatabase` to optimize read operations. When enabled, it uses Redis for lazy loading with TTL-based caching while maintaining JSONDatabase as the source of truth for all writes.

### Key Features

1. **Lazy Loading**: Data is cached on first read, subsequent reads hit cache
2. **Smart Invalidation**: Write operations invalidate related cache entries
3. **Configurable TTL**: Different TTL values per collection type
4. **Graceful Degradation**: Falls back to direct disk access if Redis is unavailable
5. **Async Operations**: All cache operations are async for high performance

### Cache Strategy

#### Read Operations
1. Check Redis cache for data
2. If cache hit → return cached data (fast path)
3. If cache miss → load from disk via JSONDatabase
4. Store result in Redis with appropriate TTL
5. Return data

#### Write Operations
1. Persist to disk via JSONDatabase (source of truth)
2. Invalidate related cache entries using pattern matching
3. Next read will cache fresh data from disk

### Configuration

Configure caching via environment variables (see `.env.example`):

```bash
# Enable Redis for event streaming and caching
REDIS_ENABLED=true
REDIS_CACHE_ENABLED=true

# Redis connection
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Cache TTL (seconds)
REDIS_CACHE_TTL=3600              # Default: 1 hour
REDIS_CACHE_TTL_CELULAS=1800      # Celulas: 30 minutes
REDIS_CACHE_TTL_LIVROS=1800       # Livros: 30 minutes
REDIS_CACHE_TTL_CONFIG=300        # Config: 5 minutes
REDIS_CACHE_TTL_CANONICAL=7200    # Canonical: 2 hours
```

## Usage

### Basic Operations (JSONDatabase)

```python
from app.database import JSONDatabase, get_db_instance
from app.models import Celula

# Get database instance (runtime)
db = get_db_instance()

# Insert document
celula = Celula(id="cel_123", nome="Test Cell", tipo="code")
db.insert("celulas", celula, usuario_id="user_1", sessao_id="sess_1")

# Find document
found = db.find_one("celulas", "cel_123", Celula, 
                    usuario_id="user_1", sessao_id="sess_1")

# Update document
db.update("celulas", "cel_123", {"nome": "Updated Cell"}, 
          usuario_id="user_1", sessao_id="sess_1")

# Delete document
db.delete("celulas", "cel_123", usuario_id="user_1", sessao_id="sess_1")
```

### Cached Operations (RedisCachedJSONDatabase)

```python
from app.database import RedisCachedJSONDatabase
from app.models import Celula

# Create cached database instance
cached_db = RedisCachedJSONDatabase()

# Async operations with caching
async def cached_operations():
    # Find with cache - first call caches result
    celula = await cached_db.find_one_async(
        "celulas", "cel_123", Celula,
        usuario_id="user_1", sessao_id="sess_1"
    )
    
    # Second call hits cache (fast)
    celula_cached = await cached_db.find_one_async(
        "celulas", "cel_123", Celula,
        usuario_id="user_1", sessao_id="sess_1"
    )
    
    # Find many with cache
    all_celulas = await cached_db.find_many_async(
        "celulas", Celula, usuario_id="user_1"
    )
    
    # Insert invalidates related cache entries
    new_celula = Celula(
        id="cel_456", nome="New Cell", tipo="code"
    )
    await cached_db.insert_async(
        "celulas", new_celula, 
        usuario_id="user_1", sessao_id="sess_1"
    )
    
    # Update invalidates cache - next read gets fresh data
    await cached_db.update_async(
        "celulas", "cel_123", {"nome": "Updated"},
        usuario_id="user_1", sessao_id="sess_1"
    )
    
    # Delete invalidates cache
    await cached_db.delete_async(
        "celulas", "cel_456",
        usuario_id="user_1", sessao_id="sess_1"
    )

# Run async operations
import asyncio
asyncio.run(cached_operations())
```

### Synchronous Fallback

The cached database extends JSONDatabase, so all synchronous operations still work:

```python
cached_db = RedisCachedJSONDatabase()

# Sync operations bypass cache (direct disk access)
celula = cached_db.find_one("celulas", "cel_123", Celula)
cached_db.insert("celulas", celula)
```

### Canonical Artifacts

```python
# Insert canonical artifact (no user/session)
db.insert("tipos_celula", tipo_celula, is_canonical=True)

# Find canonical artifact
tipo = db.find_one("tipos_celula", "tipo_code", TipoCelula, is_canonical=True)
```

### Query Operations

```python
# Find all documents
all_celulas = db.find_many("celulas", Celula, usuario_id="user_1")

# Find by single field
celula = db.find_by_field("celulas", "nome", "Test Cell", Celula)

# Find by multiple fields
celula = db.find_by_fields("celulas", 
                           {"nome": "Test", "tipo": "code"}, 
                           Celula)
```

### Configuration Management

```python
# Set configuration
db.set_config("oauth", {
    "google_client_id": "xxx",
    "enabled": True
})

# Get configuration
config = db.get_config("oauth")
```

### Testing

The database module has comprehensive test coverage to ensure reliability and correctness.

#### Test Coverage Metrics

| Module | Statements | Coverage | Status |
|--------|------------|----------|--------|
| `__init__.py` | 3 | 100% | ✅ |
| `config_ops.py` | 28 | 89% | ✅ |
| `connection.py` | 65 | 95% | ✅ |
| `database_router.py` | 0 | 100% | ✅ |
| `encryption.py` | 36 | 92% | ✅ |
| `operations.py` | 107 | 93% | ✅ |
| `redis_cache.py` | 183 | 91% | ✅ |
| **TOTAL** | **422** | **92%** | ✅ |

**Test Statistics:**
- Total Tests: 122
- Test Execution Time: < 2 minutes
- All tests passing ✅

#### Running Tests

```bash
# Run all database tests
pytest tests/unit/backend/database/ -v

# Run with coverage report
pytest tests/unit/backend/database/ --cov=app/database --cov-report=term-missing

# Run specific test file
pytest tests/unit/backend/database/test_operations.py -v
```

#### Test Files

- `tests/unit/backend/database/conftest.py` - Shared fixtures and test utilities
- `tests/unit/backend/database/test_connection.py` - Path management and initialization tests
- `tests/unit/backend/database/test_operations.py` - CRUD operations tests
- `tests/unit/backend/database/test_config_ops.py` - Configuration management tests
- `tests/unit/backend/database/test_encryption.py` - Encryption/decryption tests
- `tests/unit/backend/database/test_redis_cache.py` - Redis caching layer tests

#### Test Example

```python
import pytest
from pathlib import Path
import tempfile
from app.database import JSONDatabase

@pytest.fixture
def test_db():
    """Create temporary test database."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db = JSONDatabase(base_path=Path(temp_dir), is_test_env=True)
        yield db
        db.cleanup_test_data()

def test_insert(test_db):
    celula = Celula(id="test_1", nome="Test")
    doc_id = test_db.insert("celulas", celula, is_canonical=True)
    assert doc_id == "test_1"
```

#### Testing Strategy

1. **Unit Tests**: Test each CRUD operation in isolation
2. **Persistence Tests**: Use `mongomock` for database simulation (no real MongoDB required)
3. **Cache Tests**: Mock Redis client for testing cache layer without external dependencies
4. **Error Handling**: Test graceful degradation and error scenarios
5. **Edge Cases**: Test boundary conditions, corrupted data, and race conditions

## Security Features

### Encryption

Sensitive fields (e.g., API keys in `modelos_ia` collection) are automatically encrypted on write and decrypted on read.

- **Encryption Key**: Set `ENCRYPTION_KEY` environment variable
- **Algorithm**: Fernet symmetric encryption (cryptography library)
- **Fields**: Currently encrypts `apiKey` field in `modelos_ia` collection

```python
# Automatic encryption/decryption
modelo = ModeloIA(id="gemini_1", nome="Gemini", apiKey="secret_key")
db.insert("modelos_ia", modelo, is_canonical=True)  # apiKey encrypted

# On retrieval, apiKey is automatically decrypted
retrieved = db.find_one("modelos_ia", "gemini_1", ModeloIA, is_canonical=True)
# retrieved.apiKey = "secret_key" (decrypted)
```

### Path Security

- All paths validated and sanitized
- No directory traversal allowed
- Scoped to `base_path` directory

## Environment Modes

### Runtime Mode (Production/Development)

```python
# Automatic initialization
from app.database import db

# Uses SCAREFERA_LAB_DIR/artifacts
```

### Test Mode

```python
# Set environment variable
os.environ["TEST_ENV"] = "true"

# Use fixture-provided instance
from app.database import get_db_instance

db = get_db_instance()  # Returns mocked instance from pytest fixture
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TEST_ENV` | Enable test mode | `false` |
| `ENCRYPTION_KEY` | Fernet encryption key for sensitive data | None (optional) |

### Paths

- **Base Path**: `SCAREFERA_LAB_DIR/artifacts` (from `app.config`)
- **Runtime**: `base_path/runtime/{collection}/{usuario_id}/{sessao_id}/`
- **Canonical**: `base_path/canonical/{collection}/`
- **Config**: `base_path/config/`

## Migration to MongoDB

When migrating to MongoDB, update imports and maintain the same interface:

```python
# Before (JSON)
from app.database import JSONDatabase, get_db_instance

# After (MongoDB)
from app.database import MongoDatabase as JSONDatabase, get_db_instance

# No changes to usage code required
db.insert("celulas", celula, ...)
```

## Related Documentation

- [Backend README](../README.md) - Backend overview
- [BASE_DIR Guidelines](../docs/BASE_DIR_GUIDELINES.md) - Path management
- [ARQUITETURA_TESTES.md](../../docs/ARQUITETURA_TESTES.md) - Testing strategy
- [crypto_utils.py](../crypto_utils.py) - Encryption utilities

## Notes

- **Technical names**: All function names, variables, parameters in English
- **Documentation**: Can be bilingual (English/Portuguese)
- **File size**: Each module < 500 lines (Rule 1.1)
- **Testing**: Use mongomock or JSONDatabase test mode for persistence tests
