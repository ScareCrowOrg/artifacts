---
processed: true
processed_date: 2026-03-06
generated_docs:
  - docs/official/backend/architecture/hybrid-database-rbac-api.md
themes:
  - database
  - query-engine
  - backend
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Query Engine Module

## Overview

The Query Engine module provides infrastructure for translating MongoDB-style queries into SQL queries. This is a foundational component for the RBAC-aware database access system, enabling flexible, secure query execution for both canonical and sandbox data.

## Purpose

- **Query Translation**: Convert MongoDB-style queries to SQL
- **Security**: Validate queries and prevent SQL injection
- **Extensibility**: Abstract base class for different query engine implementations
- **Dynamic Schema Inference**: Support for user-specific sandbox data
- **RBAC Support**: Foundation for role-based access control query filtering

## Module Structure

```
query_engine/
├── __init__.py              # Module exports
├── README.md               # This file
├── base.py                 # Abstract base class (QueryEngine)
├── canonical_engine.py     # Engine for canonical data with predefined schemas
├── sandbox_engine.py       # Engine for sandbox data with dynamic schemas
├── canonical_schema.py     # Schema loader for canonical data
├── canonical_compilers.py  # SQL compilation utilities
├── exceptions.py           # Custom exceptions
├── utils.py               # Utility classes (QueryValidator, QueryCompiler)
└── constants.py           # MongoDB to SQL operator mappings
```

## Core Components

### 1. QueryEngine (base.py)

Abstract base class that defines the contract for query engines.

**Key Methods**:
- `find()`: Execute query and return results
- `_compile_query()`: Compile MongoDB query to SQL
- `_validate_query()`: Validate query syntax

**Usage**:
```python
from backend.app.database.query_engine import QueryEngine

class PostgreSQLQueryEngine(QueryEngine):
    async def find(self, collection: str, query: Dict) -> List[Dict]:
        self._validate_query(query)
        sql = self._compile_query(collection, query)
        return await self._execute(sql)
```

### 2. CanonicalQueryEngine (canonical_engine.py)

Query engine for canonical data (templates, roles, workflows) using predefined schemas from `artifacts/canonical/SCHEMAS.json`.

**Key Features**:
- Schema-aware SQLite compilation
- Predefined schemas loaded at initialization
- Support for 13 MongoDB operators
- Automatic indexing on critical fields
- Performance: <50ms for simple queries, <100ms for complex queries (5k docs)

**Usage**:
```python
from backend.app.database.query_engine import CanonicalQueryEngine

# Initialize with default schema path
engine = CanonicalQueryEngine()

# Query canonical data
results = await engine.find(
    collection="templates",
    query={
        "status": "published",
        "tags": {"$all": ["featured"]},
        "metadata.level": {"$gte": 5}
    },
    limit=10
)
```

### 3. SandboxQueryEngine (sandbox_engine.py) **NEW**

Query engine for sandbox data with dynamic schema inference. Unlike CanonicalQueryEngine which uses predefined schemas, this engine infers schemas by scanning all documents in a user's sandbox collection.

**Key Features**:
- Dynamic schema inference from sandbox documents (READ-ONLY)
- Redis caching with 1-hour TTL
- Cache invalidation hooks for write operations
- Support for all 13 MongoDB operators (inherited)
- Type inference for Python to SQLite mapping
- Optimized for user-specific data patterns

**Usage**:
```python
from backend.app.database.query_engine import SandboxQueryEngine

# Initialize with Redis client and base path
engine = SandboxQueryEngine(redis_client, base_path)

# Query user's sandbox data
results = await engine.find(
    user_id="user123",
    collection="documents",
    query={
        "status": "active",
        "priority": {"$gte": 5}
    },
    limit=10
)

# Invalidate cache after mutation (called by HybridDatabase)
await engine.invalidate_schema_cache("user123", "documents")
```

**Schema Inference**:
- Scans all documents in `artifacts/sandbox/{user_id}/{collection}.json`
- Builds unified schema by taking union of all fields
- Handles type conflicts by using TEXT (most flexible)
- Caches inferred schemas in Redis for 1 hour

**Cache Invalidation Hooks**:
```python
# Invalidate specific collection
await engine.invalidate_schema_cache(user_id, collection)

# Invalidate all user schemas
await engine.invalidate_all_user_schemas(user_id)
```

**Integration with HybridDatabase** (Sub-Issue 1.6):
Cache invalidation hooks are called by HybridDatabase's unified write methods:
- `insert()` → `invalidate_schema_cache()`
- `update()` → `invalidate_schema_cache()`
- `delete()` → `invalidate_schema_cache()`

### 4. Exceptions (exceptions.py)

Custom exception classes for query engine operations:

