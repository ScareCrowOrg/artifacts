"""
Sandbox Operations - Local file-based storage for user-private draft artifacts.

This module provides methods for reading and writing artifacts to the
sandbox directory (artifacts/sandbox/{user_id}/*). Sandbox artifacts are:
- User-private (never published to MongoDB)
- Local-only (never leave ScareRunner)
- Draft/experimental (can be explicitly published later)

Security:
- User isolation via user_id in path
- No cross-user access
- Excluded from Git (.gitignore)
- Excluded from backups (local-only)

Directory Structure:
artifacts/sandbox/{user_id}/{artifact_id}/metadata.json
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from ...config.database import BASE_DIR

logger = logging.getLogger(__name__)

# Sandbox root directory
SANDBOX_DIR = BASE_DIR / "artifacts" / "sandbox"


class SandboxOperations:
    """
    File operations for sandbox (user-private) artifacts.

    Provides CRUD operations on artifacts/sandbox/{user_id}/* directory.
    """

    def __init__(self, sandbox_dir: Optional[Path] = None):
        """
        Initialize sandbox operations.

        Args:
            sandbox_dir: Root sandbox directory (defaults to artifacts/sandbox/)
        """
        self.sandbox_dir = sandbox_dir or SANDBOX_DIR
        self._ensure_sandbox_dir()

    def _ensure_sandbox_dir(self):
        """Ensure sandbox root directory exists."""
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Sandbox directory ensured: %s", self.sandbox_dir)

    def _get_user_sandbox_path(self, user_id: str) -> Path:
        """
        Get sandbox path for a specific user.

        Args:
            user_id: User ID

        Returns:
            Path to user's sandbox directory
        """
        return self.sandbox_dir / user_id

    def _get_artifact_path(self, user_id: str, artifact_id: str) -> Path:
        """
        Get path to artifact directory in sandbox.

        Args:
            user_id: User ID
            artifact_id: Artifact ID

        Returns:
            Path to artifact directory
        """
        return self._get_user_sandbox_path(user_id) / artifact_id

    def _get_metadata_path(self, user_id: str, artifact_id: str) -> Path:
        """
        Get path to artifact metadata.json file.

        Args:
            user_id: User ID
            artifact_id: Artifact ID

        Returns:
            Path to metadata.json file
        """
        return self._get_artifact_path(user_id, artifact_id) / "metadata.json"

    def find_in_sandbox(
        self, user_id: str, artifact_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find artifact in user's sandbox.

        Args:
            user_id: User ID
            artifact_id: Artifact ID

        Returns:
            Artifact metadata dict or None if not found
        """
        if not user_id:
            logger.warning("find_in_sandbox called without user_id")
            return None

        metadata_path = self._get_metadata_path(user_id, artifact_id)

        if not metadata_path.exists():
            logger.debug("Artifact not found in sandbox: %s", metadata_path)
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            logger.debug("Found artifact in sandbox: %s (user=%s)", artifact_id, user_id)
            return metadata
        except Exception as e:
            logger.error("Error reading sandbox artifact: %s, error=%s", metadata_path, e)
            return None

    def insert_to_sandbox(
        self, user_id: str, document: Dict[str, Any]
    ) -> Optional[str]:
        """
        Insert artifact into user's sandbox.

        Args:
            user_id: User ID
            document: Artifact metadata dict (must contain "_id" field)

        Returns:
            Artifact ID or None if insert failed
        """
        if not user_id:
            logger.error("insert_to_sandbox called without user_id")
            return None

        artifact_id = document.get("_id")
        if not artifact_id:
            logger.error("insert_to_sandbox: document missing '_id' field")
            return None

        # Create artifact directory
        artifact_path = self._get_artifact_path(user_id, artifact_id)
        try:
            artifact_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error("Error creating sandbox artifact directory: %s, error=%s", artifact_path, e)
            return None

        # Write metadata.json
        metadata_path = self._get_metadata_path(user_id, artifact_id)
        try:
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(document, f, indent=2, ensure_ascii=False)
            logger.info("Inserted artifact to sandbox: %s (user=%s)", artifact_id, user_id)
            return artifact_id
        except Exception as e:
            logger.error("Error writing sandbox artifact: %s, error=%s", metadata_path, e)
            return None

    def update_in_sandbox(
        self, user_id: str, artifact_id: str, updates: Dict[str, Any]
    ) -> bool:
        """
        Update artifact in user's sandbox.

        Args:
            user_id: User ID
            artifact_id: Artifact ID
            updates: Dictionary of field updates

        Returns:
            True if update successful, False otherwise
        """
        if not user_id:
            logger.error("update_in_sandbox called without user_id")
            return False

        metadata_path = self._get_metadata_path(user_id, artifact_id)

        if not metadata_path.exists():
            logger.warning("Cannot update: artifact not found in sandbox: %s (user=%s)", artifact_id, user_id)
            return False

        try:
            # Read existing metadata
            with open(metadata_path, "r", encoding="utf-8") as f:
                document = json.load(f)

            # Apply updates
            document.update(updates)

            # Write back
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(document, f, indent=2, ensure_ascii=False)

            logger.info("Updated artifact in sandbox: %s (user=%s)", artifact_id, user_id)
            return True
        except Exception as e:
            logger.error("Error updating sandbox artifact: %s, error=%s", metadata_path, e)
            return False

    def delete_from_sandbox(self, user_id: str, artifact_id: str) -> bool:
        """
        Delete artifact from user's sandbox.

        Args:
            user_id: User ID
            artifact_id: Artifact ID

        Returns:
            True if delete successful, False otherwise
        """
        if not user_id:
            logger.error("delete_from_sandbox called without user_id")
            return False

        artifact_path = self._get_artifact_path(user_id, artifact_id)

        if not artifact_path.exists():
            logger.warning("Cannot delete: artifact not found in sandbox: %s (user=%s)", artifact_id, user_id)
            return False

        try:
            # Remove metadata.json
            metadata_path = self._get_metadata_path(user_id, artifact_id)
            if metadata_path.exists():
                os.remove(metadata_path)

            # Remove artifact directory if empty
            try:
                artifact_path.rmdir()
            except OSError:
                # Directory not empty, leave it
                logger.debug("Sandbox artifact directory not empty, keeping: %s", artifact_path)

            logger.info("Deleted artifact from sandbox: %s (user=%s)", artifact_id, user_id)
            return True
        except Exception as e:
            logger.error("Error deleting sandbox artifact: %s, error=%s", artifact_path, e)
            return False
