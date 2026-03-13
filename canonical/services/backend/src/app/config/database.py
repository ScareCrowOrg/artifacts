"""
Database Configuration Module - ScareVerse Backend

Centralized configuration for all database-related settings including:
- Path configuration (artifacts, canonical, runtime directories)
- MongoDB connection settings
- Redis cache settings
- Collection-specific TTLs and policies

All configuration follows RULESET.md Rule 4.1 (Configuration Centralization)
and Rule 4.2 (Path References using BASE_DIR).
"""

import os
from pathlib import Path
from typing import Any, Dict

# Calculate BASE_DIR directly to avoid circular import
# This should be the root of the workspace/project (ScareFeraLab directory)
BASE_DIR = Path(os.getenv("BASE_DIR", Path(__file__).parent.parent.parent.parent))

# ============================================================================
# PATH CONFIGURATION
# ============================================================================
# All paths derived from BASE_DIR to ensure portability (RULESET.md Rule 4.2)

ARTIFACTS_DIR = BASE_DIR / "artifacts"
"""Base directory for all artifact storage (both canonical and runtime)"""

CANONICAL_DIR = ARTIFACTS_DIR / "canonical"
"""Directory for canonical (git-managed) artifacts like templates and types"""

RUNTIME_DIR = ARTIFACTS_DIR / "runtime"
"""Directory for runtime (user-generated) artifacts like cells and sessions"""


# ============================================================================
# MONGODB CONFIGURATION
# ============================================================================

# MongoDB connection parameters from environment variables
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
"""MongoDB server hostname"""

MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
"""MongoDB server port"""

MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "scareverse")
"""MongoDB database name"""

MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", None)
"""MongoDB authentication username (optional)"""

MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", None)
"""MongoDB authentication password (optional)"""

MONGODB_URI = os.getenv("MONGODB_URI", None)
"""MongoDB connection URI (takes precedence over host/port/username/password)"""

MONGODB_ENABLED = os.getenv("MONGODB_ENABLED", "false").lower() == "true"
"""Flag to enable/disable MongoDB usage"""

MONGODB_MIGRATIONS_ENABLED = (
    os.getenv("MONGODB_MIGRATIONS_ENABLED", "false").lower() == "true"
)
"""
Flag to enable/disable MongoDB migrations in Backend.
Should be set to FALSE - migrations now run in CentralHub.
Kept for backward compatibility during migration period.
"""

# MongoDB configuration dictionary
MONGODB_CONFIG: Dict[str, Any] = {
    "host": MONGODB_HOST,
    "port": MONGODB_PORT,
    "database": MONGODB_DATABASE,
    "username": MONGODB_USERNAME,
    "password": MONGODB_PASSWORD,
    "uri": MONGODB_URI,
    "enabled": MONGODB_ENABLED,
    "migrations_enabled": MONGODB_MIGRATIONS_ENABLED,
}
"""Consolidated MongoDB configuration dictionary"""


def get_mongodb_uri() -> str:
    """
    Get MongoDB connection URI from configuration.

    Uses MONGODB_URI environment variable as the source of truth if provided.
    Falls back to constructing a URI from individual components (host, port, etc.)
    if MONGODB_URI is not set.

    The application user should authenticate against the scareverse database
    (where it was created), not the admin database.

    Returns:
        str: MongoDB connection URI

    Examples:
        With MONGODB_URI set:
            mongodb+srv://user:pass@cluster.mongodb.net/scareverse
        Constructed from components with authentication:
            mongodb://user:pass@localhost:27017/scareverse?authSource=scareverse
        Constructed without authentication:
            mongodb://localhost:27017/scareverse
    """
    # Use MONGODB_URI as source of truth if provided
    if MONGODB_URI:
        return MONGODB_URI

    # Fall back to constructing URI from components
    if MONGODB_USERNAME and MONGODB_PASSWORD:
        return f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}?authSource={MONGODB_DATABASE}"
    else:
        return f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}"


# ============================================================================
# REDIS L1 (LOCAL CACHE) CONFIGURATION
# ============================================================================
# Redis L1 is the local cache used directly by ScareRunner backend
# - Direct connection allowed
# - Used for: local caching, event streaming, temporary data
# - Isolated per ScareRunner instance

REDIS_L1_ENABLED = os.getenv("REDIS_L1_ENABLED", "false").lower() == "true"
"""Flag to enable/disable Redis L1 (local cache)"""

