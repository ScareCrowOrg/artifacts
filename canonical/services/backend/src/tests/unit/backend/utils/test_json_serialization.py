"""
Unit tests for JSON serialization utilities.

Tests cover:
- Datetime object serialization
- Nested structure serialization
- Pydantic model serialization
- Edge cases and error handling
"""

import pytest
from datetime import datetime, date
from pydantic import BaseModel, Field

from app.utils.json_serialization import serialize_for_json, safe_json_serialize


class SampleModel(BaseModel):
    """Sample Pydantic model for testing."""
    id: str
    created_at: datetime
    name: str


class NestedModel(BaseModel):
    """Nested Pydantic model for testing."""
    id: str
    user: SampleModel
    updated_at: datetime


def test_serialize_datetime():
    """Test datetime object serialization."""
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = serialize_for_json(dt)
    
    assert isinstance(result, str)
    assert result == "2023-01-01T12:00:00"


def test_serialize_date():
    """Test date object serialization."""
    d = date(2023, 1, 1)
    result = serialize_for_json(d)
    
    assert isinstance(result, str)
    assert result == "2023-01-01"


def test_serialize_dict_with_datetime():
    """Test dictionary with datetime values."""
    data = {
        "id": "123",
        "created_at": datetime(2023, 1, 1, 12, 0, 0),
        "name": "test"
    }
    
    result = serialize_for_json(data)
    
    assert result["id"] == "123"
    assert result["created_at"] == "2023-01-01T12:00:00"
    assert result["name"] == "test"


def test_serialize_nested_dict_with_datetime():
    """Test nested dictionary with datetime values."""
    data = {
        "user": {
            "id": "user-123",
            "joined": datetime(2023, 1, 1, 10, 0, 0)
        },
        "event": {
            "id": "event-456",
            "timestamp": datetime(2023, 1, 2, 14, 30, 0)
        }
    }
    
    result = serialize_for_json(data)
    
    assert result["user"]["joined"] == "2023-01-01T10:00:00"
    assert result["event"]["timestamp"] == "2023-01-02T14:30:00"


def test_serialize_list_with_datetime():
    """Test list with datetime objects."""
    data = [
        datetime(2023, 1, 1),
        datetime(2023, 1, 2),
        datetime(2023, 1, 3)
    ]
    
    result = serialize_for_json(data)
    
    assert len(result) == 3
    assert result[0] == "2023-01-01T00:00:00"
    assert result[1] == "2023-01-02T00:00:00"
    assert result[2] == "2023-01-03T00:00:00"


def test_serialize_list_of_dicts_with_datetime():
    """Test list of dictionaries with datetime values."""
    data = [
        {"id": "1", "timestamp": datetime(2023, 1, 1, 10, 0, 0)},
        {"id": "2", "timestamp": datetime(2023, 1, 2, 11, 0, 0)}
    ]
    
    result = serialize_for_json(data)
    
    assert len(result) == 2
    assert result[0]["timestamp"] == "2023-01-01T10:00:00"
    assert result[1]["timestamp"] == "2023-01-02T11:00:00"


def test_serialize_pydantic_model():
    """Test Pydantic model serialization."""
    model = SampleModel(
        id="test-123",
        created_at=datetime(2023, 1, 1, 12, 0, 0),
        name="Test User"
    )
    
    result = serialize_for_json(model)
    
    assert isinstance(result, dict)
    assert result["id"] == "test-123"
    assert result["created_at"] == "2023-01-01T12:00:00"
    assert result["name"] == "Test User"


def test_serialize_nested_pydantic_model():
    """Test nested Pydantic model serialization."""
    user = SampleModel(
        id="user-123",
        created_at=datetime(2023, 1, 1, 10, 0, 0),
        name="John Doe"
    )
    
    nested = NestedModel(
        id="nested-456",
        user=user,
        updated_at=datetime(2023, 1, 2, 14, 30, 0)
    )
    
    result = serialize_for_json(nested)
    
    assert isinstance(result, dict)
    assert result["id"] == "nested-456"
    assert result["updated_at"] == "2023-01-02T14:30:00"
    assert result["user"]["id"] == "user-123"
    assert result["user"]["created_at"] == "2023-01-01T10:00:00"


