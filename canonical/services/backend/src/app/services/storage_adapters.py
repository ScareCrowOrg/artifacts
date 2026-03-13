"""
Storage abstraction layer for content data.

Provides interfaces and adapters for storing content raw data:
- StorageAdapter: Interface for storage backends
- LocalStorageAdapter: Local filesystem storage
- Future: CloudStorageAdapter for S3/GCS/Azure
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..models.content_types import StoragePolicy

logger = logging.getLogger(__name__)


class StorageAdapter(ABC):
    """
    Abstract interface for storage backends.

    Defines the contract that all storage adapters must implement:
    - store: Save content data
    - retrieve: Get content data
    - delete: Remove content data
    - exists: Check if content exists
    - get_url: Get public URL for content
    """

    @abstractmethod
    def store(
        self,
        content_id: str,
        data: bytes,
        filename: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Store content data.

        Args:
            content_id: Unique content identifier
            data: Raw bytes to store
            filename: Optional original filename
            metadata: Optional metadata dict

        Returns:
            Data reference (URL/path) for accessing the stored data
        """

    @abstractmethod
    def retrieve(self, data_ref: str) -> bytes:
        """
        Retrieve content data.

        Args:
            data_ref: Data reference from store()

        Returns:
            Raw bytes of the content

        Raises:
            FileNotFoundError: If content doesn't exist
        """

    @abstractmethod
    def delete(self, data_ref: str) -> bool:
        """
        Delete content data.

        Args:
            data_ref: Data reference to delete

        Returns:
            True if deleted, False if not found
        """

    @abstractmethod
    def exists(self, data_ref: str) -> bool:
        """
        Check if content exists.

        Args:
            data_ref: Data reference to check

        Returns:
            True if exists, False otherwise
        """

    @abstractmethod
    def get_url(self, data_ref: str) -> str:
        """
        Get public URL for content.

        Args:
            data_ref: Data reference

        Returns:
            Public URL (may be same as data_ref for local storage)
        """


class LocalStorageAdapter(StorageAdapter):
    """
    Local filesystem storage adapter.

    Stores content in local filesystem with organized directory structure:
    - Base path: /data/content/<content_type>/
    - Files: <content_id>.<ext>

    Data refs use file:// protocol.
    """

    def __init__(self, base_path: str = None):
        """
        Initialize local storage adapter.

        Args:
            base_path: Base directory for storage (default: /data/content)
        """
        if base_path is None:
            from ..config import BASE_DIR

            base_path = BASE_DIR / "data" / "content"

        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorageAdapter initialized: %s", self.base_path)

    def _get_file_path(self, content_id: str, filename: Optional[str] = None) -> Path:
        """
        Get file path for content.

        Args:
            content_id: Content identifier
            filename: Original filename (to extract extension)

        Returns:
            Full file path
        """
        # Extract extension from filename
        ext = ""
        if filename:
            ext = Path(filename).suffix

        # Create subdirectory based on first 2 chars of content_id (sharding)
        subdir = content_id[:2]
        dir_path = self.base_path / subdir
        dir_path.mkdir(parents=True, exist_ok=True)

        return dir_path / f"{content_id}{ext}"

    def _data_ref_to_path(self, data_ref: str) -> Path:
        """
        Convert data_ref (file:// URL) to file path.

        Args:
            data_ref: Data reference

        Returns:
            File path
        """
        if data_ref.startswith("file://"):
            # Remove file:// prefix
            path_str = data_ref[7:]
            return Path(path_str)

        # Assume it's already a path
        return Path(data_ref)

    def store(
        self,
        content_id: str,
        data: bytes,
        filename: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Store content data to local filesystem."""
        file_path = self._get_file_path(content_id, filename)

        # Write data
        with open(file_path, "wb") as f:
            f.write(data)

        logger.info("Stored content: %s -> %s", content_id, file_path)

        # Return data_ref with file:// protocol
        return f"file://{file_path}"

    def retrieve(self, data_ref: str) -> bytes:
        """Retrieve content data from local filesystem."""
        file_path = self._data_ref_to_path(data_ref)

        if not file_path.exists():
            raise FileNotFoundError(f"Content not found: {data_ref}")

        with open(file_path, "rb") as f:
            return f.read()

    def delete(self, data_ref: str) -> bool:
        """Delete content data from local filesystem."""
        file_path = self._data_ref_to_path(data_ref)

        if not file_path.exists():
            return False

        file_path.unlink()
        logger.info("Deleted content: %s", data_ref)
        return True

    def exists(self, data_ref: str) -> bool:
        """Check if content exists in local filesystem."""
        file_path = self._data_ref_to_path(data_ref)
        return file_path.exists()

    def get_url(self, data_ref: str) -> str:
        """Get URL for local content (returns data_ref as-is)."""
        return data_ref

    def calculate_checksum(self, data: bytes) -> str:
        """
        Calculate SHA-256 checksum for data.

        Args:
            data: Raw bytes

        Returns:
            Hex string of checksum
        """
        return hashlib.sha256(data).hexdigest()


class StorageFactory:
    """
    Factory for creating storage adapters based on policy.

    Maps StoragePolicy to appropriate StorageAdapter implementation.
    """

    _adapters = {}

    @classmethod
    def get_adapter(cls, policy: StoragePolicy) -> StorageAdapter:
        """
        Get storage adapter for policy.

        Args:
            policy: Storage policy

        Returns:
            StorageAdapter instance

        Raises:
            NotImplementedError: If policy not supported
        """
        # Cache adapters (singleton pattern)
        if policy in cls._adapters:
            return cls._adapters[policy]

        if policy == StoragePolicy.LOCAL:
            adapter = LocalStorageAdapter()
        elif policy == StoragePolicy.CLOUD:
            # Future: CloudStorageAdapter()
            raise NotImplementedError("Cloud storage not yet implemented")
        elif policy == StoragePolicy.REPO:
            # Future: RepoStorageAdapter (Git LFS)
            raise NotImplementedError("Repo storage not yet implemented")
        else:
            raise ValueError(f"Unknown storage policy: {policy}")

        cls._adapters[policy] = adapter
        return adapter
