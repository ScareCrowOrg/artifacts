"""
Unit tests for ExecutionRecord model and execution traceability.

Tests the ExecutionRecord DTO and its integration with NotebookItem.fragments.
"""

import pytest
from datetime import datetime
from app.models.execution_models import ExecutionRecord
from app.core.models import NotebookItem, PipelineItem


def test_execution_record_creation():
    """Test creating an ExecutionRecord with all fields."""
    execution_record = ExecutionRecord(
        pipeline_item_id="test-pipeline-123",
        status="completed",
        assignee_id="user-456",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        fragments=[
            {"type": "execucao", "content": "Started execution"},
            {"type": "execucao", "content": "Completed execution"}
        ],
        error=None,
        initial_data_snapshot={"file_path": "/tmp/test.pdf"}
    )
    
    assert execution_record.pipeline_item_id == "test-pipeline-123"
    assert execution_record.status == "completed"
    assert execution_record.assignee_id == "user-456"
    assert execution_record.type == "execution_record"
    assert len(execution_record.fragments) == 2
    assert execution_record.initial_data_snapshot["file_path"] == "/tmp/test.pdf"
    assert execution_record.error is None


def test_execution_record_with_error():
    """Test creating an ExecutionRecord with error status."""
    execution_record = ExecutionRecord(
        pipeline_item_id="test-pipeline-error",
        status="error",
        assignee_id="user-456",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        fragments=[
            {"type": "execucao", "content": "Started execution"},
            {"type": "error", "content": "Failed to process file"}
        ],
        error="File not found: /tmp/test.pdf"
    )
    
    assert execution_record.status == "error"
    assert execution_record.error == "File not found: /tmp/test.pdf"
    assert execution_record.type == "execution_record"


