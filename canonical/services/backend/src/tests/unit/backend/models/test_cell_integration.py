"""
Integration tests for Cell semantic fields with routers.

Simple tests to verify that title and content fields work correctly
through the API endpoints without heavy dependencies.
"""

import pytest
from datetime import datetime

from app.models import (
    Cell, 
    CreateCellRequest, 
    UpdateCellRequest,
    CellStatus
)


class TestCellSemanticsIntegration:
    """Integration tests for semantic fields in Cell creation and update."""
    
    def test_create_cell_request_to_cell_with_semantics(self):
        """Test creating a Cell from request with title and content."""
        # Simulate request
        request = CreateCellRequest(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Integration Test Cell",
            content="Content for integration test",
            initial_data={"extra": "data"}
        )
        
        # Simulate creating Cell as router would
        cell = Cell(
            assignee_id=request.assignee_id,
            notebook_item_type_id=request.notebook_item_type_id,
            title=request.title,
            content=request.content,
            initial_data=request.initial_data or {}
        )
        
        # Verify
        assert cell.title == "Integration Test Cell"
        assert cell.content == "Content for integration test"
        assert cell.initial_data["extra"] == "data"
        assert cell.assignee_id == "user-123"
    
    def test_update_cell_updates_semantics(self):
        """Test updating a Cell with new title and content."""
        # Create initial cell
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Original Title",
            content="Original content"
        )
        
        # Simulate update request
        update_request = UpdateCellRequest(
            title="Updated Title",
            content="Updated content"
        )
        
        # Simulate router update logic
        updates = {}
        if update_request.title is not None:
            updates["title"] = update_request.title
        if update_request.content is not None:
            updates["content"] = update_request.content
        
        # Apply updates (simulating what the database would do)
        for key, value in updates.items():
            setattr(cell, key, value)
        
        # Verify
        assert cell.title == "Updated Title"
        assert cell.content == "Updated content"
    
    def test_cell_serialization_includes_semantics(self):
        """Test that serialized Cell includes title and content."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Serialization Cell",
            content="For testing JSON output"
        )
        
        # Serialize to dict (as router would return)
        data = cell.model_dump()
        
        # Verify all fields present
        assert "title" in data
        assert "content" in data
        assert data["title"] == "Serialization Cell"
        assert data["content"] == "For testing JSON output"
        assert "id" in data
        assert "assignee_id" in data
        assert "notebook_item_type_id" in data
    
    def test_cell_without_semantics_still_valid(self):
        """Test that Cell without title/content is still valid (backward compat)."""
        # Create cell without semantic fields
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456"
        )
        
        # Serialize
        data = cell.model_dump()
        
        # Should have null values
        assert data["title"] is None
        assert data["content"] is None
        # But should still be valid
        assert data["assignee_id"] == "user-123"
        assert data["status"] == CellStatus.PENDING.value
    
    def test_partial_update_only_title(self):
        """Test updating only title without affecting content."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Original Title",
            content="Original Content"
        )
        
        # Update only title
        update_request = UpdateCellRequest(title="New Title Only")
        
        # Apply update
        if update_request.title is not None:
            cell.title = update_request.title
        
        # Verify
        assert cell.title == "New Title Only"
        assert cell.content == "Original Content"  # Should not change
    
    def test_partial_update_only_content(self):
        """Test updating only content without affecting title."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Original Title",
            content="Original Content"
        )
        
        # Update only content
        update_request = UpdateCellRequest(content="New Content Only")
        
        # Apply update
        if update_request.content is not None:
            cell.content = update_request.content
        
        # Verify
        assert cell.title == "Original Title"  # Should not change
        assert cell.content == "New Content Only"
    
    def test_migration_from_initial_data_to_fields(self):
        """Test that cells with title/content in initial_data are migrated."""
        # Simulate old cell data from database
        old_cell_data = {
            "assignee_id": "user-123",
            "notebook_item_type_id": "type-456",
            "initial_data": {
                "title": "Old Title in Data",
                "content": "Old Content in Data",
                "other_stuff": "keep this"
            }
        }
        
        # Load as Cell (triggers migration)
        cell = Cell(**old_cell_data)
        
        # Verify migration happened
        assert cell.title == "Old Title in Data"
        assert cell.content == "Old Content in Data"
        # initial_data should still have it
        assert cell.initial_data["title"] == "Old Title in Data"
        assert cell.initial_data["other_stuff"] == "keep this"
    
    def test_request_with_empty_strings(self):
        """Test that empty strings are handled correctly."""
        request = CreateCellRequest(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="",  # Empty title
            content=""  # Empty content
        )
        
        cell = Cell(
            assignee_id=request.assignee_id,
            notebook_item_type_id=request.notebook_item_type_id,
            title=request.title,
            content=request.content
        )
        
        # Empty strings should be preserved (not None)
        assert cell.title == ""
        assert cell.content == ""
        assert cell.title is not None
        assert cell.content is not None
    
    def test_complex_workflow_create_execute_update(self):
        """Test complex workflow: create with semantics, execute, then update."""
        # 1. Create
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="type-456",
            title="Workflow Test",
            content="Initial workflow content"
        )
        assert cell.status == CellStatus.PENDING
        
        # 2. Simulate execution
        cell.status = CellStatus.RUNNING
        assert cell.title == "Workflow Test"  # Title preserved during execution
        
        # 3. Complete execution
        cell.status = CellStatus.COMPLETED
        
        # 4. Update with results
        cell.content = "Updated with execution results"
        
        # Verify final state
        assert cell.title == "Workflow Test"
        assert cell.content == "Updated with execution results"
        assert cell.status == CellStatus.COMPLETED
