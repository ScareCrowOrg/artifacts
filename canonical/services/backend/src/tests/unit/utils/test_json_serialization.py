"""
Tests for JSON serialization utilities.

Ensures JSON serialization handles various Python types correctly.
"""

import pytest
from datetime import datetime, date
from pydantic import BaseModel

from app.utils.json_serialization import serialize_for_json, safe_json_serialize


class MockPydanticModel(BaseModel):
    """Mock Pydantic model for testing."""
    name: str
    count: int
    created_at: datetime


class TestSerializeForJson:
    """Tests for serialize_for_json function."""
    
    def test_serialize_datetime(self):
        """Test datetime serialization to ISO format."""
        dt = datetime(2023, 1, 15, 10, 30, 45)
        result = serialize_for_json(dt)
        
        assert result == "2023-01-15T10:30:45"
        assert isinstance(result, str)
    
    def test_serialize_date(self):
        """Test date serialization to ISO format."""
        d = date(2023, 1, 15)
        result = serialize_for_json(d)
        
        assert result == "2023-01-15"
        assert isinstance(result, str)
    
    def test_serialize_dict_with_datetime(self):
        """Test dict with datetime values."""
        data = {
            "created_at": datetime(2023, 1, 1, 12, 0, 0),
            "name": "test"
        }
        result = serialize_for_json(data)
        
        assert result["created_at"] == "2023-01-01T12:00:00"
        assert result["name"] == "test"
    
    def test_serialize_nested_dict(self):
        """Test nested dict with datetime."""
        data = {
            "user": {
                "joined": datetime(2023, 1, 1, 0, 0, 0),
                "name": "Alice"
            },
            "count": 5
        }
        result = serialize_for_json(data)
        
        assert result["user"]["joined"] == "2023-01-01T00:00:00"
        assert result["user"]["name"] == "Alice"
        assert result["count"] == 5
    
    def test_serialize_list_with_datetime(self):
        """Test list with datetime objects."""
        data = [
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 2, 1, 0, 0, 0)
        ]
        result = serialize_for_json(data)
        
        assert len(result) == 2
        assert result[0] == "2023-01-01T00:00:00"
        assert result[1] == "2023-02-01T00:00:00"
    
    def test_serialize_tuple_with_datetime(self):
        """Test tuple with datetime objects."""
        data = (
            datetime(2023, 1, 1, 0, 0, 0),
            "test"
        )
        result = serialize_for_json(data)
        
        assert isinstance(result, list)  # Tuples convert to lists
        assert len(result) == 2
        assert result[0] == "2023-01-01T00:00:00"
        assert result[1] == "test"
    
    def test_serialize_list_of_dicts_with_datetime(self):
        """Test list of dicts with datetime."""
        data = [
            {"created_at": datetime(2023, 1, 1, 0, 0, 0), "name": "item1"},
            {"created_at": datetime(2023, 2, 1, 0, 0, 0), "name": "item2"}
        ]
        result = serialize_for_json(data)
        
        assert len(result) == 2
        assert result[0]["created_at"] == "2023-01-01T00:00:00"
        assert result[1]["created_at"] == "2023-02-01T00:00:00"
    
    def test_serialize_primitive_types(self):
        """Test that primitive types pass through unchanged."""
        assert serialize_for_json(None) is None
        assert serialize_for_json(True) is True
        assert serialize_for_json(False) is False
        assert serialize_for_json(42) == 42
        assert serialize_for_json(3.14) == 3.14
        assert serialize_for_json("test") == "test"
    
    def test_serialize_empty_dict(self):
        """Test empty dict serialization."""
        result = serialize_for_json({})
        assert result == {}
    
    def test_serialize_empty_list(self):
        """Test empty list serialization."""
        result = serialize_for_json([])
        assert result == []
    
    def test_serialize_pydantic_model(self):
        """Test Pydantic model serialization."""
        model = MockPydanticModel(
            name="test",
            count=5,
            created_at=datetime(2023, 1, 1, 12, 0, 0)
        )
        result = serialize_for_json(model)
        
        assert result["name"] == "test"
        assert result["count"] == 5
        assert result["created_at"] == "2023-01-01T12:00:00"
    
    def test_serialize_deeply_nested(self):
        """Test deeply nested structures."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "datetime": datetime(2023, 1, 1, 0, 0, 0),
                        "list": [
                            {"nested_dt": datetime(2023, 2, 1, 0, 0, 0)}
                        ]
                    }
                }
            }
        }
        result = serialize_for_json(data)
        
        assert result["level1"]["level2"]["level3"]["datetime"] == "2023-01-01T00:00:00"
        assert result["level1"]["level2"]["level3"]["list"][0]["nested_dt"] == "2023-02-01T00:00:00"
    
    def test_serialize_mixed_list(self):
        """Test list with mixed types."""
        data = [
            42,
            "test",
            datetime(2023, 1, 1, 0, 0, 0),
            {"key": "value"},
            None,
            True
        ]
        result = serialize_for_json(data)
        
        assert len(result) == 6
        assert result[0] == 42
        assert result[1] == "test"
        assert result[2] == "2023-01-01T00:00:00"
        assert result[3] == {"key": "value"}
        assert result[4] is None
        assert result[5] is True


class TestSafeJsonSerialize:
    """Tests for safe_json_serialize function."""
    
    def test_safe_serialize_dict(self):
        """Test safe serialization of dict."""
        data = {
            "created_at": datetime(2023, 1, 1, 0, 0, 0),
            "name": "test"
        }
        result = safe_json_serialize(data)
        
        assert result["created_at"] == "2023-01-01T00:00:00"
        assert result["name"] == "test"
    
    def test_safe_serialize_list(self):
        """Test safe serialization of list."""
        data = [
            datetime(2023, 1, 1, 0, 0, 0),
            "test"
        ]
        result = safe_json_serialize(data)
        
        assert result[0] == "2023-01-01T00:00:00"
        assert result[1] == "test"
    
    def test_safe_serialize_primitive(self):
        """Test safe serialization of primitive."""
        assert safe_json_serialize(42) == 42
        assert safe_json_serialize("test") == "test"
        assert safe_json_serialize(None) is None
    
    def test_safe_serialize_pydantic_model(self):
        """Test safe serialization of Pydantic model."""
        model = MockPydanticModel(
            name="test",
            count=10,
            created_at=datetime(2023, 1, 1, 0, 0, 0)
        )
        result = safe_json_serialize(model)
        
        assert result["name"] == "test"
        assert result["count"] == 10
        assert result["created_at"] == "2023-01-01T00:00:00"
    
    def test_safe_serialize_empty_structures(self):
        """Test safe serialization of empty structures."""
        assert safe_json_serialize({}) == {}
        assert safe_json_serialize([]) == []


class TestErrorHandling:
    """Tests for error handling in serialization."""
    
    def test_serialize_pydantic_model_error(self):
        """Test error handling when Pydantic model fails to serialize."""
        
        class BrokenModel:
            """Mock model that raises on model_dump."""
            def model_dump(self):
                raise ValueError("Model dump failed")
        
        broken = BrokenModel()
        result = serialize_for_json(broken)
        
        assert isinstance(result, dict)
        assert result["error"] == "PydanticSerializationError"
        assert result["model_type"] == "BrokenModel"
        assert "Model dump failed" in result["message"]
    
    def test_safe_json_serialize_with_exception(self):
        """Test safe_json_serialize handles unexpected exceptions."""
        # Create a scenario that causes an exception in serialize_for_json
        # We'll use a deeply circular reference which will cause a RecursionError
        circular = {}
        circular['self'] = circular
        
        # Mock the serialize_for_json to raise an exception
        import app.utils.json_serialization as js_module
        original_func = js_module.serialize_for_json
        
        def mock_serialize(obj):
            if obj == "trigger_error":
                raise ValueError("Test error")
            return original_func(obj)
        
        # Temporarily replace function
        js_module.serialize_for_json = mock_serialize
        
        try:
            result = safe_json_serialize("trigger_error")
            assert isinstance(result, dict)
            assert result["error"] == "Serialization failed"
            assert "Test error" in result["message"]
        finally:
            # Restore original function
            js_module.serialize_for_json = original_func