REDIS_L1_HOST = os.getenv("REDIS_L1_HOST", "redis-local")
"""Redis L1 server hostname"""

REDIS_L1_PORT = int(os.getenv("REDIS_L1_PORT", "6380"))
"""Redis L1 server port"""

REDIS_L1_DB = int(os.getenv("REDIS_L1_DB", "0"))
"""Redis L1 database number (0-15)"""

REDIS_L1_PASSWORD = os.getenv("REDIS_L1_PASSWORD", None)
"""Redis L1 authentication password (optional)"""

# ============================================================================
# REDIS L2 (CLUSTER CACHE) CONFIGURATION
# ============================================================================
# Redis L2 is the cluster cache - MUST be accessed via CentralHubClient HTTP
# - NO direct connection from ScareRunner
# - Use CentralHubClient.update_one(), get_one(), etc. for L2 operations
# - Managed by CentralHub in Kubernetes cluster

REDIS_L2_ENABLED = os.getenv("REDIS_L2_ENABLED", "false").lower() == "true"
"""Flag to enable/disable Redis L2 (cluster cache) - access via CentralHubClient HTTP"""

REDIS_L2_HOST = os.getenv("REDIS_L2_HOST", "host.docker.internal")
"""Redis L2 server hostname (for reference only - use CentralHubClient)"""

REDIS_L2_PORT = int(os.getenv("REDIS_L2_PORT", "6379"))
"""Redis L2 server port (for reference only - use CentralHubClient)"""

REDIS_L2_DB = int(os.getenv("REDIS_L2_DB", "0"))
"""Redis L2 database number (for reference only - use CentralHubClient)"""

REDIS_L2_PASSWORD = os.getenv("REDIS_L2_PASSWORD", None)
"""Redis L2 authentication password (for reference only - use CentralHubClient)"""

# Redis cache configuration
REDIS_CACHE_ENABLED = os.getenv("REDIS_CACHE_ENABLED", "false").lower() == "true"
"""Flag to enable/disable Redis caching for JSONDatabase (uses L1)"""

REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "3600"))
"""Default cache TTL in seconds (1 hour)"""

REDIS_CACHE_TTL_CELULAS = int(os.getenv("REDIS_CACHE_TTL_CELULAS", "1800"))
"""Cache TTL for cells collection in seconds (30 minutes)"""

REDIS_CACHE_TTL_LIVROS = int(os.getenv("REDIS_CACHE_TTL_LIVROS", "1800"))
"""Cache TTL for books collection in seconds (30 minutes)"""

REDIS_CACHE_TTL_CONFIG = int(os.getenv("REDIS_CACHE_TTL_CONFIG", "300"))
"""Cache TTL for config collection in seconds (5 minutes)"""

REDIS_CACHE_TTL_CANONICAL = int(os.getenv("REDIS_CACHE_TTL_CANONICAL", "7200"))
"""Cache TTL for canonical artifacts in seconds (2 hours)"""

# Redis L1 configuration dictionary
REDIS_L1_CONFIG: Dict[str, Any] = {
    "host": REDIS_L1_HOST,
    "port": REDIS_L1_PORT,
    "db": REDIS_L1_DB,
    "password": REDIS_L1_PASSWORD,
    "enabled": REDIS_L1_ENABLED,
}
"""Consolidated Redis L1 (local cache) configuration dictionary"""

# Redis L2 configuration dictionary (for reference - use CentralHubClient)
REDIS_L2_CONFIG: Dict[str, Any] = {
    "host": REDIS_L2_HOST,
    "port": REDIS_L2_PORT,
    "db": REDIS_L2_DB,
    "password": REDIS_L2_PASSWORD,
    "enabled": REDIS_L2_ENABLED,
}
"""Consolidated Redis L2 (cluster cache) configuration - access via CentralHubClient HTTP"""

# ============================================================================
# CENTRALHUB HTTP ABSTRACTION (Phase 1B)
# ============================================================================

# CentralHub connection settings
CENTRALHUB_URL = os.getenv("CENTRALHUB_URL", "http://centralhub:8080")
"""CentralHub service URL for HTTP Redis abstraction"""

CENTRALHUB_TIMEOUT = float(os.getenv("CENTRALHUB_TIMEOUT", "310.0"))
"""CentralHub request timeout in seconds (310s for long-polling with margin)"""

