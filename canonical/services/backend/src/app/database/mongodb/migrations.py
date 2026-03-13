"""
MongoDB Migration System for ScareVerse

⚠️  DEPRECATED: Migrations are now managed by CentralHub ⚠️

This file is kept for reference and backward compatibility.
All new migrations should be added to centralhub/app/migrations/

Migration Ownership:
- CentralHub: Owns MongoDB schema (Single Source of Truth)
- Backend: Uses CentralHub as MongoDB proxy (no direct schema management)

To enable migrations here (NOT RECOMMENDED):
Set MONGODB_MIGRATIONS_ENABLED=true in environment variables

Provides automatic database schema migrations on application startup.
Inspired by Alembic/Flyway migration patterns but optimized for MongoDB.

Key Features:
- Idempotent: Safe to run multiple times
- Automatic: Runs on application startup
- Versioned: Tracks applied migrations
- Flexible: Works with local or external MongoDB (Atlas)

Usage:
    from app.database.mongodb.migrations import run_migrations

    # In startup
    await run_migrations()
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


class MongoDBMigration(ABC):
    """
    Base class for MongoDB migrations.

    Each migration should:
    - Have a unique version/name
    - Implement up() method for forward migration
    - Implement down() method for rollback (optional but recommended)
    - Be idempotent (safe to run multiple times)
    """

    def __init__(self):
        self.version: str = self.__class__.__name__
        self.applied_at: Optional[datetime] = None

    @abstractmethod
    async def up(self, db: AsyncIOMotorDatabase) -> None:
        """
        Apply the migration.

        Args:
            db: MongoDB database instance

        Raises:
            Exception: If migration fails
        """

    async def down(self, _db: AsyncIOMotorDatabase) -> None:
        """
        Rollback the migration (optional).

        Args:
            db: MongoDB database instance

        Note:
            Default implementation does nothing.
            Override if rollback is supported.
        """
        logger.warning("Migration %s does not implement rollback (down)", self.version)

    async def is_applied(self, db: AsyncIOMotorDatabase) -> bool:
        """
        Check if this migration has already been applied.

        Args:
            db: MongoDB database instance

        Returns:
            bool: True if migration was already applied
        """
        migrations_collection = db["_migrations"]
        result = await migrations_collection.find_one({"version": self.version})
        return result is not None

    async def mark_applied(self, db: AsyncIOMotorDatabase) -> None:
        """
        Mark this migration as applied.

        Args:
            db: MongoDB database instance
        """
        migrations_collection = db["_migrations"]
        self.applied_at = datetime.utcnow()
        await migrations_collection.update_one(
            {"version": self.version},
            {
                "$set": {
                    "version": self.version,
                    "applied_at": self.applied_at,
                    "class_name": self.__class__.__name__,
                }
            },
            upsert=True,
        )
        logger.info("Migration %s marked as applied", self.version)


class CreateRuntimeCollections(MongoDBMigration):
    """
    Initial migration: Create runtime collections and indexes.

    Converts logic from init-db.js to Python.
    Creates:
    - cells_runtime: Notebook cells (computational units)
    - books_runtime: Notebooks (collections of cells)
    - sessions_runtime: User sessions
    - users_runtime: User accounts
    - memory_runtime: Conversation memory
    - traces_runtime: Execution traces
    """

    async def up(self, db: AsyncIOMotorDatabase) -> None:
        """Create all runtime collections and their indexes."""
        logger.info("Creating runtime collections and indexes...")

        # List of collections to create
        collections = [
            "cells_runtime",
            "books_runtime",
            "sessions_runtime",
            "users_runtime",
            "memory_runtime",
            "traces_runtime",
        ]

        # Get existing collections
        existing_collections = await db.list_collection_names()

        # Create collections (idempotent - only if not exists)
        for collection_name in collections:
            if collection_name not in existing_collections:
                await db.create_collection(collection_name)
                logger.info("  ✓ Created collection: %s", collection_name)
            else:
                logger.debug("  → Collection already exists: %s", collection_name)

        # Create indexes for cells_runtime
        logger.info("Creating indexes for cells_runtime...")
        await self._create_index_if_not_exists(
            db.cells_runtime, "id", {"id": 1}, unique=True, name="idx_cells_id"
        )
        await self._create_index_if_not_exists(
            db.cells_runtime,
            "assignee_id",
            {"assignee_id": 1},
            name="idx_cells_assignee",
        )
        await self._create_index_if_not_exists(
            db.cells_runtime, "sessao_id", {"sessao_id": 1}, name="idx_cells_sessao"
        )
        await self._create_index_if_not_exists(
            db.cells_runtime, "usuario_id", {"usuario_id": 1}, name="idx_cells_usuario"
        )
        await self._create_index_if_not_exists(
            db.cells_runtime,
            "created_at",
            {"created_at": -1},
            name="idx_cells_created_at",
        )

        # Create indexes for books_runtime
        logger.info("Creating indexes for books_runtime...")
        await self._create_index_if_not_exists(
            db.books_runtime, "id", {"id": 1}, unique=True, name="idx_books_id"
        )
        await self._create_index_if_not_exists(
            db.books_runtime,
            "assignee_id",
            {"assignee_id": 1},
            name="idx_books_assignee",
        )
        await self._create_index_if_not_exists(
            db.books_runtime,
            "created_at",
            {"created_at": -1},
            name="idx_books_created_at",
        )

        # Create indexes for sessions_runtime
        logger.info("Creating indexes for sessions_runtime...")
        await self._create_index_if_not_exists(
            db.sessions_runtime, "id", {"id": 1}, unique=True, name="idx_sessions_id"
        )
        await self._create_index_if_not_exists(
            db.sessions_runtime,
            "usuario_id",
            {"usuario_id": 1},
            name="idx_sessions_usuario",
        )
        await self._create_index_if_not_exists(
            db.sessions_runtime,
            "created_at",
            {"created_at": -1},
            name="idx_sessions_created_at",
        )

        # Create indexes for users_runtime
        logger.info("Creating indexes for users_runtime...")
        await self._create_index_if_not_exists(
            db.users_runtime, "id", {"id": 1}, unique=True, name="idx_users_id"
        )
        await self._create_index_if_not_exists(
            db.users_runtime, "email", {"email": 1}, unique=True, name="idx_users_email"
        )

        # Create indexes for memory_runtime
        logger.info("Creating indexes for memory_runtime...")
        await self._create_index_if_not_exists(
            db.memory_runtime, "id", {"id": 1}, unique=True, name="idx_memory_id"
        )
        await self._create_index_if_not_exists(
            db.memory_runtime,
            "usuario_id",
            {"usuario_id": 1},
            name="idx_memory_usuario",
        )
        await self._create_index_if_not_exists(
            db.memory_runtime, "sessao_id", {"sessao_id": 1}, name="idx_memory_sessao"
        )

        # Create indexes for traces_runtime
        logger.info("Creating indexes for traces_runtime...")
        await self._create_index_if_not_exists(
            db.traces_runtime, "id", {"id": 1}, unique=True, name="idx_traces_id"
        )
        await self._create_index_if_not_exists(
            db.traces_runtime,
            "usuario_id",
            {"usuario_id": 1},
            name="idx_traces_usuario",
        )
        await self._create_index_if_not_exists(
            db.traces_runtime, "sessao_id", {"sessao_id": 1}, name="idx_traces_sessao"
        )
        await self._create_index_if_not_exists(
            db.traces_runtime,
            "created_at",
            {"created_at": -1},
            name="idx_traces_created_at",
        )

        logger.info("✓ All runtime collections and indexes created successfully")

    async def _create_index_if_not_exists(
        self,
        collection,
        field_name: str,
        keys: Dict[str, Any],
        unique: bool = False,
        name: Optional[str] = None,
    ) -> None:
        """
        Create an index if it doesn't already exist (idempotent).

        Args:
            collection: MongoDB collection
            field_name: Name of field for logging
            keys: Index specification
            unique: Whether index should be unique
            name: Optional index name
        """
        try:
            # Get existing indexes
            existing_indexes = await collection.list_indexes().to_list(length=None)
            index_names = [idx.get("name") for idx in existing_indexes]

            # Check if index with this name already exists
            if name and name in index_names:
                logger.debug("    → Index already exists: %s", name)
                return

            # Create the index
            await collection.create_index(keys, unique=unique, name=name)
            logger.info("    ✓ Created index on %s: %s", field_name, name or keys)

        except Exception as e:
            # If error is "index already exists", it's okay (idempotent)
            if "already exists" in str(e).lower():
                logger.debug("    → Index already exists: %s", name or field_name)
            else:
                logger.error("    ✗ Error creating index on %s: %s", field_name, e)
                raise


class CreateApplicationUser(MongoDBMigration):
    """
    Create application user with appropriate permissions.

    Note: This migration requires admin privileges to create users.
    If the user already exists, it will update the roles.

    Environment variables required:
    - MONGODB_APP_USERNAME (default: scareverse)
    - MONGODB_APP_PASSWORD (default: scareverse-dev-password)
    """

    async def up(self, db: AsyncIOMotorDatabase) -> None:
        """Create or update application user."""
        import os

        from ...config.database import MONGODB_DATABASE

        app_user = os.getenv("MONGODB_APP_USERNAME", "scareverse")
        app_password = os.getenv("MONGODB_APP_PASSWORD", "scareverse-dev-password")

        logger.info("Ensuring application user '%s' exists...", app_user)

        try:
            # Check if user exists
            users = await db.command("usersInfo", app_user)
            user_exists = len(users.get("users", [])) > 0

            if user_exists:
                # Update user roles
                logger.info("  → User '%s' already exists, updating roles...", app_user)
                await db.command(
                    "updateUser",
                    app_user,
                    roles=[
                        {"role": "readWrite", "db": MONGODB_DATABASE},
                        {"role": "dbAdmin", "db": MONGODB_DATABASE},
                    ],
                )
                logger.info("  ✓ User '%s' roles updated", app_user)
            else:
                # Create user
                logger.info("  → Creating user '%s'...", app_user)
                await db.command(
                    "createUser",
                    app_user,
                    pwd=app_password,
                    roles=[
                        {"role": "readWrite", "db": MONGODB_DATABASE},
                        {"role": "dbAdmin", "db": MONGODB_DATABASE},
                    ],
                )
                logger.info("  ✓ User '%s' created successfully", app_user)

        except PyMongoError as e:
            # If we don't have admin privileges, log warning but don't fail
            error_msg = str(e).lower()
            if "not authorized" in error_msg or "requires authentication" in error_msg:
                logger.warning("  ⚠ Cannot manage users (insufficient privileges): %s", e)
                logger.warning("    User '%s' must be created manually by admin", app_user)
                logger.warning(
                    "    This is expected when connecting to Atlas or other managed MongoDB"
                )
            else:
                logger.error("  ✗ Error managing user: %s", e)
                raise


class CreateContentsCollection(MongoDBMigration):
    """
    Migration: Create contents_runtime collection with schema validation and indexes.

    Stores content metadata for:
    - Images (image-png, image-jpeg)
    - Vectors (vector-svg)
    - 3D Models (3d-glb)
    - Other typed content assets

    Tracks:
    - Storage reference (data_ref) for R2/local
    - Versioning and lineage
    - Origin cell and generation metadata
    - Content fragments and custom metadata

    CRITICAL: This collection is used by ContentManager service for atomic
    persistence operations. The data_ref field has a unique index to prevent
    duplicate file tracking and enable orphaned file detection.
    """

    async def up(self, db: AsyncIOMotorDatabase) -> None:
        """Create contents_runtime collection with indexes and validation."""
        logger.info("Creating contents_runtime collection...")

        # Get existing collections
        existing_collections = await db.list_collection_names()

        # Create collection if it doesn't exist
        if "contents_runtime" not in existing_collections:
            await db.create_collection("contents_runtime")
            logger.info("  ✓ Created collection: contents_runtime")
        else:
            logger.debug("  → Collection already exists: contents_runtime")

        # Create indexes
        logger.info("Creating indexes for contents_runtime...")

        # Unique index on id (primary key)
        await self._create_index_if_not_exists(
            db.contents_runtime, "id", {"id": 1}, unique=True, name="idx_contents_id"
        )

        # Index on content_type_id for filtering by type
        await self._create_index_if_not_exists(
            db.contents_runtime,
            "content_type_id",
            {"content_type_id": 1},
            name="idx_contents_type",
        )

        # Index on assignee_id for filtering by owner
        await self._create_index_if_not_exists(
            db.contents_runtime,
            "assignee_id",
            {"assignee_id": 1},
            name="idx_contents_assignee",
        )

        # Index on created_at for sorting/filtering by date
        await self._create_index_if_not_exists(
            db.contents_runtime,
            "created_at",
            {"created_at": -1},
            name="idx_contents_created_at",
        )

        # Index on tags for tag-based queries
        await self._create_index_if_not_exists(
            db.contents_runtime, "tags", {"tags": 1}, name="idx_contents_tags"
        )

        # CRITICAL: Unique index on data_ref to prevent duplicate file tracking
        # and enable orphaned file detection
        await self._create_index_if_not_exists(
            db.contents_runtime,
            "data_ref",
            {"data_ref": 1},
            unique=True,
            name="idx_contents_data_ref",
        )

        # Index on status for filtering by lifecycle state
        await self._create_index_if_not_exists(
            db.contents_runtime, "status", {"status": 1}, name="idx_contents_status"
        )

        # Index on origin_cell_id for lineage tracking
        await self._create_index_if_not_exists(
            db.contents_runtime,
            "origin_cell_id",
            {"origin_cell_id": 1},
            name="idx_contents_origin",
        )

        # Add schema validation
        try:
            await db.command(
                {
                    "collMod": "contents_runtime",
                    "validator": {
                        "$jsonSchema": {
                            "bsonType": "object",
                            "required": [
                                "id",
                                "content_type_id",
                                "assignee_id",
                                "data_ref",
                            ],
                            "properties": {
                                "id": {
                                    "bsonType": "string",
                                    "description": "Unique content identifier (UUID)",
                                },
                                "content_type_id": {
                                    "bsonType": "string",
                                    "description": "ContentType identifier (e.g., 'image-png')",
                                },
                                "assignee_id": {
                                    "bsonType": "string",
                                    "description": "Owner user ID",
                                },
                                "data_ref": {
                                    "bsonType": "string",
                                    "description": "Storage reference (e.g., 'r2://bucket/path' or 'file:///path')",
                                },
                                "status": {
                                    "enum": ["pending", "live", "deleted"],
                                    "description": "Content lifecycle status",
                                },
                                "version": {
                                    "bsonType": "int",
                                    "minimum": 1,
                                    "description": "Content version number",
                                },
                            },
                        }
                    },
                    "validationLevel": "moderate",
                    "validationAction": "warn",
                }
            )
            logger.info("  ✓ Schema validation configured for contents_runtime")
        except Exception as e:
            # Schema validation is optional - log warning but continue
            logger.warning("  ⚠ Could not set schema validation: %s", e)

        logger.info("✓ contents_runtime collection created successfully")

    async def down(self, db: AsyncIOMotorDatabase) -> None:
        """Rollback: Drop contents_runtime collection."""
        logger.info("Rolling back contents_runtime collection...")
        await db.drop_collection("contents_runtime")
        logger.info("✓ contents_runtime collection dropped")

    async def _create_index_if_not_exists(
        self,
        collection,
        field_name: str,
        keys: Dict[str, Any],
        unique: bool = False,
        name: Optional[str] = None,
    ) -> None:
        """
        Create an index if it doesn't already exist (idempotent).

        Args:
            collection: MongoDB collection
            field_name: Name of field for logging
            keys: Index specification
            unique: Whether index should be unique
            name: Optional index name
        """
        try:
            # Get existing indexes
            existing_indexes = await collection.list_indexes().to_list(length=None)
            index_names = [idx.get("name") for idx in existing_indexes]

            # Check if index with this name already exists
            if name and name in index_names:
                logger.debug("    → Index already exists: %s", name)
                return

            # Create the index
            await collection.create_index(keys, unique=unique, name=name)
            logger.info("    ✓ Created index on %s: %s", field_name, name or keys)

        except Exception as e:
            # If error is "index already exists", it's okay (idempotent)
            if "already exists" in str(e).lower():
                logger.debug("    → Index already exists: %s", name or field_name)
            else:
                logger.error("    ✗ Error creating index on %s: %s", field_name, e)
                raise


class UnifiedNotebookItemsMigration(MongoDBMigration):
    """
    Migration 0002: Unified notebook_items_runtime collection.

    Creates a unified collection for both cells and books with a 'kind' discriminator field.
    This enables:
    - Single collection for all notebook items
    - Type-safe discrimination via 'kind' field
    - Foundation for ExecutionFragment hierarchy
    - Simplified query patterns

    Creates indexes for:
    - id (unique): Primary identifier
    - kind (discriminator): "cell" or "book"
    - assignee_id (ownership): User ownership queries
    - status: Filter by status
    - created_at: Time-based queries
    """

    async def up(self, db: AsyncIOMotorDatabase) -> None:
        """Create unified notebook_items_runtime collection with indexes."""
        logger.info("Creating unified notebook_items_runtime collection...")

        collection_name = "notebook_items_runtime"

        # Get existing collections
        existing_collections = await db.list_collection_names()

        # Create collection if it doesn't exist (MongoDB auto-creates on first insert, but explicit is better)
        if collection_name not in existing_collections:
            await db.create_collection(collection_name)
            logger.info("  ✓ Created collection: %s", collection_name)
        else:
            logger.debug("  → Collection already exists: %s", collection_name)

        # Create indexes
        logger.info("Creating indexes for %s...", collection_name)
        collection = db[collection_name]

        # Primary key: id (unique)
        await self._create_index_if_not_exists(
            collection, "id", {"id": 1}, unique=True, name="idx_notebook_items_id"
        )

        # Kind discriminator (essential for queries)
        await self._create_index_if_not_exists(
            collection, "kind", {"kind": 1}, name="idx_notebook_items_kind"
        )

        # Ownership index
        await self._create_index_if_not_exists(
            collection,
            "assignee_id",
            {"assignee_id": 1},
            name="idx_notebook_items_assignee",
        )

        # Status index (for filtering)
        await self._create_index_if_not_exists(
            collection, "status", {"status": 1}, name="idx_notebook_items_status"
        )

        # Created timestamp index (for time-based queries)
        await self._create_index_if_not_exists(
            collection,
            "created_at",
            {"created_at": -1},
            name="idx_notebook_items_created_at",
        )

        # Compound index for common query pattern: kind + assignee_id
        await self._create_index_if_not_exists(
            collection,
            "kind_assignee",
            {"kind": 1, "assignee_id": 1},
            name="idx_notebook_items_kind_assignee",
        )

        logger.info("✓ %s collection and indexes created successfully", collection_name)

    async def down(self, db: AsyncIOMotorDatabase) -> None:
        """Drop the unified collection (rollback)."""
        collection_name = "notebook_items_runtime"
        logger.info("Rolling back: dropping %s...", collection_name)
        await db.drop_collection(collection_name)
        logger.info("✓ %s dropped successfully", collection_name)

    async def _create_index_if_not_exists(
        self,
        collection,
        field_name: str,
        keys: Dict[str, Any],
        unique: bool = False,
        name: Optional[str] = None,
    ) -> None:
        """
        Create an index if it doesn't already exist (idempotent).

        Args:
            collection: MongoDB collection
            field_name: Name of field for logging
            keys: Index specification
            unique: Whether index should be unique
            name: Optional index name
        """
        try:
            # Get existing indexes
            existing_indexes = await collection.list_indexes().to_list(length=None)
            index_names = [idx.get("name") for idx in existing_indexes]

            # Check if index with this name already exists
            if name and name in index_names:
                logger.debug("    → Index already exists: %s", name)
                return

            # Create the index
            await collection.create_index(keys, unique=unique, name=name)
            logger.info("    ✓ Created index on %s: %s", field_name, name or keys)

        except Exception as e:
            # If error is "index already exists", it's okay (idempotent)
            if "already exists" in str(e).lower():
                logger.debug("    → Index already exists: %s", name or field_name)
            else:
                logger.error("    ✗ Error creating index on %s: %s", field_name, e)
                raise


async def run_migrations(client: Optional[AsyncIOMotorClient] = None) -> Dict[str, Any]:
    """
    Run all pending migrations.

    This function:
    1. Connects to MongoDB (if client not provided)
    2. Creates migrations tracking collection if needed
    3. Runs all migrations that haven't been applied yet
    4. Tracks migration status

    Args:
        client: Optional MongoDB client (will create one if not provided)

    Returns:
        dict: Migration results with status and details

    Example:
        result = await run_migrations()
        # {'status': 'success', 'applied': 2, 'skipped': 0, 'failed': 0}
    """
    from ...config.database import MONGODB_ENABLED
    from .client import get_mongodb_client, get_mongodb_database

    if not MONGODB_ENABLED:
        logger.info("MongoDB is disabled - skipping migrations")
        return {
            "status": "skipped",
            "reason": "MongoDB is disabled",
            "applied": 0,
            "skipped": 0,
            "failed": 0,
        }

    # Get MongoDB client and database
    if client is None:
        client = await get_mongodb_client()

    if client is None:
        logger.warning("Cannot run migrations - MongoDB client unavailable")
        return {
            "status": "error",
            "reason": "MongoDB client unavailable",
            "applied": 0,
            "skipped": 0,
            "failed": 0,
        }

    db = await get_mongodb_database()
    if db is None:
        logger.warning("Cannot run migrations - MongoDB database unavailable")
        return {
            "status": "error",
            "reason": "MongoDB database unavailable",
            "applied": 0,
            "skipped": 0,
            "failed": 0,
        }

    # Ensure migrations collection exists
    collections = await db.list_collection_names()
    if "_migrations" not in collections:
        await db.create_collection("_migrations")
        logger.info("Created migrations tracking collection: _migrations")

    # Define all migrations in order
    migrations: List[MongoDBMigration] = [
        CreateRuntimeCollections(),
        CreateApplicationUser(),
        CreateContentsCollection(),
        UnifiedNotebookItemsMigration(),
    ]

    # Run migrations
    applied = 0
    skipped = 0
    failed = 0

    logger.info("=" * 70)
    logger.info("Starting MongoDB migrations...")
    logger.info("=" * 70)

    for migration in migrations:
        try:
            # Check if already applied
            if await migration.is_applied(db):
                logger.info("⏭  SKIP: %s (already applied)", migration.version)
                skipped += 1
                continue

            # Run migration
            logger.info("🚀 APPLYING: %s...", migration.version)
            await migration.up(db)
            await migration.mark_applied(db)
            logger.info("✅ SUCCESS: %s", migration.version)
            applied += 1

        except Exception as e:
            logger.error("❌ FAILED: %s", migration.version)
            logger.error("   Error: %s: %s", type(e).__name__, e)
            failed += 1

            # Stop on first failure to prevent cascade issues
            logger.error("Stopping migrations due to failure")
            break

    logger.info("=" * 70)
    logger.info("Migration results: %s applied, %s skipped, %s failed", applied, skipped, failed)
    logger.info("=" * 70)

    status = "success" if failed == 0 else "partial" if applied > 0 else "failed"

    return {
        "status": status,
        "applied": applied,
        "skipped": skipped,
        "failed": failed,
        "total": len(migrations),
    }
