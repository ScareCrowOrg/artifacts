"""
Tests for SchemaGenerator - Auto-generation of SCHEMAS.json from Pydantic models.

This test suite validates the schema generation logic, type mapping,
and constraint extraction from Pydantic models.
"""

import pytest
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from app.database.schema_generator import SchemaGenerator


# Test fixtures - Sample Pydantic models

class SampleStatus(str, Enum):
    """Sample enum for testing."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class SimpleSampleModel(BaseModel):
    """Simple model for basic type testing."""
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Name field")
    count: int = Field(..., description="Count value")
    price: float = Field(..., description="Price value")
    is_active: bool = Field(default=True, description="Active flag")
    created_at: datetime = Field(..., description="Creation timestamp")


class ComplexSampleModel(BaseModel):
    """Complex model for advanced type testing."""
    id: str = Field(..., description="Unique identifier")
    optional_field: Optional[str] = Field(None, description="Optional text")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Metadata dictionary")
    tags: List[str] = Field(default_factory=list, description="Tag list")
    status: SampleStatus = Field(..., description="Status enum")
    config: Optional[Dict] = Field(None, description="Configuration")


class TestSchemaGenerator:
    """Test suite for SchemaGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create a schema generator instance."""
        return SchemaGenerator()
    
    def test_generator_initialization(self, generator):
        """Test that generator initializes correctly."""
        assert generator is not None
        assert generator.type_mapping is not None
        assert len(generator.type_mapping) > 0
    
    def test_simple_type_mapping(self, generator):
        """Test basic Python type to SQLite type mapping."""
        assert generator._python_type_to_sqlite(str) == "TEXT"
        assert generator._python_type_to_sqlite(int) == "INTEGER"
        assert generator._python_type_to_sqlite(float) == "REAL"
        assert generator._python_type_to_sqlite(bool) == "INTEGER"
        assert generator._python_type_to_sqlite(datetime) == "DATETIME"
        assert generator._python_type_to_sqlite(dict) == "JSON"
        assert generator._python_type_to_sqlite(list) == "JSON"
    
    def test_optional_type_mapping(self, generator):
        """Test Optional type handling."""
        # Optional[str] should map to TEXT
        optional_str = Optional[str]
        assert generator._python_type_to_sqlite(optional_str) == "TEXT"
        
        # Optional[int] should map to INTEGER
        optional_int = Optional[int]
        assert generator._python_type_to_sqlite(optional_int) == "INTEGER"
    
    def test_collection_type_mapping(self, generator):
        """Test Dict and List type mapping."""
        # Dict should map to JSON
        assert generator._python_type_to_sqlite(Dict) == "JSON"
        assert generator._python_type_to_sqlite(Dict[str, str]) == "JSON"
        
        # List should map to JSON
        assert generator._python_type_to_sqlite(List) == "JSON"
        assert generator._python_type_to_sqlite(List[str]) == "JSON"
    
    def test_enum_type_mapping(self, generator):
        """Test Enum type mapping."""
        # Enum should map to TEXT
        assert generator._python_type_to_sqlite(SampleStatus) == "TEXT"
    
    def test_is_optional_detection(self, generator):
        """Test Optional type detection."""
        assert generator._is_optional(Optional[str]) is True
        assert generator._is_optional(str) is False
        assert generator._is_optional(Optional[int]) is True
        assert generator._is_optional(int) is False
    
    def test_should_be_indexed(self, generator):
        """Test field indexing logic."""
        # Foreign key fields should be indexed
        assert generator._should_be_indexed("user_id", str) is True
        assert generator._should_be_indexed("assignee_id", str) is True
        
        # Common query fields should be indexed
        assert generator._should_be_indexed("status", str) is True
        assert generator._should_be_indexed("name", str) is True
        assert generator._should_be_indexed("created_at", datetime) is True
        assert generator._should_be_indexed("type", str) is True
        
        # Regular fields should not be indexed
        assert generator._should_be_indexed("description", str) is False
        assert generator._should_be_indexed("data", dict) is False
    
    def test_generate_schema_simple_model(self, generator):
        """Test schema generation for a simple model."""
        schema = generator.generate_schema(
            SimpleSampleModel,
            collection_name="simple_samples"
        )
        
        # Check that all fields are present
        assert "_id" in schema  # id mapped to _id
        assert "name" in schema
        assert "count" in schema
        assert "price" in schema
        assert "is_active" in schema
        assert "created_at" in schema
        
        # Check field types
        assert schema["_id"]["type"] == "TEXT"
        assert schema["name"]["type"] == "TEXT"
        assert schema["count"]["type"] == "INTEGER"
        assert schema["price"]["type"] == "REAL"
        assert schema["is_active"]["type"] == "INTEGER"  # bool → INTEGER
        assert schema["created_at"]["type"] == "DATETIME"
        
        # Check constraints
        assert "PRIMARY KEY" in schema["_id"]["constraints"]
        assert "NOT NULL" in schema["name"]["constraints"]
        
        # Check descriptions
        assert schema["_id"]["description"] == "Unique identifier"
        assert schema["name"]["description"] == "Name field"
    
    def test_generate_schema_complex_model(self, generator):
        """Test schema generation for a complex model."""
        schema = generator.generate_schema(
            ComplexSampleModel,
            collection_name="complex_samples"
        )
        
        # Check that all fields are present
        assert "_id" in schema
        assert "optional_field" in schema
        assert "metadata" in schema
        assert "tags" in schema
        assert "status" in schema
        assert "config" in schema
        
        # Check complex field types
        assert schema["metadata"]["type"] == "JSON"
        assert schema["tags"]["type"] == "JSON"
        assert schema["status"]["type"] == "TEXT"  # Enum → TEXT
        assert schema["config"]["type"] == "JSON"
        
        # Check optional fields don't have NOT NULL constraint
        assert "NOT NULL" not in schema["optional_field"].get("constraints", "")
    
    def test_generate_all_schemas(self, generator):
        """Test bulk schema generation."""
        model_mapping = {
            "simple_samples": SimpleSampleModel,
            "complex_samples": ComplexSampleModel,
        }
        
        schemas = generator.generate_all_schemas(model_mapping)
        
        # Check metadata fields
        assert "version" in schemas
        assert "description" in schemas
        assert "last_updated" in schemas
        
        # Check collections
        assert "simple_samples" in schemas
        assert "complex_samples" in schemas
        
        # Check that description mentions auto-generation
        assert "AUTO-GENERATED" in schemas["description"]
        assert "DO NOT EDIT MANUALLY" in schemas["description"]
    
    def test_extract_description(self, generator):
        """Test field description extraction."""
        field_info = Field(..., description="Test description")
        description = generator._extract_description(field_info)
        assert description == "Test description"
        
        # Test field without description
        field_info_no_desc = Field(...)
        description_empty = generator._extract_description(field_info_no_desc)
        assert description_empty == ""
    
    def test_extract_constraints_primary_key(self, generator):
        """Test primary key constraint extraction."""
        from pydantic.fields import FieldInfo
        
        field_info = FieldInfo(annotation=str, default=...)
        constraints = generator._extract_constraints(
            field_name="id",
            field_info=field_info,
            field_type=str,
            is_primary_key=True
        )
        
        assert "PRIMARY KEY" in constraints
    
    def test_extract_constraints_not_null(self, generator):
        """Test NOT NULL constraint extraction."""
        from pydantic.fields import FieldInfo
        
        # Required field should have NOT NULL
        field_info = FieldInfo(annotation=str, default=...)
        constraints = generator._extract_constraints(
            field_name="name",
            field_info=field_info,
            field_type=str,
            is_primary_key=False
        )
        
        assert "NOT NULL" in constraints
    
    def test_extract_constraints_optional(self, generator):
        """Test that optional fields don't have NOT NULL."""
        from pydantic.fields import FieldInfo
        
        # Optional field should not have NOT NULL
        field_info = FieldInfo(annotation=Optional[str], default=None)
        constraints = generator._extract_constraints(
            field_name="optional_field",
            field_info=field_info,
            field_type=Optional[str],
            is_primary_key=False
        )
        
        # Optional fields should not have NOT NULL
        assert "NOT NULL" not in constraints or constraints == ""


class TestSchemaGeneratorEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def generator(self):
        """Create a schema generator instance."""
        return SchemaGenerator()
    
    def test_unknown_type_defaults_to_text(self, generator):
        """Test that unknown types default to TEXT."""
        # Custom class not in type_mapping
        class CustomType:
            pass
        
        result = generator._python_type_to_sqlite(CustomType)
        assert result == "TEXT"
    
    def test_none_type_handling(self, generator):
        """Test None type handling."""
        result = generator._python_type_to_sqlite(type(None))
        assert result == "NULL"
    
    def test_empty_model(self, generator):
        """Test schema generation for model with no fields except id."""
        class EmptyModel(BaseModel):
            id: str = Field(..., description="ID")
        
        schema = generator.generate_schema(EmptyModel, "empty")
        assert "_id" in schema
        assert len(schema) == 1
    
    def test_schema_generation_error_handling(self, generator):
        """Test error handling in bulk schema generation."""
        # Include a valid model and an invalid one
        model_mapping = {
            "valid": SimpleSampleModel,
            # Invalid model (not a class)
            "invalid": "not_a_model",
        }
        
        # Should not raise exception, just log error and continue
        schemas = generator.generate_all_schemas(model_mapping)
        
        # Valid model should be in schemas
        assert "valid" in schemas
        # Invalid model should not be in schemas
        assert "invalid" not in schemas


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
