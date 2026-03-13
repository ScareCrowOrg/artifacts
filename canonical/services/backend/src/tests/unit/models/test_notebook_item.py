"""
Unit tests for NotebookItem and ExecutionFragment models.

Tests the unified runtime schema with 'kind' discriminator,
execution status tracking, and hierarchical tracing via ExecutionFragment.

Coverage target: 100%
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.core.models import NotebookItem, ExecutionFragment, generate_uuid


class TestExecutionFragment:
    """Test ExecutionFragment model for unified runtime."""
    
    def test_execution_fragment_creation_valid(self):
        """Test creating a valid ExecutionFragment."""
        fragment = ExecutionFragment(
            timestamp="2026-02-07T10:00:00Z",
            step="discovery",
            status="success",
            output={"cells": ["png-generator", "sf3d"], "confidence": 0.85}
        )
        
        assert fragment.timestamp == "2026-02-07T10:00:00Z"
        assert fragment.step == "discovery"
        assert fragment.status == "success"
        assert fragment.output == {"cells": ["png-generator", "sf3d"], "confidence": 0.85}
        assert fragment.duration_ms is None
        assert fragment.input is None
        assert fragment.error is None
        assert fragment.executed_by is None
        assert fragment.parent_fragment_index is None
    
    def test_execution_fragment_with_hierarchical_tracing(self):
        """Test ExecutionFragment with executed_by for hierarchical tracing."""
        fragment = ExecutionFragment(
            timestamp="2026-02-07T10:00:00Z",
            step="planning",
            status="success",
            executed_by="notebook_item_67890",
            parent_fragment_index=0
        )
        
        assert fragment.executed_by == "notebook_item_67890"
        assert fragment.parent_fragment_index == 0
    
    def test_execution_fragment_with_duration(self):
        """Test ExecutionFragment with duration_ms."""
        fragment = ExecutionFragment(
            timestamp="2026-02-07T10:00:00Z",
            duration_ms=5000,
            step="execute",
            status="success"
        )
        
        assert fragment.duration_ms == 5000
    
    def test_execution_fragment_with_error(self):
        """Test ExecutionFragment with error status."""
        fragment = ExecutionFragment(
            timestamp="2026-02-07T10:00:00Z",
            step="execute",
            status="failed",
            error="Cell execution timeout"
        )
        
        assert fragment.status == "failed"
        assert fragment.error == "Cell execution timeout"
    
    def test_execution_fragment_status_values(self):
        """Test all valid status values."""
        statuses = ['running', 'success', 'failed', 'waiting_approval', 'skipped']
        
        for status in statuses:
            fragment = ExecutionFragment(
                timestamp="2026-02-07T10:00:00Z",
                step="test",
                status=status
            )
            assert fragment.status == status
    
    def test_execution_fragment_invalid_status(self):
        """Test ExecutionFragment with invalid status."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionFragment(
                timestamp="2026-02-07T10:00:00Z",
                step="test",
                status="invalid_status"
            )
        assert "status" in str(exc_info.value).lower()
    
    def test_execution_fragment_missing_required_fields(self):
        """Test ExecutionFragment missing required fields."""
        # Missing timestamp
        with pytest.raises(ValidationError) as exc_info:
            ExecutionFragment(
                step="test",
                status="success"
            )
        assert "timestamp" in str(exc_info.value).lower()
        
        # Missing step
        with pytest.raises(ValidationError) as exc_info:
            ExecutionFragment(
                timestamp="2026-02-07T10:00:00Z",
                status="success"
            )
        assert "step" in str(exc_info.value).lower()
        
        # Missing status
        with pytest.raises(ValidationError) as exc_info:
            ExecutionFragment(
                timestamp="2026-02-07T10:00:00Z",
                step="test"
            )
        assert "status" in str(exc_info.value).lower()


class TestNotebookItemBasic:
    """Test basic NotebookItem functionality."""
    
    def test_notebook_item_creation_minimal(self):
        """Test creating NotebookItem with minimal required fields."""
        item = NotebookItem(
            assignee_id="user_123"
        )
        
        assert item.assignee_id == "user_123"
        assert item.id is not None  # UUID auto-generated
        assert item.kind is None
        assert item.notebook_item_type_id is None
        assert item.status is None
        assert item.fragments == []
        assert item.refs == {}
        assert item.initial_data == {}
        assert item.outputs == {}
        assert item.cells is None
        assert item.execution_mode is None
        assert isinstance(item.created_at, datetime)
        assert isinstance(item.updated_at, datetime)
    
    def test_notebook_item_with_all_fields(self):
        """Test creating NotebookItem with all fields."""
        item = NotebookItem(
            id="notebook_item_123",
            assignee_id="user_456",
            kind="cell",
            notebook_item_type_id="png-generator-cell",
            status="success",
            initial_data={"prompt": "A sunset", "width": 1024},
            outputs={"image_url": "https://r2.example.com/image.png"},
            refs={"images": ["https://r2.example.com/image.png"]},
            fragments=["Fragment 1", {"type": "log", "content": "Started"}]
        )
        
        assert item.id == "notebook_item_123"
        assert item.assignee_id == "user_456"
        assert item.kind == "cell"
        assert item.notebook_item_type_id == "png-generator-cell"
        assert item.status == "success"
        assert item.initial_data == {"prompt": "A sunset", "width": 1024}
        assert item.outputs == {"image_url": "https://r2.example.com/image.png"}
        assert item.refs == {"images": ["https://r2.example.com/image.png"]}
        assert len(item.fragments) == 2