def test_serialize_passthrough_types():
    """Test that JSON-serializable types pass through unchanged."""
    # Test various native types
    assert serialize_for_json(None) is None
    assert serialize_for_json(True) is True
    assert serialize_for_json(False) is False
    assert serialize_for_json(42) == 42
    assert serialize_for_json(3.14) == 3.14
    assert serialize_for_json("test") == "test"


def test_serialize_complex_structure():
    """Test complex nested structure with mixed types."""
    data = {
        "id": "complex-123",
        "created_at": datetime(2023, 1, 1, 12, 0, 0),
        "users": [
            {
                "id": "user-1",
                "joined": datetime(2023, 1, 2, 10, 0, 0),
                "active": True
            },
            {
                "id": "user-2",
                "joined": datetime(2023, 1, 3, 11, 0, 0),
                "active": False
            }
        ],
        "metadata": {
            "version": "1.0",
            "updated_at": datetime(2023, 1, 4, 15, 30, 0),
            "tags": ["tag1", "tag2"]
        },
        "count": 42
    }
    
    result = serialize_for_json(data)
    
    assert result["id"] == "complex-123"
    assert result["created_at"] == "2023-01-01T12:00:00"
    assert result["users"][0]["joined"] == "2023-01-02T10:00:00"
    assert result["users"][1]["joined"] == "2023-01-03T11:00:00"
    assert result["metadata"]["updated_at"] == "2023-01-04T15:30:00"
    assert result["metadata"]["tags"] == ["tag1", "tag2"]
    assert result["count"] == 42


def test_serialize_empty_structures():
    """Test serialization of empty structures."""
    assert serialize_for_json({}) == {}
    assert serialize_for_json([]) == []
    assert serialize_for_json(()) == []


def test_serialize_tuple_with_datetime():
    """Test tuple with datetime objects (converted to list)."""
    data = (datetime(2023, 1, 1), "test", 42)
    
    result = serialize_for_json(data)
    
    assert isinstance(result, list)
    assert result[0] == "2023-01-01T00:00:00"
    assert result[1] == "test"
    assert result[2] == 42


def test_safe_json_serialize_success():
    """Test safe_json_serialize with valid data."""
    data = {
        "id": "test",
        "created_at": datetime(2023, 1, 1)
    }
    
    result = safe_json_serialize(data)
    
    assert result["id"] == "test"
    assert result["created_at"] == "2023-01-01T00:00:00"


def test_safe_json_serialize_with_error():
    """Test safe_json_serialize error handling (edge case)."""
    # This test validates that safe_json_serialize handles unexpected errors gracefully
    # In practice, serialize_for_json is quite robust, but the wrapper provides extra safety
    
    # Create a mock object that will cause issues during serialization
    class ProblematicObject:
        def __getattribute__(self, name):
            raise RuntimeError("Simulated serialization error")
    
    result = safe_json_serialize(ProblematicObject())
    
    # Should return error dict instead of raising
    assert "error" in result
    assert result["error"] == "Serialization failed"


def test_serialize_cell_data_like_structure():
    """Test serialization of structure similar to cell_data from event bus."""
    # This simulates the actual use case from the bug report
    cell_data = {
        "id": "cell-123",
        "assignee_id": "user-456",
        "notebook_item_type_id": "type-789",
        "created_at": datetime(2023, 1, 1, 10, 0, 0),
        "updated_at": datetime(2023, 1, 2, 14, 30, 0),
        "status": "PENDING",
        "fragments": [
            {
                "type": "execution",
                "content": "Test fragment",
                "timestamp": datetime(2023, 1, 1, 10, 5, 0)
            }
        ],
        "initial_data": {
            "source": "test",
            "created": datetime(2023, 1, 1, 9, 0, 0)
        }
    }
    
    result = serialize_for_json(cell_data)
    
    # Verify all datetime objects are serialized
    assert result["created_at"] == "2023-01-01T10:00:00"
    assert result["updated_at"] == "2023-01-02T14:30:00"
    assert result["fragments"][0]["timestamp"] == "2023-01-01T10:05:00"
    assert result["initial_data"]["created"] == "2023-01-01T09:00:00"
    
    # Verify other fields are preserved
    assert result["id"] == "cell-123"
    assert result["status"] == "PENDING"
    assert result["fragments"][0]["content"] == "Test fragment"