- `QueryEngineException`: Base exception
- `InvalidQueryException`: Query syntax errors
- `UnsupportedOperatorException`: Unsupported MongoDB operators
- `ValidationException`: Query validation failures
- `CompilationException`: SQL compilation errors

**Usage**:
```python
from backend.app.database.query_engine import InvalidQueryException

if not isinstance(query, dict):
    raise InvalidQueryException("Query must be a dictionary")
```

### 3. Utilities (utils.py)

Helper classes for query validation and compilation:

**QueryValidator**:
- `validate_query()`: Comprehensive query validation
- `validate_field_name()`: Field name security checks
- `validate_operator()`: Operator support validation
- `check_sql_injection()`: SQL injection detection

**QueryCompiler**:
- `escape_identifier()`: Escape SQL identifiers
- `format_value()`: Format values for SQL
- `compile_condition()`: Compile conditions to SQL

**Usage**:
```python
from backend.app.database.query_engine import QueryValidator, QueryCompiler

# Validate query
QueryValidator.validate_query({"status": "active", "age": {"$gte": 18}})

# Escape identifier
field = QueryCompiler.escape_identifier("user")  # "user"

# Format value
value = QueryCompiler.format_value("test")  # 'test'
```

### 4. Constants (constants.py)

MongoDB to SQL operator mappings and configuration:

**Operator Sets**:
- `COMPARISON_OPERATORS`: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin
- `LOGICAL_OPERATORS`: $and, $or, $not, $nor
- `ELEMENT_OPERATORS`: $exists, $type
- `ARRAY_OPERATORS`: $all, $elemMatch, $size
- `STRING_OPERATORS`: $regex, $text

**Mappings**:
- `MONGODB_OPERATORS`: All supported operators
- `SQL_OPERATORS`: Operator to SQL symbol mapping
- `OPERATOR_MAPPING`: Operator to SQL template mapping
- `TYPE_MAPPING`: MongoDB to PostgreSQL type mapping
- `RESERVED_KEYWORDS`: SQL reserved keywords

**Usage**:
```python
from backend.app.database.query_engine import MONGODB_OPERATORS, OPERATOR_MAPPING

# Check if operator is supported
if "$eq" in MONGODB_OPERATORS:
    template = OPERATOR_MAPPING["$eq"]["template"]
```

## Query Syntax

### Supported MongoDB Operators

**Comparison**:
- `$eq`: Equal (=)
- `$ne`: Not equal (!=)
- `$gt`: Greater than (>)
- `$gte`: Greater than or equal (>=)
- `$lt`: Less than (<)
- `$lte`: Less than or equal (<=)
- `$in`: In array (IN)
- `$nin`: Not in array (NOT IN)

**Logical**:
- `$and`: Logical AND
- `$or`: Logical OR
- `$not`: Logical NOT
- `$nor`: Logical NOR

**Element**:
- `$exists`: Field exists check
- `$type`: Field type check

**Array** (for JSONB columns):
- `$all`: All elements match
- `$elemMatch`: At least one element matches
- `$size`: Array size check

**String**:
- `$regex`: Regular expression match
- `$text`: Full-text search

### Query Examples

**Simple Query**:
```python
query = {"status": "active"}
# SQL: WHERE status = 'active'
```

**Comparison Operators**:
```python
query = {"age": {"$gte": 18, "$lt": 65}}
# SQL: WHERE age >= 18 AND age < 65
```

**IN Operator**:
```python
query = {"status": {"$in": ["active", "pending"]}}
# SQL: WHERE status IN ('active', 'pending')
```

**Logical Operators**:
```python
query = {
    "$or": [
        {"status": "active"},
        {"priority": "high"}
    ]
}
# SQL: WHERE (status = 'active' OR priority = 'high')
```

**Complex Query**:
```python
query = {
    "$and": [
        {"status": "active"},
        {"$or": [
            {"age": {"$gte": 18}},
            {"verified": True}
        ]}
    ]
}
# SQL: WHERE (status = 'active' AND (age >= 18 OR verified = TRUE))
```

## Security Features

### SQL Injection Prevention

The module includes multiple layers of security:

1. **Query Validation**: Validates query structure before compilation
2. **Field Name Validation**: Checks for SQL injection patterns in field names
3. **Value Escaping**: Properly escapes all values in queries
4. **Identifier Escaping**: Escapes identifiers (field/table names)
5. **Reserved Keyword Detection**: Identifies and quotes reserved SQL keywords

### Validation Checks

- Query structure validation (must be dictionary)
- Operator support validation (only allowed operators)
- Field name security (no SQL injection patterns)
- Value type validation (appropriate for operator)
- Regex syntax validation (for $regex operator)

## Integration

### With Existing Database Layer

The query engine integrates with the existing hybrid database system:

