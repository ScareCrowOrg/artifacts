---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - architecture
  - database
  - services
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# MongoDB Database Module

## Overview

This module provides MongoDB-based persistence for ScareVerse runtime data. It implements an async interface compatible with the existing `JSONDatabase` pattern, enabling transparent migration from file-based to MongoDB storage.

## Architecture

### Design Principles

1. **Interface Compatibility**: Maintains the same method signatures as `JSONDatabase` for easy migration
2. **Async Operations**: Uses Motor (async MongoDB driver) for non-blocking database operations
3. **Runtime Only**: MongoDB stores only runtime data; canonical data remains in the file system
4. **Transparent Fallback**: If MongoDB is unavailable, the system falls back to file-based storage

### Components

#### `client.py`
Manages MongoDB client connection lifecycle:
- Global client singleton pattern
- Automatic connection pooling (max 50 connections)
- Connection health checks
- Graceful degradation if MongoDB is unavailable

#### `operations.py`
Provides CRUD operations compatible with JSONDatabase:
- `insert()` - Create new documents
- `find_one()` - Retrieve by ID
- `update()` - Update existing documents
- `delete()` - Remove documents
- `find_many()` - Query multiple documents
- `find_by_field()` - Query by single field
- `find_by_fields()` - Query by multiple fields

#### `__init__.py`
Module exports and public API

## Usage

### Basic Operations

```python
from backend.app.database.mongodb import MongoDBOperations
from backend.app.models import Celula

# Initialize operations
ops = MongoDBOperations()

# Insert document
doc_id = await ops.insert(
    collection="celulas",
    document=celula_model,
    usuario_id="user123",
    sessao_id="session456"
)

# Find document
celula = await ops.find_one(
    collection="celulas",
    doc_id=doc_id,
    model_class=Celula
)

# Update document
success = await ops.update(
    collection="celulas",
    doc_id=doc_id,
    updates={"status": "completed"}
)

# Delete document
deleted = await ops.delete(
    collection="celulas",
    doc_id=doc_id
)

# Find multiple documents
celulas = await ops.find_many(
    collection="celulas",
    model_class=Celula,
    usuario_id="user123",
    limit=10
)
```

### Integration with JSONDatabase

The MongoDB module is designed to be used alongside JSONDatabase through a routing layer:

```python
from backend.app.database import JSONDatabase
from backend.app.database.mongodb import MongoDBOperations

class HybridDatabase(JSONDatabase, MongoDBOperations):
    """
    Hybrid database that routes canonical data to files
    and runtime data to MongoDB.
    """
    
    async def insert(self, collection, document, **kwargs):
        if kwargs.get('is_canonical'):
            # Use file-based storage
            return super().insert(collection, document, **kwargs)
        else:
            # Use MongoDB
            return await MongoDBOperations.insert(self, collection, document, **kwargs)
```

## Collections

### Runtime Collections

All MongoDB collections use the `_runtime` suffix:

- `celulas_runtime` - Runtime cell documents
- `livros_runtime` - Runtime book documents
- `sessoes_runtime` - User session documents
- `usuarios_runtime` - User data (runtime state)
- `memoria_runtime` - Conversation memory
- `traces_runtime` - Conversation traces

### Indexes

Collections are automatically indexed on startup (via init-db.js):

**Common Indexes:**
- `id` (unique)
- `usuario_id`
- `sessao_id`
- `assignee_id`
- `created_at` (descending)

**Specific Indexes:**
- `usuarios_runtime.email` (unique)

## Configuration

### Environment Variables

```bash
# Enable MongoDB
MONGODB_ENABLED=true

# Connection settings
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=scareverse
MONGODB_USERNAME=scareverse
MONGODB_PASSWORD=your-secure-password
```

### Connection String

The module automatically builds the connection string from environment variables:

```
mongodb://username:password@host:port/database
```

For unauthenticated connections, omit username/password:

```
mongodb://host:port/database
```

## Data Model

### Document Structure

All MongoDB documents include standard metadata fields:

```json
{
  "id": "unique-document-id",
  "usuario_id": "user-id",
  "sessao_id": "session-id",
  "created_at": "2025-11-27T00:00:00Z",
  "updated_at": "2025-11-27T00:00:00Z",
  // ... document-specific fields
}
```

### Canonical vs Runtime

- **Canonical Data**: Stored in `artifacts/canonical/` (file system, git-managed)
  - Cell types, book templates, AI models, permissions, roles
  - Version controlled, immutable configuration
  
- **Runtime Data**: Stored in MongoDB
  - User-created cells, books, sessions
  - Conversation memory and traces
  - Mutable, user-generated content

## Migration

### From JSON Files to MongoDB

Use the data migration scripts in `scripts/data_migration/`:

```bash
# Migrate runtime data from JSON to MongoDB
python scripts/data_migration/migrate_json_to_mongodb.py

# Validate migrated data
python scripts/data_migration/validate_migration.py
```

### Migration Process