class TestNotebookItemKind:
    """Test NotebookItem 'kind' discriminator field."""
    
    def test_notebook_item_kind_cell(self):
        """Test NotebookItem with kind='cell'."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="cell",
            notebook_item_type_id="png-generator-cell"
        )
        
        assert item.kind == "cell"
        # Cells should not have book-specific fields
        assert item.cells is None
        assert item.execution_mode is None
    
    def test_notebook_item_kind_book(self):
        """Test NotebookItem with kind='book'."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            notebook_item_type_id="automation-book",
            cells=["notebook_item_001", "notebook_item_002"],
            execution_mode="dag"
        )
        
        assert item.kind == "book"
        assert item.cells == ["notebook_item_001", "notebook_item_002"]
        assert item.execution_mode == "dag"
    
    def test_notebook_item_kind_invalid(self):
        """Test NotebookItem with invalid kind."""
        with pytest.raises(ValidationError) as exc_info:
            NotebookItem(
                assignee_id="user_123",
                kind="invalid_kind"
            )
        assert "kind" in str(exc_info.value).lower()


class TestNotebookItemStatus:
    """Test NotebookItem status field."""
    
    def test_notebook_item_all_status_values(self):
        """Test all valid status values."""
        statuses = ['idle', 'running', 'AWAITING_REVIEW', 'success', 'failed', 'paused']
        
        for status in statuses:
            item = NotebookItem(
                assignee_id="user_123",
                status=status
            )
            assert item.status == status
    
    def test_notebook_item_invalid_status(self):
        """Test NotebookItem with invalid status."""
        with pytest.raises(ValidationError) as exc_info:
            NotebookItem(
                assignee_id="user_123",
                status="invalid_status"
            )
        assert "status" in str(exc_info.value).lower()


