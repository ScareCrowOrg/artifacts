"""
Unit tests for Content and ContentType models.

Tests model validation, schema enforcement, and the zero-raw-in-db principle.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.content_types import (
    ContentType,
    Content,
    StoragePolicy,
    RenderHints,
    CreateContentRequest
)


class TestContentType:
    """Tests for ContentType model."""
    
    def test_create_basic_content_type(self):
        """Test creating a basic ContentType."""
        ct = ContentType(
            id="test-type",
            name="Test Type",
            mime_type="text/plain"
        )
        
        assert ct.id == "test-type"
        assert ct.name == "Test Type"
        assert ct.mime_type == "text/plain"
        assert ct.storage_policy == StoragePolicy.LOCAL
        assert isinstance(ct.created_at, datetime)
    
    def test_content_type_with_fragments(self):
        """Test ContentType with expected_fragments schema."""
        ct = ContentType(
            id="image-test",
            name="Image Test",
            mime_type="image/png",
            expected_fragments={
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "format": {"type": "string", "optional": True}
            }
        )
        
        assert "width" in ct.expected_fragments
        assert "height" in ct.expected_fragments
        assert ct.expected_fragments["width"]["type"] == "integer"
    
    def test_content_type_with_render_hints(self):
        """Test ContentType with rendering hints."""
        hints = RenderHints(
            component="ImageViewer",
            viewport_params={"fit": "contain"},
            interaction_mode="view-only"
        )
        
        ct = ContentType(
            id="test-render",
            name="Test Render",
            mime_type="image/png",
            render_hints=hints
        )
        
        assert ct.render_hints.component == "ImageViewer"
        assert ct.render_hints.interaction_mode == "view-only"
    
    def test_invalid_mime_type(self):
        """Test that invalid MIME types are rejected."""
        with pytest.raises(ValidationError, match="Invalid MIME type format"):
            ContentType(
                id="bad-mime",
                name="Bad MIME",
                mime_type="invalid"  # Missing '/'
            )
    
    def test_storage_policies(self):
        """Test different storage policies."""
        for policy in [StoragePolicy.LOCAL, StoragePolicy.CLOUD, StoragePolicy.REPO]:
            ct = ContentType(
                id="test-storage",
                name="Test Storage",
                mime_type="text/plain",
                storage_policy=policy
            )
            assert ct.storage_policy == policy


class TestContent:
    """Tests for Content model."""
    
    def test_create_basic_content(self):
        """Test creating basic content."""
        content = Content(
            content_type_id="image-png",
            assignee_id="user-123",
            data_ref="file:///data/content/test.png",
            fragments={"width": 100, "height": 100}
        )
        
        assert content.content_type_id == "image-png"
        assert content.assignee_id == "user-123"
        assert content.data_ref == "file:///data/content/test.png"
        assert content.version == 1
        assert content.is_latest is True
        assert isinstance(content.id, str)
    
    def test_content_versioning(self):
        """Test content version tracking."""
        content_v1 = Content(
            content_type_id="test-type",
            assignee_id="user-123",
            data_ref="file:///test.dat",
            version=1,
            is_latest=False
        )
        
        content_v2 = Content(
            content_type_id="test-type",
            assignee_id="user-123",
            data_ref="file:///test.dat",
            version=2,
            is_latest=True,
            previous_version_id=content_v1.id
        )
        
        assert content_v2.version == 2
        assert content_v2.is_latest is True
        assert content_v2.previous_version_id == content_v1.id
    
    def test_content_with_lineage(self):
        """Test content with origin_cell_id tracking."""
        content = Content(
            content_type_id="test-type",
            assignee_id="user-123",
            data_ref="file:///test.dat",
            origin_cell_id="cell-abc-123"
        )
        
        assert content.origin_cell_id == "cell-abc-123"
    
    def test_prevent_large_string_in_fragments(self):
        """Test that large strings in fragments are rejected."""
        large_string = "A" * 20000  # 20K characters
        
        with pytest.raises(ValidationError, match="suspiciously large string"):
            Content(
                content_type_id="test-type",
                assignee_id="user-123",
                data_ref="file:///test.dat",
                fragments={"data": large_string}
            )
    
    def test_prevent_base64_in_fragments(self):
        """Test that base64 data in fragments is rejected."""
        # Simulate base64-encoded image
        base64_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        
        with pytest.raises(ValidationError, match="base64-encoded data"):
            Content(
                content_type_id="test-type",
                assignee_id="user-123",
                data_ref="file:///test.dat",
                fragments={"image": base64_data}
            )
    
    def test_content_with_file_metadata(self):
        """Test content with file metadata."""
        content = Content(
            content_type_id="image-png",
            assignee_id="user-123",
            data_ref="file:///test.png",
            filename="test.png",
            size_bytes=1024,
            checksum="abc123def456",
            fragments={"width": 100, "height": 100}
        )
        
        assert content.filename == "test.png"
        assert content.size_bytes == 1024
        assert content.checksum == "abc123def456"
    
    def test_content_with_tags(self):
        """Test content with tags."""
        content = Content(
            content_type_id="test-type",
            assignee_id="user-123",
            data_ref="file:///test.dat",
            tags=["generated", "ai", "png"]
        )
        
        assert "generated" in content.tags
        assert "ai" in content.tags
        assert len(content.tags) == 3


class TestCreateContentRequest:
    """Tests for CreateContentRequest model."""
    
    def test_create_content_request(self):
        """Test creating a content request."""
        request = CreateContentRequest(
            content_type_id="image-png",
            assignee_id="user-123",
            data_ref="file:///test.png",
            fragments={"width": 100, "height": 100},
            filename="test.png"
        )
        
        assert request.content_type_id == "image-png"
        assert request.data_ref == "file:///test.png"
        assert request.fragments["width"] == 100
    
    def test_create_content_request_with_lineage(self):
        """Test request with cell lineage."""
        request = CreateContentRequest(
            content_type_id="test-type",
            assignee_id="user-123",
            data_ref="file:///test.dat",
            origin_cell_id="cell-123"
        )
        
        assert request.origin_cell_id == "cell-123"