def test_execution_record_type_marker():
    """Test that ExecutionRecord has the correct type marker."""
    execution_record = ExecutionRecord(
        pipeline_item_id="test-pipeline-123",
        status="completed",
        assignee_id="user-456",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Type should be set by default
    assert execution_record.type == "execution_record"
    
    # Serialize to dict and check type marker
    record_dict = execution_record.model_dump(mode='json')
    assert record_dict["type"] == "execution_record"


def test_execution_record_serialization():
    """Test serializing ExecutionRecord to dict for storage."""
    now = datetime.utcnow()
    execution_record = ExecutionRecord(
        pipeline_item_id="test-pipeline-123",
        status="completed",
        assignee_id="user-456",
        created_at=now,
        updated_at=now,
        fragments=[
            {"type": "execucao", "content": "Test fragment"}
        ],
        initial_data_snapshot={"key": "value"}
    )
    
    # Serialize to dict
    record_dict = execution_record.model_dump(mode='json')
    
    # Verify all fields are present
    assert record_dict["pipeline_item_id"] == "test-pipeline-123"
    assert record_dict["status"] == "completed"
    assert record_dict["assignee_id"] == "user-456"
    assert record_dict["type"] == "execution_record"
    assert isinstance(record_dict["created_at"], str)  # Should be ISO format
    assert isinstance(record_dict["updated_at"], str)
    assert len(record_dict["fragments"]) == 1
    assert record_dict["initial_data_snapshot"]["key"] == "value"


def test_execution_record_deserialization():
    """Test deserializing ExecutionRecord from dict."""
    now = datetime.utcnow()
    record_dict = {
        "pipeline_item_id": "test-pipeline-123",
        "status": "completed",
        "assignee_id": "user-456",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "type": "execution_record",
        "fragments": [
            {"type": "execucao", "content": "Test fragment"}
        ],
        "initial_data_snapshot": {"key": "value"},
        "error": None
    }
    
    # Deserialize from dict
    execution_record = ExecutionRecord(**record_dict)
    
    # Verify fields
    assert execution_record.pipeline_item_id == "test-pipeline-123"
    assert execution_record.status == "completed"
    assert execution_record.assignee_id == "user-456"
    assert execution_record.type == "execution_record"
    assert len(execution_record.fragments) == 1


def test_notebook_item_with_execution_record():
    """Test storing ExecutionRecord in NotebookItem.fragments."""
    # Create a NotebookItem
    notebook_item = NotebookItem(
        assignee_id="user-123",
        fragments=[
            "Initial memory fragment",
            {"type": "memoria", "content": "Some context"}
        ]
    )
    
    # Create an ExecutionRecord
    execution_record = ExecutionRecord(
        pipeline_item_id="exec-1",
        status="completed",
        assignee_id="user-123",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        fragments=[{"type": "execucao", "content": "Execution log"}]
    )
    
    # Append ExecutionRecord to fragments as dict
    record_dict = execution_record.model_dump(mode='json')
    notebook_item.fragments.append(record_dict)
    
    # Verify fragments
    assert len(notebook_item.fragments) == 3
    assert isinstance(notebook_item.fragments[0], str)
    assert isinstance(notebook_item.fragments[1], dict)
    assert isinstance(notebook_item.fragments[2], dict)
    assert notebook_item.fragments[2]["type"] == "execution_record"


def test_filter_execution_records_from_fragments():
    """Test filtering execution records from mixed fragments."""
    fragments = [
        "Simple string fragment",
        {"type": "memoria", "content": "Memory fragment"},
        {
            "type": "execution_record",
            "pipeline_item_id": "exec-1",
            "status": "completed",
            "assignee_id": "user-123",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "fragments": []
        },
        {"type": "error", "content": "Some error"},
        {
            "type": "execution_record",
            "pipeline_item_id": "exec-2",
            "status": "error",
            "assignee_id": "user-123",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "fragments": [],
            "error": "Test error"
        }
    ]
    
    # Filter execution records
    execution_records = []
    for fragment in fragments:
        if isinstance(fragment, dict) and fragment.get("type") == "execution_record":
            try:
                execution_record = ExecutionRecord(**fragment)
                execution_records.append(execution_record)
            except Exception:
                pass
    
    # Verify filtering
    assert len(execution_records) == 2
    assert execution_records[0].pipeline_item_id == "exec-1"
    assert execution_records[0].status == "completed"
    assert execution_records[1].pipeline_item_id == "exec-2"
    assert execution_records[1].status == "error"


def test_execution_record_from_pipeline_item():
    """Test creating ExecutionRecord from PipelineItem."""
    # Create a NotebookItem
    notebook_item = NotebookItem(
        assignee_id="user-123",
        initial_data={"file_path": "/tmp/test.pdf"}
    )
    
    # Create a PipelineItem
    pipeline_item = PipelineItem(
        notebook_item_id=notebook_item.id,
        notebook_item_data=notebook_item,
        cell_id=notebook_item.id,
        cell_type_id="type-1",
        assignee_id="user-123",
        status="completed",
        fragments=[
            {"type": "execucao", "content": "Started"},
            {"type": "execucao", "content": "Completed"}
        ]
    )
    
    # Create ExecutionRecord from PipelineItem
    execution_record = ExecutionRecord(
        pipeline_item_id=pipeline_item.id,
        status=pipeline_item.status,
        assignee_id=pipeline_item.assignee_id,
        created_at=pipeline_item.created_at,
        updated_at=pipeline_item.updated_at,
        fragments=pipeline_item.fragments,
        error=pipeline_item.error,
        initial_data_snapshot=notebook_item.initial_data.copy()
    )
    
    # Verify ExecutionRecord
    assert execution_record.pipeline_item_id == pipeline_item.id
    assert execution_record.status == "completed"
    assert len(execution_record.fragments) == 2
    assert execution_record.initial_data_snapshot["file_path"] == "/tmp/test.pdf"


def test_multiple_executions_in_notebook_item():
    """Test storing multiple execution records in NotebookItem.fragments."""
    # Create a NotebookItem
    notebook_item = NotebookItem(
        assignee_id="user-123",
        fragments=["Initial memory"]
    )
    
    # Add first execution
    exec_1 = ExecutionRecord(
        pipeline_item_id="exec-1",
        status="completed",
        assignee_id="user-123",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    notebook_item.fragments.append(exec_1.model_dump(mode='json'))
    
    # Add second execution
    exec_2 = ExecutionRecord(
        pipeline_item_id="exec-2",
        status="error",
        assignee_id="user-123",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        error="Test error"
    )
    notebook_item.fragments.append(exec_2.model_dump(mode='json'))
    
    # Verify multiple executions
    assert len(notebook_item.fragments) == 3
    
    # Extract execution records
    exec_records = [
        ExecutionRecord(**f)
        for f in notebook_item.fragments
        if isinstance(f, dict) and f.get("type") == "execution_record"
    ]
    
    assert len(exec_records) == 2
    assert exec_records[0].pipeline_item_id == "exec-1"
    assert exec_records[0].status == "completed"
    assert exec_records[1].pipeline_item_id == "exec-2"
    assert exec_records[1].status == "error"