# Feature flag for gradual migration
USE_CENTRALHUB_REDIS = os.getenv("USE_CENTRALHUB_REDIS", "false").lower() == "true"
"""Feature flag to enable CentralHub HTTP Redis abstraction (Phase 1B migration)"""

# Service account token for backend operations (if needed)
CENTRALHUB_SERVICE_TOKEN = os.getenv("CENTRALHUB_SERVICE_TOKEN", None)
"""Service account token for backend → CentralHub authenticated operations"""

# Collection-specific cache TTL mapping
COLLECTION_CACHE_TTLS: Dict[str, int] = {
    "cells": REDIS_CACHE_TTL_CELULAS,
    "books": REDIS_CACHE_TTL_LIVROS,
    "config": REDIS_CACHE_TTL_CONFIG,
}
"""Mapping of collection names to their cache TTL values"""


def get_cache_ttl(collection: str, is_canonical: bool = False) -> int:
    """
    Get the appropriate cache TTL for a collection.

    Args:
        collection: Collection name (e.g., 'cells', 'books')
        is_canonical: Whether this is a canonical artifact

    Returns:
        int: TTL in seconds

    Examples:
        >>> get_cache_ttl('cells')
        1800
        >>> get_cache_ttl('custom_collection', is_canonical=True)
        7200
    """
    if is_canonical:
        return REDIS_CACHE_TTL_CANONICAL

    return COLLECTION_CACHE_TTLS.get(collection, REDIS_CACHE_TTL)


# ============================================================================
# COLLECTION-SPECIFIC SETTINGS
# ============================================================================

# Collections that should always use canonical (file-based) storage
CANONICAL_COLLECTIONS = {
    "notebook_item_types",
    "agent_types",
    "workflows",
    "ai_models",
    "templates",
    "permissions",
    "roles",
}
"""Set of collection names that should always use file-based storage"""

# Collections that should always use runtime (MongoDB) storage when available
RUNTIME_COLLECTIONS = {
    "cells",
    "books",
    "sessions",
    "users",
    "memory",
    "traces",
    "audit_logs",
    "contents",
}
"""Set of collection names that should use MongoDB when enabled (MongoDB adds _runtime suffix)"""


# ============================================================================
# CONFIGURATION VALIDATION
# ============================================================================


def validate_mongodb_config() -> bool:
    """
    Validate MongoDB configuration.

    Checks that required MongoDB configuration values are present
    when MongoDB is enabled.

    Returns:
        bool: True if configuration is valid, False otherwise

    Raises:
        ValueError: If MongoDB is enabled but required settings are missing
    """
    if not MONGODB_ENABLED:
        return True

    if not MONGODB_HOST:
        raise ValueError("MONGODB_HOST is required when MongoDB is enabled")

    if not MONGODB_DATABASE:
        raise ValueError("MONGODB_DATABASE is required when MongoDB is enabled")

    if MONGODB_PORT <= 0 or MONGODB_PORT > 65535:
        raise ValueError(f"Invalid MONGODB_PORT: {MONGODB_PORT}")

    return True


def validate_redis_config() -> bool:
    """
    Validate Redis L1 configuration.

    Checks that required Redis L1 configuration values are present
    when Redis L1 is enabled.

    Returns:
        bool: True if configuration is valid, False otherwise

    Raises:
        ValueError: If Redis L1 is enabled but required settings are missing
    """
    if not REDIS_L1_ENABLED and not REDIS_CACHE_ENABLED:
        return True

    if not REDIS_L1_HOST:
        raise ValueError("REDIS_L1_HOST is required when Redis L1 is enabled")

    if REDIS_L1_PORT <= 0 or REDIS_L1_PORT > 65535:
        raise ValueError(f"Invalid REDIS_L1_PORT: {REDIS_L1_PORT}")

    if REDIS_L1_DB < 0 or REDIS_L1_DB > 15:
        raise ValueError(f"Invalid REDIS_L1_DB: {REDIS_L1_DB} (must be 0-15)")

    return True


def validate_all_database_config() -> bool:
    """
    Validate all database configuration.

    Performs comprehensive validation of MongoDB, Redis, and path configuration.

    Returns:
        bool: True if all configuration is valid

    Raises:
        ValueError: If any configuration is invalid
    """
    validate_mongodb_config()
    validate_redis_config()

    # Validate paths exist
    if not BASE_DIR.exists():
        raise ValueError(f"BASE_DIR does not exist: {BASE_DIR}")

    return True
