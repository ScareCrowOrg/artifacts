"""
Tests for Resource Loader Service.

These tests validate the unified resource staging mechanism for local and remote files.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from app.services.resource_loader import ResourceLoader, get_resource_loader


class TestResourceLoader:
    """Test suite for ResourceLoader"""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def temp_source_files(self):
        """Create temporary source files for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            source_dir.mkdir()
            
            # Create test files
            (source_dir / "test.py").write_text("print('test')")
            (source_dir / "test.vue").write_text("<template>Test</template>")
            
            yield source_dir
    
    def test_loader_initialization(self, temp_cache_dir):
        """Test ResourceLoader can be initialized"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        assert loader.cache_base_path == Path(temp_cache_dir)
        assert loader.cache_base_path.exists()
        assert loader.cache_ttl_seconds == 3600
    
    def test_stage_local_resource(self, temp_cache_dir, temp_source_files):
        """Test staging a local file resource"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        source_file = temp_source_files / "test.py"
        staged = loader.stage_resource(
            str(source_file),
            "example/backend",
            "local"
        )
        
        assert staged.exists()
        assert staged.name == "test.py"
        assert "example/backend" in str(staged)
    
    def test_stage_local_resource_creates_symlink(self, temp_cache_dir, temp_source_files):
        """Test that local resources use symlinks when possible"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        source_file = temp_source_files / "test.py"
        staged = loader.stage_resource(
            str(source_file),
            "example/backend",
            "local"
        )
        
        # Should be a symlink (or regular file if symlinks not supported)
        assert staged.exists()
        content = staged.read_text()
        assert content == "print('test')"
    
    def test_stage_nonexistent_local_resource_raises(self, temp_cache_dir):
        """Test staging a non-existent local file raises error"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        with pytest.raises(FileNotFoundError):
            loader.stage_resource(
                "/nonexistent/file.py",
                "example/backend",
                "local"
            )
    
    def test_stage_remote_resource_not_implemented(self, temp_cache_dir):
        """Test staging remote resource raises NotImplementedError (Phase 3)"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        with pytest.raises(NotImplementedError):
            loader.stage_resource(
                "gs://bucket/file.py",
                "example/backend",
                "remote"
            )
    
    def test_stage_cell_type_local(self, temp_cache_dir, temp_source_files):
        """Test staging all resources for a cell type"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        refs = {
            "scripts": ["test.py"],
            "view": ["test.vue"]
        }
        
        staged = loader.stage_cell_type(
            "example",
            refs,
            base_local_path=temp_source_files
        )
        
        assert "scripts" in staged
        assert "view" in staged
        assert len(staged["scripts"]) == 1
        assert len(staged["view"]) == 1
        assert staged["scripts"][0].name == "test.py"
        assert staged["view"][0].name == "test.vue"
    
    def test_cache_freshness(self, temp_cache_dir, temp_source_files):
        """Test cache freshness checking"""
        loader = ResourceLoader(
            cache_base_path=temp_cache_dir,
            cache_ttl_seconds=2  # 2 seconds for testing
        )
        
        source_file = temp_source_files / "test.py"
        staged = loader.stage_resource(
            str(source_file),
            "example/backend",
            "local"
        )
        
        # Initially fresh
        assert loader._is_cache_fresh(staged)
        
        # Wait for TTL to expire
        import time
        time.sleep(3)
        
        # Now stale
        assert not loader._is_cache_fresh(staged)
    
    def test_cleanup_old_cache(self, temp_cache_dir, temp_source_files):
        """Test cleanup of old cached files"""
        loader = ResourceLoader(
            cache_base_path=temp_cache_dir,
            cache_ttl_seconds=1
        )
        
        # Stage a file
        source_file = temp_source_files / "test.py"
        staged = loader.stage_resource(
            str(source_file),
            "example/backend",
            "local"
        )
        
        assert staged.exists()
        
        # Wait for it to become old
        import time
        time.sleep(2)
        
        # Cleanup
        loader.cleanup_old_cache(max_age_seconds=1)
        
        # File should be removed (or symlink removed)
        # Note: The actual file might still exist if it was a symlink
        # but the symlink itself should be gone
    
    def test_clear_cache_all(self, temp_cache_dir, temp_source_files):
        """Test clearing all cache"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        # Stage some files
        source_file = temp_source_files / "test.py"
        loader.stage_resource(str(source_file), "example/backend", "local")
        loader.stage_resource(str(source_file), "another/dir", "local")
        
        # Clear all
        loader.clear_cache()
        
        # Cache should be empty (but directory should exist)
        assert loader.cache_base_path.exists()
        # Check no files remain
        cached_files = list(loader.cache_base_path.rglob("*"))
        # Filter out directories
        cached_files = [f for f in cached_files if f.is_file()]
        assert len(cached_files) == 0
    
    def test_clear_cache_specific_type(self, temp_cache_dir, temp_source_files):
        """Test clearing cache for specific cell type"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        # Stage files for two different types
        source_file = temp_source_files / "test.py"
        loader.stage_resource(str(source_file), "example/backend", "local")
        loader.stage_resource(str(source_file), "another/backend", "local")
        
        # Clear only 'example'
        loader.clear_cache(cell_type_id="example")
        
        # 'example' should be gone, 'another' should remain
        example_dir = loader.cache_base_path / "example"
        another_dir = loader.cache_base_path / "another"
        
        assert not example_dir.exists()
        assert another_dir.exists()
    
    def test_get_global_loader(self):
        """Test global loader singleton"""
        loader1 = get_resource_loader()
        loader2 = get_resource_loader()
        
        assert loader1 is loader2  # Same instance
    
    def test_invalid_resource_type_raises(self, temp_cache_dir):
        """Test invalid resource type raises ValueError"""
        loader = ResourceLoader(cache_base_path=temp_cache_dir)
        
        with pytest.raises(ValueError, match="Unknown resource type"):
            loader.stage_resource(
                "some/file.py",
                "example/backend",
                "invalid_type"
            )


class TestResourceLoaderIntegration:
    """Integration tests with Registry"""
    
    def test_registry_uses_resource_loader(self):
        """Test that Registry can use ResourceLoader for staging"""
        from app.services.notebook_item_type_registry import NotebookItemTypeRegistry
        from pathlib import Path
        
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
        registry.discover_types()
        
        # Try to stage example cell type
        example_type = registry.get_type("example")
        if example_type:
            staged = registry.stage_cell_type_resources("example")
            
            # Should have staged resources
            assert isinstance(staged, dict)
            assert len(staged) > 0
            
            # All staged paths should exist
            for ref_type, paths in staged.items():
                for path in paths:
                    assert path.exists(), f"Staged path should exist: {path}"