```python
from backend.app.database.query_engine import QueryEngine
from backend.app.database import HybridDatabase

class RBACQueryEngine(QueryEngine):
    def __init__(self, db: HybridDatabase):
        super().__init__()
        self.db = db
    
    async def find(self, collection: str, query: Dict) -> List[Dict]:
        # Validate and compile
        self._validate_query(query)
        sql = self._compile_query(collection, query)
        
        # Execute through existing database layer
        return await self.db.execute_sql(sql)
```

### Future Extensions

This foundation enables:
- RBAC filtering (Phase 2)
- Permission-based query modification
- Audit logging for queries
- Query optimization
- Caching strategies

## Error Handling

All exceptions include detailed error messages and context:

```python
try:
    QueryValidator.validate_query(query)
except InvalidQueryException as e:
    logger.error(f"Invalid query: {e.message}")
    logger.debug(f"Details: {e.details}")
except UnsupportedOperatorException as e:
    logger.error(f"Unsupported operator: {e.details['operator']}")
    logger.info(f"Supported: {e.details['supported_operators']}")
except ValidationException as e:
    logger.error(f"Validation failed: {e.message}")
    if 'field' in e.details:
        logger.debug(f"Field: {e.details['field']}")
```

## Testing

Tests are located in:
- `tests/unit/backend/query_engine/test_base.py` - Base class tests
- `tests/unit/backend/query_engine/test_canonical_query_engine.py` - Canonical engine tests
- `tests/unit/backend/query_engine/test_sandbox_query_engine.py` - Sandbox engine tests (NEW)
- `tests/unit/backend/query_engine/test_validators.py` - Validator tests
- `tests/unit/backend/query_engine/test_compilers.py` - Compiler tests

**Coverage Target**: 90%+ for query engines, 100% for utilities and exceptions

**Test Categories**:
- Query validation tests
- Operator support tests
- Security tests (SQL injection)
- Value formatting tests
- Exception handling tests
- Schema inference tests (SandboxQueryEngine)
- Redis caching tests (SandboxQueryEngine)
- Performance tests (schema build < 100ms for 1k docs, < 500ms for 5k docs)

**Run Tests**:
```bash
# Run all query engine tests
pytest tests/unit/backend/query_engine/ -v

# Run specific engine tests
pytest tests/unit/backend/query_engine/test_canonical_query_engine.py -v
pytest tests/unit/backend/query_engine/test_sandbox_query_engine.py -v

# Run with coverage
pytest tests/unit/backend/query_engine/ --cov=app.database.query_engine
```

**Test Results (SandboxQueryEngine)**:
- 35 tests passed
- 98% code coverage
- Performance validated: <100ms for 1k docs, <500ms for 5k docs

## Development Guidelines

### Adding New Operators

1. Add operator to appropriate set in `constants.py`
2. Add SQL mapping in `OPERATOR_MAPPING`
3. Add validation logic in `QueryValidator` (if needed)
4. Update this README with examples
5. Add tests for the new operator

### Implementing Query Engine

When creating a concrete query engine:

1. Inherit from `QueryEngine`
2. Implement `find()` method
3. Implement `_compile_query()` method
4. Implement `_validate_query()` method (or use `QueryValidator`)
5. Add comprehensive error handling
6. Add logging for debugging
7. Write unit tests for all methods

## References

- **Parent Epic**: database-unified-rbac-access
- **Phase**: 1 - Infrastructure
- **Sub-Issues**:
  - Sub-Issue 1.1: Query Engine Foundation ✅ Complete
  - Sub-Issue 1.2: CanonicalQueryEngine Implementation ✅ Complete
  - Sub-Issue 1.3: SandboxQueryEngine Implementation ✅ Complete (this)
  - Sub-Issue 1.6: HybridDatabase Refactoring (upcoming integration)
- **Dependencies**: 
  - Redis client (for SandboxQueryEngine caching)
  - SQLite (in-memory database for query execution)
- **Related Modules**: 
  - `backend/app/database/` - Database layer
  - `backend/app/core/exceptions.py` - Exception patterns
  - `artifacts/canonical/SCHEMAS.json` - Canonical data schemas
  - `artifacts/sandbox/{user_id}/` - Sandbox data files

## Status

- **Version**: 1.1.0
- **Status**: Phase 1 Complete
- **Completed Sub-Issues**:
  - ✅ Sub-Issue 1.1: Query Engine Foundation
  - ✅ Sub-Issue 1.2: CanonicalQueryEngine Implementation
  - ✅ Sub-Issue 1.3: SandboxQueryEngine Implementation (NEW)
- **Next Phase**: 
  - Sub-Issue 1.4: RBAC Infrastructure
  - Sub-Issue 1.5: Cache Manager
  - Sub-Issue 1.6: HybridDatabase Refactoring (will integrate SandboxQueryEngine cache invalidation hooks)

## Contact

For questions or issues with this module, refer to the parent epic documentation or team leads.
