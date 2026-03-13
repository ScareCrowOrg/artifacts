"""
Core JSONDatabase class with path management and initialization.

Provides a simple file-based JSON storage system that mimics MongoDB operations.
Designed as a lightweight solution for MVP, easily replaceable with MongoDB later.

Storage Structure:
- artifacts/runtime/{collection}/{user_id}/{session_id}/{id}.json
- artifacts/canonical/{collection}/{id}.json
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from ..config.database import ARTIFACTS_DIR
from .config_ops import ConfigOperations
from .operations import CRUDOperations

logger = logging.getLogger(__name__)


class JSONDatabase(CRUDOperations, ConfigOperations):
    """
    Simple JSON file-based database for MVP1.

    Provides basic CRUD operations with file-based persistence.
    Each document is stored as a separate JSON file.
    """

    def __init__(self, base_path: Optional[Path] = None, is_test_env: bool = False):
        """
        Initialize the JSON database.

        Args:
            base_path: Base path for artifact storage.
                       Defaults to SCAREFERA_LAB_DIR/artifacts for runtime.
                       For tests, it should be a temporary path.
            is_test_env: Flag to indicate if running in a test environment.
                         If true, a temporary path will be used if base_path is None,
                         and a cleanup method will be available.
        """
        self.is_test_env = is_test_env

        if base_path is None:
            if self.is_test_env:
                # For tests, create a unique temporary directory
                import tempfile

                self._temp_dir = tempfile.TemporaryDirectory()
                base_path = Path(self._temp_dir.name) / "artifacts_test"
            else:
                # For runtime, use the configured path from config.database
                base_path = ARTIFACTS_DIR
        else:
            logger.info("JSONDatabase initialized with explicit path: %s (is_test_env=%s)", base_path, is_test_env)

        self.base_path = Path(base_path)
        self.runtime_path = self.base_path / "runtime"
        self.canonical_path = self.base_path / "canonical"

        # Ensure base directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all required directories exist."""
        directories = [
            self.base_path,
            self.runtime_path,
            self.canonical_path,
            self.runtime_path / "cells",
            self.runtime_path / "books",
            self.runtime_path / "ai_models",
            self.runtime_path / "memory",
            self.runtime_path / "users",
            self.runtime_path / "sessions",
            self.canonical_path / "cells",
            self.canonical_path / "books",
            self.canonical_path / "templates",
            self.canonical_path / "ai_models",
            self.canonical_path / "agent_types",
            self.canonical_path / "notebook_item_types",
            self.canonical_path / "permissions",
            self.canonical_path / "roles",
            self.canonical_path / "workflows",
            self.base_path / "config",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def cleanup_test_data(self):
        """Removes all data created by the test database instance."""
        if self.is_test_env and hasattr(self, "_temp_dir"):
            logger.info("Cleaning up test data from %s", self.base_path)
            self._temp_dir.cleanup()
            # Re-create directories for subsequent tests in the same session if needed
            self._ensure_directories()
        elif self.is_test_env and self.base_path.exists():
            # If a base_path was explicitly provided for testing, clear it
            logger.info("Cleaning up explicit test data path: %s", self.base_path)
            shutil.rmtree(self.base_path)
            self._ensure_directories()
        else:
            logger.warning(
                "Attempted to cleanup non-test or non-temporary JSONDatabase. No action taken."
            )

    def _get_collection_path(self, collection: str, is_canonical: bool = False) -> Path:
        """
        Get the path for a collection.

        Args:
            collection: Name of the collection (e.g., 'cells', 'books')
            is_canonical: Whether this is a canonical artifact

        Returns:
            Path to the collection directory
        """
        if is_canonical:
            return self.canonical_path / collection
        else:
            return self.runtime_path / collection

    def _get_document_path(
        self,
        collection: str,
        doc_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> Path:
        """
        Get the full path for a document.

        Args:
            collection: Collection name
            doc_id: Document ID
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            Path to the document file
        """
        collection_path = self._get_collection_path(collection, is_canonical)

        if is_canonical:
            # Canonical artifacts: canonical/{collection}/{id}.json
            # Ensure collection directory exists
            collection_path.mkdir(parents=True, exist_ok=True)
            return collection_path / f"{doc_id}.json"
        else:
            # Runtime artifacts: runtime/{collection}/{user_id}/{session_id}/{id}.json
            # or runtime/{collection}/{id}.json if no user/session
            if user_id and session_id:
                doc_path = collection_path / user_id / session_id
                doc_path.mkdir(parents=True, exist_ok=True)
                return doc_path / f"{doc_id}.json"
            else:
                # Ensure collection directory exists for runtime artifacts too
                collection_path.mkdir(parents=True, exist_ok=True)
                return collection_path / f"{doc_id}.json"


# Global database instance management
# NOTE: Changed from JSONDatabase to HybridDatabase to enable intelligent routing
# between file-based storage (canonical data) and MongoDB (runtime data).
# This ensures runtime data uses MongoDB when enabled, as required by issue #973.
#
# Phase 1B: Added Redis L1 client and CentralHub client for unified cache facade
# and sandbox operations.
db: Optional["HybridDatabase"] = None


def initialize_db() -> "HybridDatabase":
    """
    Initialize HybridDatabase instance AFTER logging is configured.

    This function must be called during app lifespan startup, NOT at module import time.
    This ensures logging is properly configured before CanonicalQueryEngine logs anything.
    """
    global db

    if os.getenv("TEST_ENV") == "true":
        logger.info("HybridDatabase initialization skipped for TEST_ENV")
        return None

    # Import HybridDatabase here to avoid circular imports
    from .hybrid import HybridDatabase
    from .phase1b_init import get_centralhub_client, get_redis_l1_client

    # Initialize Phase 1B clients (optional, gracefully degrade if unavailable)
    redis_l1_client = None
    centralhub_client = None
    try:
        redis_l1_client = get_redis_l1_client()
    except Exception as e:
        logger.warning("Failed to initialize Redis L1 client: %s", e)

    try:
        centralhub_client = get_centralhub_client()
    except Exception as e:
        logger.warning("Failed to initialize CentralHub client: %s", e)

    # Initialize HybridDatabase with Phase 1B support
    # Use BASE_DIR env var for Docker, fallback to artifacts/ for development
    base_dir = os.getenv("BASE_DIR", ".")
    base_path = Path(base_dir) / "artifacts"

    logger.info("[DATABASE] Initializing HybridDatabase with base_path=%s", base_path)
    db = HybridDatabase(
        base_path=base_path,
        is_test_env=False,
        redis_client=redis_l1_client,
        centralhub_client=centralhub_client,
    )
    logger.info(
        "[DATABASE] HybridDatabase initialized successfully with Phase 1B support"
    )
    return db


def get_db_instance() -> "HybridDatabase":
    """
    Returns the appropriate HybridDatabase instance.

    For runtime, returns the global 'db' instance (HybridDatabase).
    For tests, expects a mocked instance to be provided (e.g., via pytest monkeypatch).

    NOTE: Changed from JSONDatabase to HybridDatabase to enable intelligent routing
    between file-based storage (canonical data) and MongoDB (runtime data).
    """
    global db

    if os.getenv("TEST_ENV") == "true":
        if db is None:
            raise RuntimeError(
                "JSONDatabase not initialized for TEST_ENV. Use a pytest fixture."
            )
        return db
    else:
        if db is None:
            db = JSONDatabase(is_test_env=False)
        return db
