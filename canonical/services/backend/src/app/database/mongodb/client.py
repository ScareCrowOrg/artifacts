"""
MongoDB client setup and connection management for ScareVerse.

⚠️ DEPRECATION WARNING (Phase 1B):
This module provides direct MongoDB access and should ONLY be used by CentralHub.
ScareRunner workers should use CentralHubClient HTTP proxy instead.

For ScareRunner: Use backend.app.database.centralhub_client.CentralHubClient
For CentralHub: This module is the correct choice

Provides async MongoDB client using Motor for runtime data persistence.
Maintains compatibility with JSONDatabase interface patterns.
"""

import logging
import warnings
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure

from ...config.database import (
    MONGODB_DATABASE,
    MONGODB_ENABLED,
    MONGODB_HOST,
    MONGODB_PASSWORD,
    MONGODB_PORT,
    MONGODB_USERNAME,
    get_mongodb_uri,
)

logger = logging.getLogger(__name__)

# Global MongoDB client instance
_mongodb_client: Optional[AsyncIOMotorClient] = None
_mongodb_database: Optional[AsyncIOMotorDatabase] = None


async def get_mongodb_client() -> Optional[AsyncIOMotorClient]:
    """
    Get or create async MongoDB client instance.

    ⚠️ DEPRECATION WARNING (Phase 1B):
    Direct MongoDB access should only be used by CentralHub.
    ScareRunner workers should use CentralHubClient HTTP proxy instead.

    Returns:
        MongoDB client instance or None if MongoDB is disabled or unavailable
    """
    global _mongodb_client

    if not MONGODB_ENABLED:
        logger.debug("MongoDB is disabled in configuration")
        return None

    # Emit deprecation warning for ScareRunner usage
    warnings.warn(
        "Direct MongoDB client usage is deprecated for ScareRunner. "
        "Use CentralHubClient HTTP proxy instead for Phase 1B architecture compliance.",
        DeprecationWarning,
        stacklevel=2,
    )

    if _mongodb_client is not None:
        return _mongodb_client

    try:
        uri = get_mongodb_uri()
        # Log URI without password for debugging
        safe_uri = (
            uri.replace(f":{MONGODB_PASSWORD}@", ":****@") if MONGODB_PASSWORD else uri
        )
        logger.info("Connecting to MongoDB with URI: %s", safe_uri)
        logger.info("MongoDB auth configuration: username=%s, database=%s", MONGODB_USERNAME, MONGODB_DATABASE)
        logger.info("MongoDB connection details: host=%s, port=%s", MONGODB_HOST, MONGODB_PORT)

        _mongodb_client = AsyncIOMotorClient(
            uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=10000, maxPoolSize=50
        )

        # Test connection
        logger.info("Testing MongoDB connection with ping...")
        await _mongodb_client.admin.command("ping")
        logger.info("MongoDB ping successful!")
        logger.info("MongoDB client initialized successfully: %s:%s/%s", MONGODB_HOST, MONGODB_PORT, MONGODB_DATABASE)

        # Test authentication by listing collections
        try:
            db = _mongodb_client[MONGODB_DATABASE]
            logger.info("Attempting to list collections in database '%s'...", MONGODB_DATABASE)
            collections = await db.list_collection_names()
            logger.info("MongoDB collections available (%s): %s", len(collections), collections)
            logger.info("MongoDB authentication verified successfully for database '%s'", MONGODB_DATABASE)
        except Exception as e:
            logger.error("MongoDB authentication test failed when listing collections: %s: %s", type(e).__name__, e)
            logger.error("Make sure the configured user has read/write permissions on database '%s'", MONGODB_DATABASE)
            logger.error("To fix, run in MongoDB shell:")
            logger.error("  use %s", MONGODB_DATABASE)
            logger.error("  db.grantRolesToUser('<username>', [{%s}])", role)

        return _mongodb_client

    except ConnectionFailure as e:
        logger.warning("Failed to connect to MongoDB: %s. Runtime data will use fallback storage.", e)
        _mongodb_client = None
        return None
    except Exception as e:
        logger.error("Error initializing MongoDB client: %s: %s", type(e).__name__, e)
        logger.error(
            "Connection parameters: host=%s, port=%s, db=%s, user=%s",
            MONGODB_HOST, MONGODB_PORT, MONGODB_DATABASE, MONGODB_USERNAME
        )
        _mongodb_client = None
        return None


async def get_mongodb_database() -> Optional[AsyncIOMotorDatabase]:
    """
    Get MongoDB database instance.

    Returns:
        MongoDB database instance or None if unavailable
    """
    global _mongodb_database

    if _mongodb_database is not None:
        return _mongodb_database

    client = await get_mongodb_client()
    if client is None:
        return None

    _mongodb_database = client[MONGODB_DATABASE]
    return _mongodb_database


async def close_mongodb_client():
    """Close MongoDB client connection."""
    global _mongodb_client, _mongodb_database

    if _mongodb_client is not None:
        try:
            _mongodb_client.close()
            logger.info("MongoDB client closed")
        except Exception as e:
            logger.error("Error closing MongoDB client: %s", e)
        finally:
            _mongodb_client = None
            _mongodb_database = None


def reset_mongodb_client():
    """Reset MongoDB client (for testing)."""
    global _mongodb_client, _mongodb_database
    _mongodb_client = None
    _mongodb_database = None
