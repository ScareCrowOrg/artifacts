"""
Tests for NotebookItemType model with discovery metadata.

These tests validate the enhanced NotebookItemType schema with discovery field.
"""

import pytest
from pydantic import ValidationError
from datetime import datetime

from app.models.content import NotebookItemType, DiscoveryMetadata


class TestDiscoveryMetadata:
    """Test suite for DiscoveryMetadata model"""

    def test_minimaldiscovery_metadata(self):
        """Test creating DiscoveryMetadata with only required fields"""
        metadata = DiscoveryMetadata(describe="A simple test cell for validation")

        assert metadata.describe == "A simple test cell for validation"
        assert metadata.labels == []
        assert metadata.estimated_duration_seconds is None
        assert metadata.required_resources == []
        assert metadata.dependencies == []
        assert metadata.tags == []
        assert metadata.use_cases == []

    def test_completediscovery_metadata(self):
        """Test creating DiscoveryMetadata with all fields"""
        metadata = DiscoveryMetadata(
            labels=["#3d", "#generation", "#mesh"],
            describe="Generates high-quality 3D meshes from images using SF3D model",
            estimated_duration_seconds=180,
            required_resources=["gpu", "8gb-vram"],
            dependencies=["sf3d-runtime", "rembg"],
            tags=["3d", "generation", "quality"],
            use_cases=[
                "Convert concept art to 3D prototypes",
                "Generate game assets from images",
            ],
        )

        assert len(metadata.labels) == 3
        assert metadata.labels[0] == "#3d"
        assert metadata.estimated_duration_seconds == 180
        assert len(metadata.required_resources) == 2
        assert len(metadata.dependencies) == 2
        assert len(metadata.use_cases) == 2

    def testdiscovery_metadata_validation_missing_describe(self):
        """Test that describe field is required"""
        with pytest.raises(ValidationError) as exc_info:
            DiscoveryMetadata(
                labels=["#test"],
                # Missing describe field
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("describe",)
        assert errors[0]["type"] == "missing"

    def testdiscovery_metadata_empty_describe(self):
        """Test that empty describe is allowed (will be caught in semantic validation)"""
        # Empty string is technically valid for Pydantic, but semantically wrong
        # This should be caught by higher-level validation or documentation
        metadata = DiscoveryMetadata(describe="")
        assert metadata.describe == ""


class TestNotebookItemTypeWithDiscovery:
    """Test suite for NotebookItemType with discovery field"""

    def test_notebook_item_type_withoutdiscovery(self):
        """Test backward compatibility - NotebookItemType without discovery field"""
        item_type = NotebookItemType(
            id="test-cell",
            name="Test Cell",
            description="A test cell without discovery metadata",
        )

        assert item_type.id == "test-cell"
        assert item_type.name == "Test Cell"
        assert item_type.discovery is None  # Should be None, not error

    def test_notebook_item_type_withdiscovery(self):
        """Test NotebookItemType with complete discovery field"""
        discovery = DiscoveryMetadata(
            labels=["#planning", "#discovery"],
            describe="Autonomous planning cell that discovers cells and generates DAGs",
            estimated_duration_seconds=30,
            required_resources=["discovery-service", "llm-service"],
            dependencies=["discovery-service"],
            tags=["planning", "autonomous"],
            use_cases=["Transform user intent into executable workflows"],
        )

        item_type = NotebookItemType(
            id="planner-cell",
            name="Planner Cell",
            description="Autonomous planning cell",
            discovery=discovery,
        )

        assert item_type.id == "planner-cell"
        assert item_type.discovery is not None
        assert item_type.discovery.describe.startswith("Autonomous planning")
        assert len(item_type.discovery.labels) == 2
        assert item_type.discovery.estimated_duration_seconds == 30

    def test_notebook_item_type_from_dict_withdiscovery(self):
        """Test creating NotebookItemType from dict (like loading from JSON)"""
        data = {
            "id": "test-cell",
            "name": "Test Cell",
            "description": "Test cell with discovery",
            "discovery": {
                "labels": ["#test", "#validation"],
                "describe": "A test cell for validation purposes",
                "estimated_duration_seconds": 10,
                "required_resources": ["test-runner"],
                "dependencies": [],
                "tags": ["test"],
                "use_cases": ["Validate schema", "Test discovery system"],
            },
        }

        item_type = NotebookItemType(**data)

        assert item_type.id == "test-cell"
        assert item_type.discovery is not None
        assert item_type.discovery.labels == ["#test", "#validation"]
        assert item_type.discovery.estimated_duration_seconds == 10
        assert len(item_type.discovery.use_cases) == 2

    def test_notebook_item_type_from_dict_withoutdiscovery(self):
        """Test creating NotebookItemType from dict without discovery field"""
        data = {
            "id": "simple-cell",
            "name": "Simple Cell",
            "description": "A simple cell",
        }

        item_type = NotebookItemType(**data)

        assert item_type.id == "simple-cell"
        assert item_type.discovery is None

    def test_notebook_item_type_serialization_withdiscovery(self):
        """Test that NotebookItemType with discovery can be serialized to dict"""
        item_type = NotebookItemType(
            id="test-cell",
            name="Test Cell",
            discovery=DiscoveryMetadata(
                labels=["#test"],
                describe="Test description",
            ),
        )

        data = item_type.model_dump(by_alias=True)

        assert data["id"] == "test-cell"
        assert "_discovery" in data  # Uses alias
        assert data["_discovery"]["labels"] == ["#test"]
        assert data["_discovery"]["describe"] == "Test description"

    def test_notebook_item_type_json_serialization(self):
        """Test that NotebookItemType can be serialized to JSON string"""
        item_type = NotebookItemType(
            id="test-cell",
            name="Test Cell",
            discovery=DiscoveryMetadata(
                labels=["#test"],
                describe="Test description",
            ),
        )

        json_str = item_type.model_dump_json(by_alias=True)

        assert '"id":"test-cell"' in json_str or '"id": "test-cell"' in json_str
        assert '"_discovery"' in json_str  # Uses alias
        assert '"labels":["#test"]' in json_str or '"labels": ["#test"]' in json_str

    def test_notebook_item_type_validation_invaliddiscovery(self):
        """Test that invalid discovery field raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            NotebookItemType(
                id="test-cell",
                name="Test Cell",
                discovery={
                    "labels": ["#test"],
                    # Missing required 'describe' field
                },
            )

        errors = exc_info.value.errors()
        # Should have error about missing describe field in discovery
        assert any("describe" in str(err["loc"]) for err in errors)

    def test_notebook_item_type_all_fields_withdiscovery(self):
        """Test NotebookItemType with all fields including discovery"""
        item_type = NotebookItemType(
            id="full-cell",
            name="Full Cell",
            description="A cell with all fields",
            default_refs={
                "scripts": ["backend/scripts/main.py"],
                "view": ["frontend/View.vue"],
            },
            default_initial_data={"message": "Hello"},
            allow_instance_override_refs=True,
            can_render_dynamically=True,
            discovery=DiscoveryMetadata(
                labels=["#full", "#test"],
                describe="Complete test cell with all fields",
                estimated_duration_seconds=5,
                required_resources=["test-env"],
                dependencies=["test-framework"],
                tags=["complete", "test"],
                use_cases=["Test all features"],
            ),
        )

        assert item_type.id == "full-cell"
        assert item_type.name == "Full Cell"
        assert item_type.description == "A cell with all fields"
        assert "scripts" in item_type.default_refs
        assert "message" in item_type.default_initial_data
        assert item_type.allow_instance_override_refs is True
        assert item_type.can_render_dynamically is True
        assert item_type.discovery is not None
        assert len(item_type.discovery.labels) == 2
        assert item_type.discovery.estimated_duration_seconds == 5


class TestNotebookItemTypeRegistryCompatibility:
    """Test compatibility with NotebookItemTypeRegistry"""

    def test_type_json_structure_compatibility(self):
        """Test that structure matches real type.json files"""
        # Simulate loading from a real type.json file
        type_json_data = {
            "id": "planner-cell",
            "name": "Planner Cell",
            "description": "Autonomous planning cell",
            "version": "1.0.0",
            "category": "planning",
            "can_render_dynamically": True,
            "default_refs": {
                "view": ["frontend/View.vue"],
                "scripts": ["backend/scripts/main.py"],
            },
            "default_initial_data": {
                "category": "ephemeral",
                "intent": "",
            },
            "allow_instance_override_refs": True,
            "discovery": {
                "labels": ["#planning", "#discovery"],
                "describe": "Autonomous planning cell that discovers cells",
                "estimated_duration_seconds": 30,
                "required_resources": ["discovery-service"],
                "dependencies": ["discovery-service"],
                "tags": ["planning"],
                "use_cases": ["Transform user intent"],
            },
        }

        # Should load without errors
        item_type = NotebookItemType(**type_json_data)

        assert item_type.id == "planner-cell"
        assert item_type.discovery is not None
        assert item_type.discovery.labels[0] == "#planning"

    def test_backward_compatibility_old_type_json(self):
        """Test that old type.json files (without discovery) still work"""
        old_type_json_data = {
            "id": "example",
            "name": "Example Cell",
            "description": "Reference implementation",
            "version": "1.0.0",
            "category": "reference",
            "default_refs": {
                "scripts": ["backend/scripts/main.py"],
            },
            "default_initial_data": {
                "message": "Hello",
            },
            "allow_instance_override_refs": True,
            # No discovery field
        }

        # Should load without errors
        item_type = NotebookItemType(**old_type_json_data)

        assert item_type.id == "example"
        assert item_type.discovery is None  # Should be None, not error


class TestDiscoveryMetadataEdgeCases:
    """Test edge cases for DiscoveryMetadata"""

    def testdiscovery_with_empty_lists(self):
        """Test DiscoveryMetadata with empty lists"""
        metadata = DiscoveryMetadata(
            describe="Test cell",
            labels=[],
            required_resources=[],
            dependencies=[],
            tags=[],
            use_cases=[],
        )

        assert metadata.labels == []
        assert metadata.required_resources == []

    def testdiscovery_with_long_describe(self):
        """Test DiscoveryMetadata with long description"""
        long_text = "A" * 5000  # 5000 character description
        metadata = DiscoveryMetadata(describe=long_text)

        assert len(metadata.describe) == 5000

    def testdiscovery_with_special_characters_in_labels(self):
        """Test labels with special characters"""
        metadata = DiscoveryMetadata(
            describe="Test",
            labels=["#3d-mesh", "#ai/ml", "#web_api", "#real-time"],
        )

        assert len(metadata.labels) == 4
        assert metadata.labels[0] == "#3d-mesh"

    def testdiscovery_duration_edge_cases(self):
        """Test duration with various values"""
        # Zero duration
        metadata1 = DiscoveryMetadata(
            describe="Instant cell", estimated_duration_seconds=0
        )
        assert metadata1.estimated_duration_seconds == 0

        # Very long duration
        metadata2 = DiscoveryMetadata(
            describe="Long running cell", estimated_duration_seconds=3600
        )
        assert metadata2.estimated_duration_seconds == 3600

        # Negative duration (should be handled by validation if needed)
        metadata3 = DiscoveryMetadata(
            describe="Test", estimated_duration_seconds=-10
        )
        assert metadata3.estimated_duration_seconds == -10
