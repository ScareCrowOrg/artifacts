"""
Unit tests for SandboxOperations - Phase 1B.

Tests sandbox file operations (create, read, update, delete) for user-private artifacts.
"""

import pytest
import json
from pathlib import Path
from app.database.hybrid.sandbox_ops import SandboxOperations


@pytest.fixture
def temp_sandbox_dir(tmp_path):
    """Create a temporary sandbox directory for testing."""
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    return sandbox_dir


@pytest.fixture
def sandbox_ops(temp_sandbox_dir):
    """Create SandboxOperations instance with temp directory."""
    return SandboxOperations(sandbox_dir=temp_sandbox_dir)


class TestSandboxOperations:
    """Test suite for SandboxOperations."""

    def test_init_creates_sandbox_dir(self, tmp_path):
        """Test that initialization creates sandbox directory."""
        sandbox_dir = tmp_path / "new_sandbox"
        assert not sandbox_dir.exists()

        ops = SandboxOperations(sandbox_dir=sandbox_dir)
        assert sandbox_dir.exists()
        assert ops.sandbox_dir == sandbox_dir

    def test_insert_to_sandbox_creates_artifact(self, sandbox_ops, temp_sandbox_dir):
        """Test inserting artifact to sandbox creates metadata.json."""
        user_id = "user-123"
        artifact_id = "artifact-001"
        document = {
            "_id": artifact_id,
            "name": "Test Artifact",
            "type": "cell",
            "data": "test data",
        }

        result_id = sandbox_ops.insert_to_sandbox(user_id, document)

        assert result_id == artifact_id

        # Verify file was created
        metadata_path = temp_sandbox_dir / user_id / artifact_id / "metadata.json"
        assert metadata_path.exists()

        # Verify content
        with open(metadata_path, "r") as f:
            saved_doc = json.load(f)
        assert saved_doc == document

    def test_insert_to_sandbox_without_user_id_fails(self, sandbox_ops):
        """Test that insert without user_id returns None."""
        document = {"_id": "artifact-001", "name": "Test"}
        result = sandbox_ops.insert_to_sandbox("", document)
        assert result is None

    def test_insert_to_sandbox_without_id_fails(self, sandbox_ops):
        """Test that insert without _id field returns None."""
        document = {"name": "Test"}
        result = sandbox_ops.insert_to_sandbox("user-123", document)
        assert result is None

    def test_find_in_sandbox_returns_artifact(self, sandbox_ops, temp_sandbox_dir):
        """Test finding artifact in sandbox."""
        user_id = "user-123"
        artifact_id = "artifact-001"
        document = {"_id": artifact_id, "name": "Test Artifact"}

        # Insert first
        sandbox_ops.insert_to_sandbox(user_id, document)

        # Find it
        result = sandbox_ops.find_in_sandbox(user_id, artifact_id)

        assert result is not None
        assert result["_id"] == artifact_id
        assert result["name"] == "Test Artifact"

    def test_find_in_sandbox_nonexistent_returns_none(self, sandbox_ops):
        """Test finding nonexistent artifact returns None."""
        result = sandbox_ops.find_in_sandbox("user-123", "nonexistent")
        assert result is None

    def test_find_in_sandbox_without_user_id_returns_none(self, sandbox_ops):
        """Test finding without user_id returns None."""
        result = sandbox_ops.find_in_sandbox("", "artifact-001")
        assert result is None

    def test_update_in_sandbox_modifies_artifact(self, sandbox_ops):
        """Test updating artifact in sandbox."""
        user_id = "user-123"
        artifact_id = "artifact-001"
        document = {"_id": artifact_id, "name": "Original", "count": 1}

        # Insert first
        sandbox_ops.insert_to_sandbox(user_id, document)

        # Update
        updates = {"name": "Updated", "count": 2}
        result = sandbox_ops.update_in_sandbox(user_id, artifact_id, updates)

        assert result is True

        # Verify update
        updated_doc = sandbox_ops.find_in_sandbox(user_id, artifact_id)
        assert updated_doc["name"] == "Updated"
        assert updated_doc["count"] == 2
        assert updated_doc["_id"] == artifact_id

    def test_update_in_sandbox_nonexistent_returns_false(self, sandbox_ops):
        """Test updating nonexistent artifact returns False."""
        result = sandbox_ops.update_in_sandbox(
            "user-123", "nonexistent", {"name": "Updated"}
        )
        assert result is False

    def test_update_in_sandbox_without_user_id_returns_false(self, sandbox_ops):
        """Test updating without user_id returns False."""
        result = sandbox_ops.update_in_sandbox("", "artifact-001", {"name": "Updated"})
        assert result is False

    def test_delete_from_sandbox_removes_artifact(self, sandbox_ops, temp_sandbox_dir):
        """Test deleting artifact from sandbox."""
        user_id = "user-123"
        artifact_id = "artifact-001"
        document = {"_id": artifact_id, "name": "Test"}

        # Insert first
        sandbox_ops.insert_to_sandbox(user_id, document)
        metadata_path = temp_sandbox_dir / user_id / artifact_id / "metadata.json"
        assert metadata_path.exists()

        # Delete
        result = sandbox_ops.delete_from_sandbox(user_id, artifact_id)

        assert result is True
        assert not metadata_path.exists()

    def test_delete_from_sandbox_nonexistent_returns_false(self, sandbox_ops):
        """Test deleting nonexistent artifact returns False."""
        result = sandbox_ops.delete_from_sandbox("user-123", "nonexistent")
        assert result is False

    def test_delete_from_sandbox_without_user_id_returns_false(self, sandbox_ops):
        """Test deleting without user_id returns False."""
        result = sandbox_ops.delete_from_sandbox("", "artifact-001")
        assert result is False

    def test_user_isolation(self, sandbox_ops):
        """Test that artifacts are isolated per user."""
        user1 = "user-001"
        user2 = "user-002"
        artifact_id = "artifact-shared"

        # User 1 creates artifact
        doc1 = {"_id": artifact_id, "owner": user1}
        sandbox_ops.insert_to_sandbox(user1, doc1)

        # User 2 creates artifact with same ID (different user sandbox)
        doc2 = {"_id": artifact_id, "owner": user2}
        sandbox_ops.insert_to_sandbox(user2, doc2)

        # Verify isolation
        result1 = sandbox_ops.find_in_sandbox(user1, artifact_id)
        result2 = sandbox_ops.find_in_sandbox(user2, artifact_id)

        assert result1["owner"] == user1
        assert result2["owner"] == user2
        assert result1 != result2
