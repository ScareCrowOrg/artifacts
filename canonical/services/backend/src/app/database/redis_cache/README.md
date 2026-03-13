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
# Backend - Redis Cache

## Overview

Redis caching layer implementation for ScareVerse backend providing fast data access and session management.

## Files

- `cache_manager.py` - Redis cache operations
- `serializers.py` - Data serialization for caching
- `config.py` - Redis configuration

## Features

- Key-value caching
- TTL (Time-To-Live) management
- Session storage
- Query result caching
- Automatic serialization/deserialization

## Usage

```python
from app.database.redis_cache import CacheManager

cache = CacheManager()

# Set value
cache.set('key', {'data': 'value'}, ttl=3600)

# Get value
result = cache.get('key')

# Delete
cache.delete('key')
```

## Testing

Tests located in `backend/tests/unit/backend/database/test_redis_cache.py`

```bash
pytest backend/tests/unit/backend/database/test_redis_cache.py -v
```

---

For more details, see [Database Module README](../README.md)