1. Read JSON files from `artifacts/runtime/`
2. Transform to MongoDB document format
3. Insert into appropriate collections
4. Validate data integrity
5. Archive original JSON files (don't delete)

## Testing

### Unit Tests

```python
import pytest
from backend.app.database.mongodb import MongoDBOperations

@pytest.mark.asyncio
async def test_insert_and_find(mongodb_ops, celula_model):
    # Insert
    doc_id = await mongodb_ops.insert("celulas", celula_model)
    assert doc_id is not None
    
    # Find
    found = await mongodb_ops.find_one("celulas", doc_id, Celula)
    assert found is not None
    assert found.id == doc_id
```

### Integration Tests

Use `mongomock` for testing without a real MongoDB instance:

```python
import pytest
import mongomock

@pytest.fixture
async def mock_mongodb():
    client = mongomock.MongoClient()
    yield client.scareverse
    client.close()
```

## Performance

### Connection Pooling

- Max pool size: 50 connections
- Automatic connection reuse
- Idle connection timeout: managed by Motor

### Query Optimization

- Use indexes for all common queries
- Limit results with `limit` parameter
- Project only needed fields when possible
- Use aggregation pipelines for complex queries

### Caching Strategy

MongoDB integrates with Redis caching:
1. Check Redis cache first
2. If miss, query MongoDB
3. Cache result in Redis with TTL
4. Invalidate cache on writes

## Error Handling

### Connection Errors

If MongoDB is unavailable:
- Logs warning message
- Returns `None` for client/database
- Operations return empty results or `False`
- System falls back to file-based storage

### Operation Errors

- Validation errors: Log and return `None`/`False`
- Network errors: Retry with exponential backoff
- Timeout errors: Log and return gracefully

## Monitoring

### Health Checks

```python
from backend.app.database.mongodb import get_mongodb_client

async def check_mongodb_health():
    client = await get_mongodb_client()
    if client is None:
        return {"status": "unavailable"}
    
    try:
        await client.admin.command('ping')
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### Metrics

Monitor key metrics:
- Connection pool usage
- Query latency
- Operation success/failure rates
- Collection sizes

## Security

### Authentication

- Required in production (`MONGODB_USERNAME`, `MONGODB_PASSWORD`)
- Optional in development (defaults to unauthenticated)

### Data Encryption

- Use TLS/SSL for connections in production
- Configure encryption at rest in MongoDB
- Sensitive fields encrypted by application layer (via `encryption.py`)

## Troubleshooting

### Connection Issues

```bash
# Test connectivity
python -c "
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
async def test():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    await client.admin.command('ping')
    print('Connected!')
asyncio.run(test())
"
```

### Performance Issues

- Check indexes: `db.collection.getIndexes()`
- Analyze queries: `db.collection.explain()`
- Monitor slow queries: Enable profiling

### Data Integrity

- Validate unique constraints on `id` and `email`
- Check for orphaned documents
- Regular data audits

## Testing

### Test Coverage

The MongoDB module has **98% test coverage** with comprehensive test suites:

| Component | Coverage | Test Count |
|-----------|----------|------------|
| `client.py` | 100% | 12 tests |
| `operations.py` | 97% | 49 tests |
| **Total** | **98%** | **61 tests** |

### Running Tests

```bash
# Run all MongoDB tests
cd backend
pytest tests/unit/backend/database/mongodb/ -v

# Run with coverage report
pytest tests/unit/backend/database/mongodb/ \
    --cov=app/database/mongodb \
    --cov-report=html:htmlcov/mongodb \
    --cov-report=term

# Run specific test file
pytest tests/unit/backend/database/mongodb/test_mongodb_client.py -v
```

### Test Structure

```
tests/unit/backend/database/mongodb/
├── conftest.py                  # Shared fixtures (mongomock)
├── test_mongodb_client.py       # Client connection tests
├── test_mongodb_operations.py   # CRUD operation tests
├── test_mongodb_find.py         # Query operation tests
└── test_mongodb_errors.py       # Error handling tests
```

### Testing Philosophy

1. **No Real Database Required**: Tests use `mongomock` for in-memory simulation
2. **Async Testing**: All tests use `pytest-asyncio` for async operations
3. **Comprehensive Coverage**: Tests cover happy paths, edge cases, and error scenarios
4. **Fast Execution**: All tests complete in <0.2 seconds

### Example Test

```python
@pytest.mark.asyncio
async def test_insert_document_success(mock_mongo_db, sample_test_document):
    """Test successful document insertion."""
    ops = MongoDBOperations()
    ops._db = mock_mongo_db
    
    doc_id = await ops.insert(
        collection="test_docs",
        document=sample_test_document,
        usuario_id="user_123",
        sessao_id="sess_456"
    )
    
    assert doc_id == "doc_123"
```

### More Information

For detailed testing documentation, see:
- [Database Testing Guide](../../../../docs/DATABASE_TESTING_GUIDE.md)
- [Test Architecture](../../../../docs/ARQUITETURA_TESTES.md)

## References

- [Motor Documentation](https://motor.readthedocs.io/)
- [PyMongo Documentation](https://pymongo.readthedocs.io/)
- [MongoDB Best Practices](https://docs.mongodb.com/manual/administration/best-practices/)
- [ScareVerse Database Architecture](../README.md)
