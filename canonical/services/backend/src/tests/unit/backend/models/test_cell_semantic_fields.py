"""
Unit tests for Cell semantic fields (title and content).

Tests the new title and content fields added to improve user presentation
and semantic understanding of cells.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models import Cell, CreateCellRequest, UpdateCellRequest, CellStatus


class TestCellTitleAndContent:
    """Test suite for Cell title and content fields."""
    
    def test_create_celula_with_title_and_content(self):
        """Test creating a cell with title and content."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="My Test Cell",
            content="This is the main content of the cell"
        )
        
        assert cell.title == "My Test Cell"
        assert cell.content == "This is the main content of the cell"
        assert cell.assignee_id == "user-123"
        assert cell.notebook_item_type_id == "type-456"
        assert cell.status == CellStatus.PENDING
    
    def test_create_celula_without_title_and_content(self):
        """Test creating a cell without title and content (backward compatibility)."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456"
        )
        
        assert cell.title is None
        assert cell.content is None
        assert cell.assignee_id == "user-123"
        assert cell.notebook_item_type_id == "type-456"
    
    def test_create_celula_with_only_title(self):
        """Test creating a cell with only title."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Title Only Cell"
        )
        
        assert cell.title == "Title Only Cell"
        assert cell.content is None
    
    def test_create_celula_with_only_content(self):
        """Test creating a cell with only content."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            content="Content only, no title"
        )
        
        assert cell.title is None
        assert cell.content == "Content only, no title"
    
    def test_cell_title_and_content_serialization(self):
        """Test that title and content are properly serialized."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Serialization Test",
            content="Testing JSON serialization"
        )
        
        data = cell.model_dump()
        
        assert data["title"] == "Serialization Test"
        assert data["content"] == "Testing JSON serialization"
        assert "assignee_id" in data
        assert "notebook_item_type_id" in data
    
    def test_cell_title_and_content_from_dict(self):
        """Test creating Cell from dictionary with title and content."""
        data = {
            "id": "cell-789",
            "assignee_id": "user-123",
            "notebook_item_type_id": "type-456",
            "title": "From Dict Cell",
            "content": "Created from dictionary",
            "status": "pending"
        }
        
        cell = Cell(**data)
        
        assert cell.id == "cell-789"
        assert cell.title == "From Dict Cell"
        assert cell.content == "Created from dictionary"
    
    def test_cell_migration_from_initial_data_title(self):
        """Test automatic migration of title from initial_data."""
        data = {
            "assignee_id": "user-123",
            "notebook_item_type_id": "type-456",
            "initial_data": {
                "title": "Title from initial_data",
                "other_field": "value"
            }
        }
        
        cell = Cell(**data)
        
        # Should migrate title from initial_data
        assert cell.title == "Title from initial_data"
        # initial_data should still contain the original data
        assert cell.initial_data["title"] == "Title from initial_data"
        assert cell.initial_data["other_field"] == "value"
    
    def test_cell_migration_from_initial_data_content(self):
        """Test automatic migration of content from initial_data."""
        data = {
            "assignee_id": "user-123",
            "notebook_item_type_id": "type-456",
            "initial_data": {
                "content": "Content from initial_data",
                "other_field": "value"
            }
        }
        
        cell = Cell(**data)
        
        # Should migrate content from initial_data
        assert cell.content == "Content from initial_data"
        # initial_data should still contain the original data
        assert cell.initial_data["content"] == "Content from initial_data"
    
    def test_cell_migration_both_title_and_content(self):
        """Test migration of both title and content from initial_data."""
        data = {
            "assignee_id": "user-123",
            "notebook_item_type_id": "type-456",
            "initial_data": {
                "title": "Migrated Title",
                "content": "Migrated Content",
                "extra": "data"
            }
        }
        
        cell = Cell(**data)
        
        assert cell.title == "Migrated Title"
        assert cell.content == "Migrated Content"
        assert cell.initial_data["extra"] == "data"
    
    def test_cell_top_level_overrides_initial_data(self):
        """Test that top-level title/content take precedence over initial_data."""
        data = {
            "assignee_id": "user-123",
            "notebook_item_type_id": "type-456",
            "title": "Top Level Title",
            "content": "Top Level Content",
            "initial_data": {
                "title": "Initial Data Title",
                "content": "Initial Data Content"
            }
        }
        
        cell = Cell(**data)
        
        # Top-level should win
        assert cell.title == "Top Level Title"
        assert cell.content == "Top Level Content"
    
    def test_cell_with_markdown_content(self):
        """Test cell with markdown formatted content."""
        markdown_content = """
# Main Title

This is a **bold** statement with *italic* text.

- Item 1
- Item 2

```python
print("Hello, World!")
```
"""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Markdown Cell",
            content=markdown_content
        )
        
        assert cell.title == "Markdown Cell"
        assert "# Main Title" in cell.content
        assert "**bold**" in cell.content
    
    def test_cell_with_long_content(self):
        """Test cell with long content (multi-paragraph)."""
        long_content = "Lorem ipsum dolor sit amet. " * 100
        
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Long Content Cell",
            content=long_content
        )
        
        assert cell.title == "Long Content Cell"
        assert len(cell.content) > 1000
        assert "Lorem ipsum" in cell.content


