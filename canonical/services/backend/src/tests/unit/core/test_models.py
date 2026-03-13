"""
Unit tests for core.models module.

Tests all core Pydantic models including:
- Fragment model
- NotebookItem model
- PipelineItem model
- UUID generation utility
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from app.core.models import (
    Fragment,
    NotebookItem,
    PipelineItem,
    generate_uuid,
)


class TestGenerateUUID:
    """Tests for the generate_uuid utility function."""
    
    def test_generates_valid_uuid_string(self):
        """Test that generate_uuid returns a valid UUID string."""
        uuid_str = generate_uuid()
        
        assert isinstance(uuid_str, str)
        # Should be able to parse as UUID
        UUID(uuid_str)
    
    def test_generates_unique_uuids(self):
        """Test that generate_uuid generates unique UUIDs."""
        uuids = [generate_uuid() for _ in range(100)]
        
        # All UUIDs should be unique
        assert len(set(uuids)) == 100
    
    def test_uuid_format(self):
        """Test that UUID follows standard format."""
        uuid_str = generate_uuid()
        
        # Standard UUID format: 8-4-4-4-12 hex characters
        parts = uuid_str.split('-')
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12


class TestFragment:
    """Tests for the Fragment model."""
    
    def test_fragment_with_minimal_fields(self):
        """Test creating a fragment with only required fields."""
        fragment = Fragment(
            type="narrative",
            content="Test content"
        )
        
        assert fragment.type == "narrative"
        assert fragment.content == "Test content"
        assert fragment.result is None
        assert isinstance(fragment.id, str)
        assert isinstance(fragment.timestamp, datetime)
        assert fragment.metadata == {}
    
    def test_fragment_with_all_fields(self):
        """Test creating a fragment with all fields."""
        timestamp = datetime.utcnow()
        metadata = {"source": "agent", "severity": "high"}
        
        fragment = Fragment(
            id="custom-id",
            type="error",
            content="Error occurred",
            result={"status": "failed"},
            timestamp=timestamp,
            metadata=metadata
        )
        
        assert fragment.id == "custom-id"
        assert fragment.type == "error"
        assert fragment.content == "Error occurred"
        assert fragment.result == {"status": "failed"}
        assert fragment.timestamp == timestamp
        assert fragment.metadata == metadata
    
    def test_fragment_content_can_be_any_type(self):
        """Test that fragment content accepts any type."""
        # String content
        f1 = Fragment(type="text", content="string content")
        assert f1.content == "string content"
        
        # Dict content
        f2 = Fragment(type="json", content={"key": "value"})
        assert f2.content == {"key": "value"}
        
        # List content
        f3 = Fragment(type="array", content=[1, 2, 3])
        assert f3.content == [1, 2, 3]
        
        # Number content
        f4 = Fragment(type="number", content=42)
        assert f4.content == 42
    
    def test_fragment_result_optional(self):
        """Test that result field is optional."""
        fragment = Fragment(type="log", content="Log entry")
        assert fragment.result is None
    
    def test_fragment_auto_generates_id(self):
        """Test that fragment auto-generates ID if not provided."""
        fragment = Fragment(type="event", content="Event data")
        
        assert fragment.id is not None
        # Should be a valid UUID
        UUID(fragment.id)
    
    def test_fragment_auto_generates_timestamp(self):
        """Test that fragment auto-generates timestamp if not provided."""
        before = datetime.utcnow()
        fragment = Fragment(type="log", content="Log message")
        after = datetime.utcnow()
        
        assert before <= fragment.timestamp <= after
    
    def test_fragment_custom_types(self):
        """Test fragment with custom type strings."""
        types = ["narrative", "memory", "log", "error", "event", "output", 
                 "debug", "execution", "custom_type", "another-custom"]
        
        for fragment_type in types:
            fragment = Fragment(type=fragment_type, content="test")
            assert fragment.type == fragment_type
    
    def test_fragment_serialization(self):
        """Test that fragment can be serialized to dict."""
        fragment = Fragment(
            type="test",
            content="test content",
            metadata={"key": "value"}
        )
        
        data = fragment.model_dump()
        
        assert data["type"] == "test"
        assert data["content"] == "test content"
        assert data["metadata"] == {"key": "value"}
        assert "id" in data
        assert "timestamp" in data


class TestNotebookItem:
    """Tests for the NotebookItem model."""
    
    def test_notebook_item_with_minimal_fields(self):
        """Test creating notebook item with only required fields."""
        item = NotebookItem(assignee_id="user-123")
        
        assert isinstance(item.id, str)
        assert item.assignee_id == "user-123"
        assert item.fragments == []
        assert item.refs == {}
        assert item.initial_data == {}
        assert isinstance(item.created_at, datetime)
        assert isinstance(item.updated_at, datetime)
    
    def test_notebook_item_with_all_fields(self):
        """Test creating notebook item with all fields."""
        fragments = ["fragment 1", {"type": "structured", "data": "value"}]
        refs = {"docs": ["doc1.md"], "python": ["script.py"]}
        initial_data = {"key": "value", "number": 42}
        
        item = NotebookItem(
            id="custom-id",
            assignee_id="user-456",
            fragments=fragments,
            refs=refs,
            initial_data=initial_data
        )
        
        assert item.id == "custom-id"
        assert item.assignee_id == "user-456"
        assert item.fragments == fragments
        assert item.refs == refs
        assert item.initial_data == initial_data
    
    def test_notebook_item_auto_generates_id(self):
        """Test that notebook item auto-generates ID."""
        item = NotebookItem(assignee_id="user-789")
        
        assert item.id is not None
        UUID(item.id)
    
    def test_notebook_item_fragments_supports_mixed_types(self):
        """Test that fragments can contain strings and dicts."""
        fragments = [
            "Simple string fragment",
            {"type": "structured", "content": "data"},
            "Another string",
            {"result": "success"}
        ]
        
        item = NotebookItem(
            assignee_id="user-123",
            fragments=fragments
        )
        
        assert len(item.fragments) == 4
        assert item.fragments[0] == "Simple string fragment"
        assert item.fragments[1]["type"] == "structured"
    
    def test_notebook_item_refs_organization(self):
        """Test that refs can organize files by type."""
        refs = {
            "docs": ["readme.md", "guide.md"],
            "python": ["main.py", "utils.py"],
            "js": ["app.js"],
            "yaml": ["config.yaml"],
            "attachments": ["image.png", "data.csv"]
        }
        
        item = NotebookItem(assignee_id="user-123", refs=refs)
        
        assert len(item.refs["docs"]) == 2
        assert len(item.refs["python"]) == 2
        assert len(item.refs["js"]) == 1
        assert "main.py" in item.refs["python"]
    
    def test_notebook_item_initial_data_alias(self):
        """Test that initial_data can be accessed via 'data' alias."""
        item = NotebookItem(
            assignee_id="user-123",
            data={"test": "value"}  # Using alias
        )
        
        # Should be accessible via initial_data
        assert item.initial_data == {"test": "value"}
    
    def test_notebook_item_timestamps_auto_generated(self):
        """Test that timestamps are auto-generated."""
        before = datetime.utcnow()
        item = NotebookItem(assignee_id="user-123")
        after = datetime.utcnow()
        
        assert before <= item.created_at <= after
        assert before <= item.updated_at <= after
    
    def test_notebook_item_serialization(self):
        """Test that notebook item can be serialized."""
        item = NotebookItem(
            assignee_id="user-123",
            fragments=["test"],
            refs={"docs": ["file.md"]},
            initial_data={"key": "value"}
        )
        
        data = item.model_dump()
        
        assert data["assignee_id"] == "user-123"
        assert data["fragments"] == ["test"]
        assert data["refs"] == {"docs": ["file.md"]}
        # Should use field name 'initial_data' not alias 'data'
        assert "initial_data" in data


class TestPipelineItem:
    """Tests for the PipelineItem model."""
    
    def test_pipeline_item_with_required_fields(self):
        """Test creating pipeline item with required fields."""
        notebook_item = NotebookItem(assignee_id="user-123")
        
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-456",
            cell_type_id="chat-ia",
            assignee_id="user-123"
        )
        
        assert isinstance(pipeline.id, str)
        assert pipeline.notebook_item_id == notebook_item.id
        assert pipeline.notebook_item_data == notebook_item
        assert pipeline.cell_id == "cell-456"
        assert pipeline.cell_type_id == "chat-ia"
        assert pipeline.assignee_id == "user-123"
        assert pipeline.fragments == []
        assert pipeline.status == "pending"
        assert pipeline.data == {}
        assert pipeline.error is None
        assert pipeline.agent_data == {}
    
    def test_pipeline_item_with_all_fields(self):
        """Test creating pipeline item with all fields."""
        notebook_item = NotebookItem(assignee_id="agent-789")
        fragments = [{"type": "execution", "step": "process"}]
        data = {"input": "test", "output": "result"}
        agent_data = {"agent_type": "custom", "version": "1.0"}
        
        pipeline = PipelineItem(
            id="pipeline-123",
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-999",
            cell_type_id="file-editor",
            assignee_id="agent-789",
            fragments=fragments,
            status="completed",
            data=data,
            error=None,
            agent_data=agent_data
        )
        
        assert pipeline.id == "pipeline-123"
        assert pipeline.fragments == fragments
        assert pipeline.status == "completed"
        assert pipeline.data == data
        assert pipeline.agent_data == agent_data
    
    def test_pipeline_item_status_values(self):
        """Test that status accepts valid literal values."""
        notebook_item = NotebookItem(assignee_id="user-123")
        
        statuses = ["pending", "running", "completed", "error"]
        
        for status in statuses:
            pipeline = PipelineItem(
                notebook_item_id=notebook_item.id,
                notebook_item_data=notebook_item,
                cell_id="cell-1",
                cell_type_id="type-1",
                assignee_id="user-123",
                status=status
            )
            assert pipeline.status == status
    
    def test_pipeline_item_with_error(self):
        """Test pipeline item with error status and message."""
        notebook_item = NotebookItem(assignee_id="user-123")
        
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123",
            status="error",
            error="Connection timeout"
        )
        
        assert pipeline.status == "error"
        assert pipeline.error == "Connection timeout"
    
    def test_pipeline_item_execution_fragments_separate(self):
        """Test that pipeline fragments are separate from notebook item fragments."""
        notebook_item = NotebookItem(
            assignee_id="user-123",
            fragments=["notebook fragment 1", "notebook fragment 2"]
        )
        
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id=notebook_item.id,
            cell_type_id="type-1",
            assignee_id="user-123",
            fragments=["execution fragment 1", "execution fragment 2"]
        )
        
        # Pipeline fragments should be different from notebook item fragments
        assert len(pipeline.fragments) == 2
        assert len(pipeline.notebook_item_data.fragments) == 2
        assert pipeline.fragments != pipeline.notebook_item_data.fragments
    
    def test_pipeline_item_data_payload(self):
        """Test pipeline item with complex data payload."""
        notebook_item = NotebookItem(assignee_id="user-123")
        
        data_payload = {
            "input": {
                "text": "Process this",
                "options": {"mode": "fast"}
            },
            "output": {
                "result": "Processed",
                "metadata": {"duration": 1.5}
            }
        }
        
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="processor",
            assignee_id="user-123",
            data=data_payload
        )
        
        assert pipeline.data["input"]["text"] == "Process this"
        assert pipeline.data["output"]["result"] == "Processed"
    
    def test_pipeline_item_agent_context(self):
        """Test pipeline item with agent context data."""
        notebook_item = NotebookItem(assignee_id="agent-456")
        
        agent_data = {
            "agent_id": "agent-456",
            "agent_type": "llm",
            "model": "gpt-4",
            "capabilities": ["code", "chat"]
        }
        
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="chat",
            assignee_id="agent-456",
            agent_data=agent_data
        )
        
        assert pipeline.agent_data["agent_id"] == "agent-456"
        assert pipeline.agent_data["model"] == "gpt-4"
        assert "code" in pipeline.agent_data["capabilities"]
    
    def test_pipeline_item_serialization(self):
        """Test that pipeline item can be serialized."""
        notebook_item = NotebookItem(assignee_id="user-123")
        
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123",
            status="completed",
            data={"result": "success"}
        )
        
        data = pipeline.model_dump()
        
        assert data["notebook_item_id"] == notebook_item.id
        assert data["status"] == "completed"
        assert data["data"] == {"result": "success"}
        assert "notebook_item_data" in data


class TestPipelineItemMethods:
    """Tests for PipelineItem methods."""
    
    def test_add_fragment_creates_and_adds_fragment(self):
        """Test add_fragment method creates and adds fragment."""
        notebook_item = NotebookItem(assignee_id="user-123")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123"
        )
        
        before_update = pipeline.updated_at
        fragment = pipeline.add_fragment(
            type="log",
            content="Test log message",
            metadata={"level": "info"}
        )
        
        assert isinstance(fragment, Fragment)
        assert len(pipeline.fragments) == 1
        assert pipeline.fragments[0]["type"] == "log"
        assert pipeline.fragments[0]["content"] == "Test log message"
        assert pipeline.fragments[0]["metadata"]["level"] == "info"
        assert pipeline.updated_at >= before_update
    
    def test_add_fragment_with_result(self):
        """Test add_fragment with result field."""
        notebook_item = NotebookItem(assignee_id="user-123")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123"
        )
        
        fragment = pipeline.add_fragment(
            type="execution",
            content="Process completed",
            result={"status": "success", "count": 42}
        )
        
        assert pipeline.fragments[0]["result"]["status"] == "success"
        assert pipeline.fragments[0]["result"]["count"] == 42
    
    def test_update_status_changes_status_and_timestamp(self):
        """Test update_status method."""
        notebook_item = NotebookItem(assignee_id="user-123")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123",
            status="pending"
        )
        
        before_update = pipeline.updated_at
        pipeline.update_status("running")
        
        assert pipeline.status == "running"
        assert pipeline.updated_at >= before_update
        
        pipeline.update_status("completed")
        assert pipeline.status == "completed"
    
    def test_set_error_marks_as_error_and_adds_fragment(self):
        """Test set_error method."""
        notebook_item = NotebookItem(assignee_id="user-123")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123",
            status="running"
        )
        
        pipeline.set_error("Connection timeout")
        
        assert pipeline.status == "error"
        assert pipeline.error == "Connection timeout"
        assert len(pipeline.fragments) == 1
        assert pipeline.fragments[0]["type"] == "execution"
        assert "Error: Connection timeout" in pipeline.fragments[0]["content"]
        assert pipeline.fragments[0]["metadata"]["error"] is True
    
    def test_merge_data_updates_data_dict(self):
        """Test merge_data method."""
        notebook_item = NotebookItem(assignee_id="user-123")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123",
            data={"existing": "value", "count": 1}
        )
        
        before_update = pipeline.updated_at
        pipeline.merge_data({"new_field": "new_value", "count": 2})
        
        assert pipeline.data["existing"] == "value"
        assert pipeline.data["new_field"] == "new_value"
        assert pipeline.data["count"] == 2  # Should be updated
        assert pipeline.updated_at >= before_update
    
    def test_get_fragments_since_with_none_returns_all(self):
        """Test get_fragments_since with None returns all fragments."""
        notebook_item = NotebookItem(assignee_id="user-123")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123"
        )
        
        pipeline.add_fragment("log", "Message 1")
        pipeline.add_fragment("log", "Message 2")
        pipeline.add_fragment("log", "Message 3")
        
        fragments = pipeline.get_fragments_since(None)
        assert len(fragments) == 3
    
    def test_get_fragments_since_with_id_returns_subsequent(self):
        """Test get_fragments_since returns fragments after specified ID."""
        notebook_item = NotebookItem(assignee_id="user-123")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123"
        )
        
        frag1 = pipeline.add_fragment("log", "Message 1")
        frag2 = pipeline.add_fragment("log", "Message 2")
        frag3 = pipeline.add_fragment("log", "Message 3")
        
        # Get fragments since frag1
        fragments = pipeline.get_fragments_since(frag1.id)
        assert len(fragments) == 2
        assert fragments[0]["content"] == "Message 2"
        assert fragments[1]["content"] == "Message 3"
    
    def test_get_fragments_since_nonexistent_id_returns_all(self):
        """Test get_fragments_since with nonexistent ID returns all."""
        notebook_item = NotebookItem(assignee_id="user-123")
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id="cell-1",
            cell_type_id="type-1",
            assignee_id="user-123"
        )
        
        pipeline.add_fragment("log", "Message 1")
        pipeline.add_fragment("log", "Message 2")
        
        fragments = pipeline.get_fragments_since("nonexistent-id")
        assert len(fragments) == 2


class TestModelsIntegration:
    """Integration tests for models working together."""
    
    def test_notebook_item_with_fragment_objects(self):
        """Test notebook item with Fragment objects in fragments list."""
        fragment = Fragment(type="log", content="Test log")
        
        # Fragments accept dicts, so we serialize Fragment
        item = NotebookItem(
            assignee_id="user-123",
            fragments=[fragment.model_dump()]
        )
        
        assert len(item.fragments) == 1
        assert isinstance(item.fragments[0], dict)
        assert item.fragments[0]["type"] == "log"
    
    def test_pipeline_composition_not_inheritance(self):
        """Test that PipelineItem composes NotebookItem, not inherits."""
        notebook_item = NotebookItem(
            assignee_id="user-123",
            initial_data={"original": "data"}
        )
        
        pipeline = PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id=notebook_item.id,
            cell_type_id="type-1",
            assignee_id="user-123",
            data={"pipeline": "data"}
        )
        
        # Pipeline has its own data, separate from notebook item
        assert pipeline.data != pipeline.notebook_item_data.initial_data
        assert pipeline.data == {"pipeline": "data"}
        assert pipeline.notebook_item_data.initial_data == {"original": "data"}
    
    def test_full_execution_workflow(self):
        """Test a complete execution workflow with all models."""
        # 1. Create a notebook item (cell)
        cell = NotebookItem(
            assignee_id="user-123",
            refs={"python": ["script.py"]},
            initial_data={"config": "value"}
        )
        
        # 2. Create a pipeline for execution
        pipeline = PipelineItem(
            notebook_item_id=cell.id,
            notebook_item_data=cell,
            cell_id=cell.id,
            cell_type_id="python-executor",
            assignee_id="user-123",
            status="pending"
        )
        
        # 3. Execute and add fragments
        execution_fragment = {"type": "execution", "step": "start"}
        pipeline.fragments.append(execution_fragment)
        pipeline.status = "running"
        
        # 4. Complete with result
        pipeline.data = {"output": "Success"}
        pipeline.status = "completed"
        
        # Verify final state
        assert pipeline.status == "completed"
        assert len(pipeline.fragments) == 1
        assert pipeline.data["output"] == "Success"
        assert pipeline.notebook_item_data.id == cell.id