class TestNotebookItemBookSpecific:
    """Test book-specific fields in NotebookItem."""
    
    def test_notebook_item_book_with_cells(self):
        """Test book NotebookItem with cells array."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            cells=["cell_1", "cell_2", "cell_3"]
        )
        
        assert item.cells == ["cell_1", "cell_2", "cell_3"]
    
    def test_notebook_item_book_empty_cells(self):
        """Test book NotebookItem with empty cells array."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            cells=[]
        )
        
        assert item.cells == []
    
    def test_notebook_item_execution_mode_dag(self):
        """Test book with execution_mode='dag'."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            execution_mode="dag"
        )
        
        assert item.execution_mode == "dag"
    
    def test_notebook_item_execution_mode_script(self):
        """Test book with execution_mode='script'."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            execution_mode="script"
        )
        
        assert item.execution_mode == "script"
    
    def test_notebook_item_execution_mode_hybrid(self):
        """Test book with execution_mode='hybrid'."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            execution_mode="hybrid"
        )
        
        assert item.execution_mode == "hybrid"
    
    def test_notebook_item_invalid_execution_mode(self):
        """Test book with invalid execution_mode."""
        with pytest.raises(ValidationError) as exc_info:
            NotebookItem(
                assignee_id="user_123",
                kind="book",
                execution_mode="invalid_mode"
            )
        assert "execution_mode" in str(exc_info.value).lower()


class TestNotebookItemFragments:
    """Test NotebookItem fragments field."""
    
    def test_notebook_item_fragments_strings(self):
        """Test fragments as list of strings."""
        item = NotebookItem(
            assignee_id="user_123",
            fragments=["Fragment 1", "Fragment 2", "Fragment 3"]
        )
        
        assert len(item.fragments) == 3
        assert item.fragments[0] == "Fragment 1"
    
    def test_notebook_item_fragments_dicts(self):
        """Test fragments as list of dictionaries."""
        item = NotebookItem(
            assignee_id="user_123",
            fragments=[
                {"type": "log", "content": "Started"},
                {"type": "output", "content": "Processing"}
            ]
        )
        
        assert len(item.fragments) == 2
        assert item.fragments[0]["type"] == "log"
    
    def test_notebook_item_fragments_mixed(self):
        """Test fragments as mixed list of strings and dicts."""
        item = NotebookItem(
            assignee_id="user_123",
            fragments=[
                "Simple fragment",
                {"type": "log", "content": "Structured fragment"}
            ]
        )
        
        assert len(item.fragments) == 2
        assert isinstance(item.fragments[0], str)
        assert isinstance(item.fragments[1], dict)


class TestNotebookItemOutputs:
    """Test NotebookItem outputs field."""
    
    def test_notebook_item_outputs_empty(self):
        """Test outputs as empty dict."""
        item = NotebookItem(
            assignee_id="user_123"
        )
        
        assert item.outputs == {}
    
    def test_notebook_item_outputs_cell(self):
        """Test outputs from a cell."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="cell",
            outputs={
                "image_url": "https://r2.example.com/image.png",
                "metadata": {"width": 1024, "height": 768}
            }
        )
        
        assert "image_url" in item.outputs
        assert "metadata" in item.outputs
    
    def test_notebook_item_outputs_book(self):
        """Test outputs from a book (aggregated)."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            outputs={
                "discovery": {
                    "cells": ["png-generator", "sf3d"],
                    "confidence": 0.85
                },
                "plan": {
                    "dag": {"nodes": ["sf3d"], "edges": []}
                }
            }
        )
        
        assert "discovery" in item.outputs
        assert "plan" in item.outputs


class TestNotebookItemRefs:
    """Test NotebookItem refs field."""
    
    def test_notebook_item_refs_empty(self):
        """Test refs as empty dict."""
        item = NotebookItem(
            assignee_id="user_123"
        )
        
        assert item.refs == {}
    
    def test_notebook_item_refs_with_files(self):
        """Test refs with multiple file types."""
        item = NotebookItem(
            assignee_id="user_123",
            refs={
                "images": ["https://r2.example.com/image1.png", "https://r2.example.com/image2.png"],
                "models": ["https://r2.example.com/model.glb"],
                "docs": ["https://r2.example.com/doc.pdf"]
            }
        )
        
        assert len(item.refs["images"]) == 2
        assert len(item.refs["models"]) == 1
        assert len(item.refs["docs"]) == 1


class TestNotebookItemInitialData:
    """Test NotebookItem initial_data field."""
    
    def test_notebook_item_initial_data_empty(self):
        """Test initial_data as empty dict."""
        item = NotebookItem(
            assignee_id="user_123"
        )
        
        assert item.initial_data == {}
    
    def test_notebook_item_initial_data_cell(self):
        """Test initial_data for a cell."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="cell",
            initial_data={
                "prompt": "A beautiful sunset over mountains",
                "width": 1024,
                "height": 768,
                "steps": 50
            }
        )
        
        assert item.initial_data["prompt"] == "A beautiful sunset over mountains"
        assert item.initial_data["width"] == 1024
    
    def test_notebook_item_initial_data_book(self):
        """Test initial_data for a book."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            initial_data={
                "intent": "Generate a 3D model from this image",
                "image_url": "https://example.com/input.png"
            }
        )
        
        assert item.initial_data["intent"] == "Generate a 3D model from this image"


class TestNotebookItemSerialization:
    """Test NotebookItem serialization."""
    
    def test_notebook_item_to_dict(self):
        """Test serializing NotebookItem to dict."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="cell",
            status="success"
        )
        
        data = item.model_dump()
        assert data["assignee_id"] == "user_123"
        assert data["kind"] == "cell"
        assert data["status"] == "success"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_notebook_item_to_json(self):
        """Test serializing NotebookItem to JSON."""
        item = NotebookItem(
            assignee_id="user_123",
            kind="book",
            cells=["cell_1", "cell_2"],
            execution_mode="dag"
        )
        
        json_str = item.model_dump_json()
        assert "user_123" in json_str
        assert "book" in json_str
        assert "dag" in json_str


class TestNotebookItemBackwardCompatibility:
    """Test backward compatibility with existing code."""
    
    def test_notebook_item_without_kind(self):
        """Test NotebookItem without 'kind' field (backward compatibility)."""
        item = NotebookItem(
            assignee_id="user_123"
        )
        
        assert item.kind is None
        assert item.assignee_id == "user_123"
    
    def test_notebook_item_without_status(self):
        """Test NotebookItem without 'status' field."""
        item = NotebookItem(
            assignee_id="user_123"
        )
        
        assert item.status is None
    
    def test_notebook_item_with_data_alias(self):
        """Test NotebookItem using 'data' alias for initial_data."""
        # The alias is configured but by_alias=False by default
        item = NotebookItem(
            assignee_id="user_123",
            initial_data={"key": "value"}
        )
        
        assert item.initial_data == {"key": "value"}
