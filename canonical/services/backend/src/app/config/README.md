---
processed: true
processed_date: 2025-12-08
themes:
  - backend
  - configuration
  - settings
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Configuration Module - ScareVerse Backend

Centralized configuration management for the ScareVerse backend application.

## Overview

This module provides a single source of truth for all database-related configuration, following RULESET.md Rule 4.1 (Configuration Centralization) and Rule 4.2 (Path References using BASE_DIR).

## Structure

```
config/
├── __init__.py      # Exports all configuration for easy imports
├── database.py      # Database-specific configuration (MongoDB, Redis, paths)
├── redis_keys.py    # Redis key constants for distributed features (SCARE-042)
└── README.md        # This file
```

## Configuration Files

### database.py

Centralized database configuration including:

### redis_keys.py

Redis key constants for distributed features (SCARE-042 - Ollama Queue Bridge):

#### Key Definitions
- **OLLAMA_JOBS_QUEUE** - Main queue for Ollama job requests (`scareverse:ollama-jobs:queue`)
- **OLLAMA_RESULTS_PREFIX** - Prefix for job results (`scareverse:ollama-results`)
- **OLLAMA_DEADLETTER** - Dead-letter queue for failed jobs (`scareverse:ollama-deadletter`)
- **OLLAMA_METRICS** - Hash key for queue metrics (`scareverse:ollama-metrics`)
- **OLLAMA_ACTIVE_JOBS** - Set of active job IDs (`scareverse:ollama-metrics:active`)

**Helper Functions:**
- `get_ollama_result_key(job_id)` - Generate result key for a specific job

**Usage Example:**
```python
from app.config.redis_keys import OLLAMA_JOBS_QUEUE, get_ollama_result_key

# Enqueue job
redis.rpush(OLLAMA_JOBS_QUEUE, job_json)

# Get result key
result_key = get_ollama_result_key("abc-123-def")  # "scareverse:ollama-results:abc-123-def"
```

#### Path Configuration
- **ARTIFACTS_DIR** - Base directory for all artifacts (`BASE_DIR/artifacts`)
- **CANONICAL_DIR** - Directory for canonical (git-managed) artifacts
- **RUNTIME_DIR** - Directory for runtime (user-generated) artifacts

All paths are derived from `BASE_DIR` to ensure portability across environments.

#### MongoDB Configuration
- **MONGODB_CONFIG** - Consolidated MongoDB settings dictionary
- **MONGODB_HOST** - MongoDB server hostname (env: `MONGODB_HOST`, default: `localhost`)
- **MONGODB_PORT** - MongoDB server port (env: `MONGODB_PORT`, default: `27017`)
- **MONGODB_DATABASE** - Database name (env: `MONGODB_DATABASE`, default: `scareverse`)
- **MONGODB_USERNAME** - Authentication username (env: `MONGODB_USERNAME`, optional)
- **MONGODB_PASSWORD** - Authentication password (env: `MONGODB_PASSWORD`, optional)
- **MONGODB_ENABLED** - Enable/disable MongoDB (env: `MONGODB_ENABLED`, default: `false`)

**Helper Functions:**
- `get_mongodb_uri()` - Generates MongoDB connection string with or without authentication

#### Redis Configuration
- **REDIS_CONFIG** - Consolidated Redis settings dictionary
- **REDIS_HOST** - Redis server hostname (env: `REDIS_HOST`, default: `localhost`)
- **REDIS_PORT** - Redis server port (env: `REDIS_PORT`, default: `6379`)
- **REDIS_DB** - Redis database number (env: `REDIS_DB`, default: `0`)
- **REDIS_PASSWORD** - Authentication password (env: `REDIS_PASSWORD`, optional)
- **REDIS_ENABLED** - Enable/disable Redis for event streaming (env: `REDIS_ENABLED`, default: `false`)
- **REDIS_CACHE_ENABLED** - Enable/disable Redis caching (env: `REDIS_CACHE_ENABLED`, default: `false`)

**Cache TTL Settings:**
- **REDIS_CACHE_TTL** - Default cache TTL: 3600s (1 hour)
- **REDIS_CACHE_TTL_CELULAS** - Cells cache TTL: 1800s (30 minutes)
- **REDIS_CACHE_TTL_LIVROS** - Books cache TTL: 1800s (30 minutes)
- **REDIS_CACHE_TTL_CONFIG** - Config cache TTL: 300s (5 minutes)
- **REDIS_CACHE_TTL_CANONICAL** - Canonical artifacts cache TTL: 7200s (2 hours)
- **COLLECTION_CACHE_TTLS** - Dictionary mapping collection names to TTL values

**Helper Functions:**
- `get_cache_ttl(collection, is_canonical)` - Returns appropriate TTL for a collection

#### Collection Settings
- **CANONICAL_COLLECTIONS** - Set of collections that use file-based storage (e.g., `cell_types`, `templates`)
- **RUNTIME_COLLECTIONS** - Set of collections that use MongoDB when enabled (e.g., `cells`, `books`)

#### Validation Functions
- `validate_mongodb_config()` - Validates MongoDB configuration
- `validate_redis_config()` - Validates Redis configuration
- `validate_all_database_config()` - Validates all database configuration