class TestCreateCellRequestSemanticFields:
    """Test suite for CreateCellRequest with semantic fields."""
    
    def test_create_cell_request_with_title_and_content(self):
        """Test creating a CreateCellRequest with title and content."""
        request = CreateCellRequest(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="New Cell Title",
            content="New cell content"
        )
        
        assert request.title == "New Cell Title"
        assert request.content == "New cell content"
        assert request.assignee_id == "user-123"
    
    def test_create_cell_request_without_title_and_content(self):
        """Test creating a CreateCellRequest without title and content."""
        request = CreateCellRequest(
            assignee_id="user-123",
            notebook_item_type_id="type-456"
        )
        
        assert request.title is None
        assert request.content is None
    
    def test_create_cell_request_with_initial_data_and_title(self):
        """Test creating request with both initial_data and title/content."""
        request = CreateCellRequest(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Request Title",
            content="Request Content",
            initial_data={"key": "value"}
        )
        
        assert request.title == "Request Title"
        assert request.content == "Request Content"
        assert request.initial_data["key"] == "value"
    
    def test_create_cell_request_serialization(self):
        """Test request serialization includes title and content."""
        request = CreateCellRequest(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Serialization Test",
            content="Test content"
        )
        
        data = request.model_dump()
        
        assert data["title"] == "Serialization Test"
        assert data["content"] == "Test content"


class TestUpdateCellRequestSemanticFields:
    """Test suite for UpdateCellRequest with semantic fields."""
    
    def test_update_cell_request_with_title(self):
        """Test updating only title."""
        request = UpdateCellRequest(
            title="Updated Title"
        )
        
        assert request.title == "Updated Title"
        assert request.content is None
        assert request.status is None
    
    def test_update_cell_request_with_content(self):
        """Test updating only content."""
        request = UpdateCellRequest(
            content="Updated content"
        )
        
        assert request.title is None
        assert request.content == "Updated content"
        assert request.status is None
    
    def test_update_cell_request_with_both(self):
        """Test updating both title and content."""
        request = UpdateCellRequest(
            title="New Title",
            content="New Content"
        )
        
        assert request.title == "New Title"
        assert request.content == "New Content"
    
    def test_update_cell_request_with_all_fields(self):
        """Test updating title, content, status, and initial_data."""
        request = UpdateCellRequest(
            title="Complete Update",
            content="Complete content",
            status=CellStatus.COMPLETED,
            initial_data={"updated": True}
        )
        
        assert request.title == "Complete Update"
        assert request.content == "Complete content"
        assert request.status == CellStatus.COMPLETED
        assert request.initial_data["updated"] is True
    
    def test_update_cell_request_empty(self):
        """Test creating an empty update request (all fields optional)."""
        request = UpdateCellRequest()
        
        assert request.title is None
        assert request.content is None
        assert request.status is None
        assert request.initial_data is None
    
    def test_update_cell_request_clear_title(self):
        """Test clearing title by setting to empty string."""
        request = UpdateCellRequest(
            title=""
        )
        
        assert request.title == ""
    
    def test_update_cell_request_clear_content(self):
        """Test clearing content by setting to empty string."""
        request = UpdateCellRequest(
            content=""
        )
        
        assert request.content == ""


class TestCellBackwardCompatibility:
    """Test backward compatibility with existing cells."""
    
    def test_load_legacy_cell_without_title_content(self):
        """Test loading a legacy cell that doesn't have title/content fields."""
        legacy_data = {
            "id": "legacy-cell",
            "assignee_id": "user-123",
            "notebook_item_type_id": "type-456",
            "status": "pending",
            "version": "1.0.0",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Should not raise an error
        cell = Cell(**legacy_data)
        
        assert cell.id == "legacy-cell"
        assert cell.title is None
        assert cell.content is None
    
    def test_backward_compatibility_properties_still_work(self):
        """Test that current field names work correctly with new semantic fields."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Compatibility Test",
            content="Testing properties"
        )
        
        # Current field names should work
        assert cell.assignee_id == "user-123"
        assert cell.initial_data == {}  # No data in initial_data since we set title/content directly
        assert isinstance(cell.created_at, datetime)
        assert isinstance(cell.updated_at, datetime)
