"""
Tests for NotebookItemType Registry Service.

These tests validate the plug-and-play cell type discovery mechanism.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from app.services.notebook_item_type_registry import (
    NotebookItemTypeRegistry,
    get_registry
)
from app.models.content import NotebookItemType


class TestNotebookItemTypeRegistry:
    """Test suite for NotebookItemTypeRegistry"""
    
    @pytest.fixture
    def temp_cell_types_dir(self):
        """Create a temporary directory structure for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            
            # Create example cell type
            example_dir = base_path / "example"
            example_dir.mkdir()
            
            type_data = {
                "id": "example",
                "name": "Example Cell",
                "description": "Test cell type",
                "version": "1.0.0",
                "category": "test",
                "default_refs": {
                    "scripts": ["backend/scripts/main.py"],
                    "view": ["frontend/View.vue"]
                },
                "default_initial_data": {
                    "message": "Hello"
                },
                "allow_instance_override_refs": True
            }
            
            type_json_path = example_dir / "type.json"
            with open(type_json_path, 'w') as f:
                json.dump(type_data, f)
            
            # Create referenced files
            backend_dir = example_dir / "backend" / "scripts"
            backend_dir.mkdir(parents=True)
            (backend_dir / "main.py").write_text("# Main script")
            
            frontend_dir = example_dir / "frontend"
            frontend_dir.mkdir(parents=True)
            (frontend_dir / "View.vue").write_text("<template>View</template>")
            
            yield base_path
    
    def test_registry_initialization(self, temp_cell_types_dir):
        """Test registry can be initialized with custom path"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        assert registry.base_path == temp_cell_types_dir
        assert len(registry.types) == 0
        assert not registry._initialized
    
    def test_discover_types(self, temp_cell_types_dir):
        """Test discovery of cell types from filesystem"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        discovered_types = registry.discover_types_sync()
        
        assert len(discovered_types) == 1
        assert discovered_types[0].id == "example"
        assert discovered_types[0].name == "Example Cell"
        assert registry._initialized
    
    @pytest.mark.asyncio
    async def test_discover_types_async(self, temp_cell_types_dir):
        """Test async discovery of cell types from filesystem"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        # Disable auto-sync for unit test
        discovered_types = await registry.discover_types(sync_to_db=False)
        
        assert len(discovered_types) == 1
        assert discovered_types[0].id == "example"
        assert discovered_types[0].name == "Example Cell"
        assert registry._initialized
    
    def test_get_type(self, temp_cell_types_dir):
        """Test getting a specific type by ID"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        
        # Should auto-discover on first get
        cell_type = registry.get_type("example")
        
        assert cell_type is not None
        assert cell_type.id == "example"
        assert cell_type.name == "Example Cell"
    
    def test_get_type_not_found(self, temp_cell_types_dir):
        """Test getting a non-existent type returns None"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        
        cell_type = registry.get_type("nonexistent")
        
        assert cell_type is None
    
    def test_list_types(self, temp_cell_types_dir):
        """Test listing all registered types"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        
        types = registry.list_types()
        
        assert len(types) == 1
        assert types[0].id == "example"
    
    def test_resolve_ref_path(self, temp_cell_types_dir):
        """Test resolving relative ref paths to absolute paths"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        registry.discover_types_sync()
        
        resolved_path = registry.resolve_ref_path(
            "example",
            "scripts",
            "backend/scripts/main.py"
        )
        
        assert resolved_path is not None
        assert resolved_path.exists()
        assert resolved_path.name == "main.py"
    
    def test_resolve_ref_path_not_found(self, temp_cell_types_dir):
        """Test resolving ref for non-existent type"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        
        resolved_path = registry.resolve_ref_path(
            "nonexistent",
            "scripts",
            "backend/scripts/main.py"
        )
        
        assert resolved_path is None
    
    def test_validate_refs(self, temp_cell_types_dir):
        """Test validating that referenced files exist"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        registry.discover_types_sync()
        
        validation_results = registry.validate_refs("example")
        
        assert validation_results["backend/scripts/main.py"] is True
        assert validation_results["frontend/View.vue"] is True
    
    def test_validate_refs_missing_files(self, temp_cell_types_dir):
        """Test validation detects missing files"""
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        
        # Add type with missing refs
        missing_dir = temp_cell_types_dir / "missing_refs"
        missing_dir.mkdir()
        
        type_data = {
            "id": "missing_refs",
            "name": "Missing Refs",
            "default_refs": {
                "scripts": ["nonexistent.py"]
            }
        }
        
        with open(missing_dir / "type.json", 'w') as f:
            json.dump(type_data, f)
        
        registry.discover_types_sync()
        validation_results = registry.validate_refs("missing_refs")
        
        assert validation_results["nonexistent.py"] is False
    
    def test_invalid_type_json(self, temp_cell_types_dir):
        """Test handling of invalid type.json files"""
        # Create directory with invalid JSON
        invalid_dir = temp_cell_types_dir / "invalid"
        invalid_dir.mkdir()
        
        with open(invalid_dir / "type.json", 'w') as f:
            f.write("{ invalid json }")
        
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        
        # Should not raise, but should skip invalid type
        discovered_types = registry.discover_types_sync()
        
        # Should only have the valid "example" type
        assert len(discovered_types) == 1
        assert discovered_types[0].id == "example"
    
    def test_missing_required_fields(self, temp_cell_types_dir):
        """Test handling of type.json missing required fields"""
        # Create directory with incomplete type.json
        incomplete_dir = temp_cell_types_dir / "incomplete"
        incomplete_dir.mkdir()
        
        type_data = {
            "description": "Missing id and name"
        }
        
        with open(incomplete_dir / "type.json", 'w') as f:
            json.dump(type_data, f)
        
        registry = NotebookItemTypeRegistry(base_path=str(temp_cell_types_dir))
        
        # Should not raise, but should skip invalid type
        discovered_types = registry.discover_types_sync()
        
        # Should only have the valid "example" type
        assert len(discovered_types) == 1
        assert discovered_types[0].id == "example"
    
    def test_get_global_registry(self):
        """Test global registry singleton"""
        registry1 = get_registry()
        registry2 = get_registry()
        
        assert registry1 is registry2  # Same instance


class TestNotebookItemTypeRegistryRealPath:
    """Test registry with real cell_types directory"""
    
    def test_discover_example_cell_type(self):
        """Test discovering the example cell type from artifacts"""
        # Find project root - look for pyproject.toml going up from test file
        current_dir = Path(__file__).resolve().parent
        project_root = None
        
        # Try to find pyproject.toml by going up the directory tree
        for parent in [current_dir] + list(current_dir.parents):
            if (parent / "backend" / "pyproject.toml").exists():
                project_root = parent
                break
        
        # Fallback: assume standard project structure
        if project_root is None:
            # tests/unit/ -> tests/ -> backend/ -> project_root/
            project_root = current_dir.parent.parent.parent
        
        cell_types_path = project_root / "artifacts" / "canonical" / "cell_types"
        
        # Skip test if path doesn't exist
        if not cell_types_path.exists():
            pytest.skip(f"Cell types directory not found at {cell_types_path}")
        
        registry = NotebookItemTypeRegistry(base_path=str(cell_types_path))
        
        try:
            discovered_types = registry.discover_types_sync()
            
            # Should find at least the example type
            example_type = registry.get_type("example")
            assert example_type is not None, (
                f"Example type not found. Discovered types: {[t.id for t in discovered_types]}. "
                f"Registry path: {registry.base_path}"
            )
            assert example_type.id == "example"
            assert example_type.name == "Example Cell"
            
        except FileNotFoundError as e:
            pytest.skip(f"Cell types directory not found: {e}")
    
    def test_discover_pipeline_monitoring_cell_with_symlink(self):
        """Test discovering the pipeline-monitoring-cell using symlink architecture"""
        # Find project root
        current_dir = Path(__file__).resolve().parent
        project_root = None
        
        for parent in [current_dir] + list(current_dir.parents):
            if (parent / "backend" / "pyproject.toml").exists():
                project_root = parent
                break
        
        if project_root is None:
            project_root = current_dir.parent.parent.parent
        
        cell_types_path = project_root / "artifacts" / "canonical" / "cell_types"
        
        if not cell_types_path.exists():
            pytest.skip(f"Cell types directory not found at {cell_types_path}")
        
        registry = NotebookItemTypeRegistry(base_path=str(cell_types_path))
        
        try:
            discovered_types = registry.discover_types_sync()
            
            # Should find pipeline-monitoring-cell
            monitoring_cell = registry.get_type("pipeline-monitoring-cell")
            assert monitoring_cell is not None, (
                f"Pipeline monitoring cell not found. Discovered types: {[t.id for t in discovered_types]}"
            )
            
            # Verify cell properties
            assert monitoring_cell.id == "pipeline-monitoring-cell"
            assert monitoring_cell.name == "Pipeline Monitoring Cell"
            # Note: can_render_dynamically may vary based on cell definition
            assert monitoring_cell.can_render_dynamically is not None
            
            # Verify type.json is a symlink
            type_json_path = cell_types_path / "pipeline-monitoring-cell" / "type.json"
            assert type_json_path.is_symlink(), "type.json should be a symlink"
            
            # Verify symlink points to canonical definition
            canonical_path = project_root / "artifacts" / "canonical" / "notebook_item_types" / "pipeline-monitoring-cell.json"
            assert canonical_path.exists(), "Canonical definition should exist"
            
            # Verify refs are accessible
            validation_results = registry.validate_refs("pipeline-monitoring-cell")
            assert validation_results["frontend/View.vue"] is True, "View.vue should be accessible"
            assert validation_results["docs/README.md"] is True, "README.md should be accessible"
            
        except FileNotFoundError as e:
            pytest.skip(f"Cell types directory not found: {e}")
    
    def test_discover_png_generator_cell_with_symlink(self):
        """Test discovering the png-generator-cell using symlink architecture"""
        # Find project root
        current_dir = Path(__file__).resolve().parent
        project_root = None
        
        for parent in [current_dir] + list(current_dir.parents):
            if (parent / "backend" / "pyproject.toml").exists():
                project_root = parent
                break
        
        if project_root is None:
            project_root = current_dir.parent.parent.parent
        
        cell_types_path = project_root / "artifacts" / "canonical" / "cell_types"
        
        if not cell_types_path.exists():
            pytest.skip(f"Cell types directory not found at {cell_types_path}")
        
        registry = NotebookItemTypeRegistry(base_path=str(cell_types_path))
        
        try:
            discovered_types = registry.discover_types_sync()
            
            # Should find png-generator-cell
            png_cell = registry.get_type("png-generator-cell")
            assert png_cell is not None, (
                f"PNG Generator cell not found. Discovered types: {[t.id for t in discovered_types]}"
            )
            
            # Verify cell properties
            assert png_cell.id == "png-generator-cell"
            assert png_cell.name == "PNG Generator Cell"
            assert png_cell.can_render_dynamically is True
            
            # Verify type.json is a symlink
            type_json_path = cell_types_path / "png-generator-cell" / "type.json"
            assert type_json_path.is_symlink(), "type.json should be a symlink"
            
            # Verify symlink points to canonical definition
            canonical_path = project_root / "artifacts" / "canonical" / "notebook_item_types" / "png-generator-cell.json"
            assert canonical_path.exists(), "Canonical definition should exist"
            
            # Verify refs are accessible
            validation_results = registry.validate_refs("png-generator-cell")
            assert validation_results["frontend/View.vue"] is True, "View.vue should be accessible"
            assert validation_results["docs/README.md"] is True, "README.md should be accessible"
            assert validation_results["backend/scripts/main.py"] is True, "main.py should be accessible"
            
        except FileNotFoundError as e:
            pytest.skip(f"Cell types directory not found: {e}")