## Usage Examples

### Import Configuration

```python
# Import from config package
from app.config.database import (
    MONGODB_CONFIG,
    REDIS_CONFIG,
    ARTIFACTS_DIR,
    get_mongodb_uri,
    get_cache_ttl
)

# Or import specific values
from app.config.database import MONGODB_HOST, MONGODB_PORT
```

### Use Path Configuration

```python
from app.config.database import CANONICAL_DIR, RUNTIME_DIR

# Access canonical artifacts
templates_dir = CANONICAL_DIR / "templates"

# Access runtime artifacts
user_cells_dir = RUNTIME_DIR / "cells" / user_id / session_id
```

### Use MongoDB Configuration

```python
from app.config.database import MONGODB_CONFIG, get_mongodb_uri
from motor.motor_asyncio import AsyncIOMotorClient

# Use configuration dictionary
if MONGODB_CONFIG["enabled"]:
    uri = get_mongodb_uri()
    client = AsyncIOMotorClient(uri)
```

### Use Redis Configuration

```python
from app.config.database import REDIS_CONFIG, get_cache_ttl
from redis.asyncio import Redis

# Use configuration dictionary
if REDIS_CONFIG["cache_enabled"]:
    redis = Redis(
        host=REDIS_CONFIG["host"],
        port=REDIS_CONFIG["port"],
        db=REDIS_CONFIG["db"],
        password=REDIS_CONFIG["password"]
    )
    
    # Get collection-specific TTL
    ttl = get_cache_ttl("cells")  # Returns 1800 seconds
```

### Validate Configuration

```python
from app.config.database import validate_all_database_config

try:
    validate_all_database_config()
    print("Configuration is valid")
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Environment Variables

All database configuration can be customized via environment variables. Create a `.env` file in the project root:

```env
# MongoDB Configuration
MONGODB_ENABLED=true
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=scareverse
MONGODB_USERNAME=scareverse_user
MONGODB_PASSWORD=secure_password

# Redis Configuration
REDIS_ENABLED=true
REDIS_CACHE_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Redis Cache TTLs (optional, defaults shown)
REDIS_CACHE_TTL=3600
REDIS_CACHE_TTL_CELULAS=1800
REDIS_CACHE_TTL_LIVROS=1800
REDIS_CACHE_TTL_CONFIG=300
REDIS_CACHE_TTL_CANONICAL=7200
```

## Design Principles

### Rule 4.1: Configuration Centralization
All database configuration is centralized in `config/database.py`, eliminating scattered configuration across multiple files.

### Rule 4.2: Path References using BASE_DIR
All path references are derived from `BASE_DIR` to ensure portability:
```python
ARTIFACTS_DIR = BASE_DIR / "artifacts"
CANONICAL_DIR = ARTIFACTS_DIR / "canonical"
RUNTIME_DIR = ARTIFACTS_DIR / "runtime"
```

### Rule 4.3: Technical Naming in English
All variable names, functions, and constants use English:
- ✅ `MONGODB_CONFIG`, `get_cache_ttl()`, `CANONICAL_COLLECTIONS`
- ❌ `CONFIG_MONGO`, `obter_ttl_cache()`, `COLECOES_CANONICAS`

### Rule 1.1: File Size Limit
- `database.py`: ~270 lines (under 500 line limit)
- `__init__.py`: ~90 lines (under 500 line limit)

## Migration from Old Configuration

Before (scattered configuration):
```python
# In app/config.py
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

# In app/database/connection.py
self.base_path = SCAREFERA_LAB_DIR / "artifacts"

# In app/database/redis_cache/redis_cache_base.py
from ...config import REDIS_CACHE_TTL
```

After (centralized configuration):
```python
# Import from config.database
from app.config.database import (
    MONGODB_HOST,
    REDIS_HOST,
    ARTIFACTS_DIR,
    REDIS_CACHE_TTL
)
```

## Testing

Configuration can be tested using the validation functions:

```python
import pytest
from app.config.database import (
    validate_mongodb_config,
    validate_redis_config,
    validate_all_database_config
)

def test_mongodb_config_validation():
    """Test MongoDB configuration validation."""
    # Should pass with valid config
    assert validate_mongodb_config() == True

def test_redis_config_validation():
    """Test Redis configuration validation."""
    # Should pass with valid config
    assert validate_redis_config() == True

def test_all_config_validation():
    """Test all database configuration validation."""
    # Should pass with valid config
    assert validate_all_database_config() == True
```

## Related Documentation

- [Backend README](../../README.md) - Backend overview
- [Database Module](../database/README.md) - Database layer documentation
- [RULESET.md](../../../RULESET.md) - Project rules and conventions
- [BASE_DIR Guidelines](../../docs/BASE_DIR_GUIDELINES.md) - Path reference guidelines

## Change Log

### Version 1.0.0 (2025-11-27)
- Initial release
- Centralized MongoDB configuration
- Centralized Redis configuration
- Centralized path configuration
- Added configuration validation functions
- Compliance with RULESET.md Rules 4.1, 4.2, 4.3, and 1.1

---

**Last Updated**: 2025-11-27  
**Maintained By**: Backend Team  
**Status**: Active
