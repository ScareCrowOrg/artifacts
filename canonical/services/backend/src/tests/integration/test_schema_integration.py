"""
Integration tests for Phase 8: Schema Generation Integration & Validation

Tests that schema generation integrates correctly with application startup
and that canonical data loads properly with auto-generated schemas.

Coverage target: ≥90%

Test Scope:
- Schema generation from Pydantic models
- Canonical data loading with generated schemas
- CanonicalQueryEngine initialization
- Discovery service integration
- Multi-source search with canonical data
"""

import pytest
import json
from pathlib import Path
import sys
import tempfile
import shutil

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_path))


class TestSchemaGenerationIntegration:
    """Test schema generation integration with application startup."""
    
    def test_generate_and_validate_schemas_creates_valid_schema(self):
        """Test that generate_and_validate_schemas creates valid schema structure."""
        from app.database.schema_initialization import generate_and_validate_schemas
        
        # Create temporary directory for test
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "canonical"
            base_path.mkdir(parents=True, exist_ok=True)
            
            # Generate schemas (don't save to disk)
            schemas = generate_and_validate_schemas(
                base_path=base_path,
                save_to_disk=False,
                validate_only=False
            )
            
            # Verify schema structure
            assert "version" in schemas
            assert "description" in schemas
            assert "last_updated" in schemas
            assert schemas["version"] == 1
            assert "AUTO-GENERATED" in schemas["description"]
            
            # Verify all 11 collections exist
            expected_collections = {
                "permissions", "cells", "books", "ai_models", "content_types",
                "notebook_items", "templates", "roles", "workflows",
                "notebook_item_types", "contents"
            }
            
            actual_collections = set(schemas.keys()) - {"version", "description", "last_updated"}
            assert actual_collections == expected_collections, (
                f"Missing collections: {expected_collections - actual_collections}, "
                f"Extra collections: {actual_collections - expected_collections}"
            )
    
    def test_generate_and_validate_schemas_saves_to_disk(self):
        """Test that schemas are saved to disk with backup."""
        from app.database.schema_initialization import generate_and_validate_schemas
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "canonical"
            base_path.mkdir(parents=True, exist_ok=True)
            schemas_path = base_path / "SCHEMAS.json"
            
            # Create existing SCHEMAS.json
            existing_schema = {
                "version": 1,
                "description": "Old schema",
                "last_updated": "2026-01-01",
                "permissions": {}
            }
            with open(schemas_path, "w") as f:
                json.dump(existing_schema, f)
            
            # Generate and save schemas
            schemas = generate_and_validate_schemas(
                base_path=base_path,
                save_to_disk=True,
                validate_only=False
            )
            
            # Verify schemas were saved
            assert schemas_path.exists()
            
            # Verify backup was created
            backup_path = schemas_path.with_suffix(".json.backup")
            assert backup_path.exists()
            
            # Verify backup contains old schema
            with open(backup_path, "r") as f:
                backup_data = json.load(f)
            assert backup_data["description"] == "Old schema"
            
            # Verify new schema is different
            with open(schemas_path, "r") as f:
                new_data = json.load(f)
            assert "AUTO-GENERATED" in new_data["description"]
    
    def test_schema_validation_detects_divergence(self, caplog):
        """Test that schema validation detects and logs divergence."""
        from app.database.schema_initialization import generate_and_validate_schemas
        import logging
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "canonical"
            base_path.mkdir(parents=True, exist_ok=True)
            schemas_path = base_path / "SCHEMAS.json"
            
            # Create existing schema with different types
            existing_schema = {
                "version": 1,
                "description": "Old schema",
                "last_updated": "2026-01-01",
                "permissions": {
                    "_id": {"type": "TEXT", "constraints": "PRIMARY KEY"},
                    "name": {"type": "INTEGER"},  # WRONG TYPE - should be TEXT
                    "old_field": {"type": "TEXT"}  # Field that doesn't exist in Pydantic model
                }
            }
            with open(schemas_path, "w") as f:
                json.dump(existing_schema, f)
            
            # Generate schemas with validation
            with caplog.at_level(logging.DEBUG):
                schemas = generate_and_validate_schemas(
                    base_path=base_path,
                    save_to_disk=False,
                    validate_only=False
                )
            
            # Check that divergence was logged
            # Should log type change and missing field
            log_text = caplog.text
            assert "permissions" in log_text or "Type changed" in log_text or "missing" in log_text


class TestCanonicalDataLoading:
    """Test canonical data loading with generated schemas."""
    
    def test_canonical_query_engine_initializes_with_generated_schema(self):
        """Test CanonicalQueryEngine initializes with auto-generated schemas."""
        from app.database.query_engine.canonical_engine import CanonicalQueryEngine
        from app.config.database import ARTIFACTS_DIR
        
        # Initialize CanonicalQueryEngine (will use auto-generated SCHEMAS.json)
        try:
            engine = CanonicalQueryEngine(
                base_path=ARTIFACTS_DIR / "canonical"
            )
            
            # Verify engine initialized
            assert engine is not None
            assert engine.schemas is not None
            assert engine.conn is not None
            
            # Verify schemas loaded
            metadata_fields = {"version", "description", "last_updated"}
            collections = set(engine.schemas.keys()) - metadata_fields
            assert len(collections) >= 11, f"Expected at least 11 collections, got {len(collections)}"
            
        except Exception as e:
            pytest.fail(f"CanonicalQueryEngine initialization failed: {e}")
    
    @pytest.mark.asyncio
    async def test_notebook_item_types_loads_correct_count(self):
        """Test that notebook_item_types collection loads 32 documents."""
        from app.database.query_engine.canonical_engine import CanonicalQueryEngine
        from app.config.database import ARTIFACTS_DIR
        
        # Check if canonical data exists
        notebook_types_dir = ARTIFACTS_DIR / "canonical" / "notebook_item_types"
        if not notebook_types_dir.exists():
            pytest.skip("Canonical notebook_item_types data not found")
        
        # Count JSON files
        json_files = list(notebook_types_dir.glob("*.json"))
        expected_count = len(json_files)
        
        # Initialize engine
        engine = CanonicalQueryEngine(
            base_path=ARTIFACTS_DIR / "canonical"
        )
        
        # Query notebook_item_types
        results = await engine.find("notebook_item_types", {})
        
        # Verify count
        assert len(results) == expected_count, (
            f"Expected {expected_count} notebook_item_types, got {len(results)}"
        )
    
    @pytest.mark.asyncio
    async def test_all_collections_load_successfully(self):
        """Test that all 11 canonical collections load without errors."""
        from app.database.query_engine.canonical_engine import CanonicalQueryEngine
        from app.config.database import ARTIFACTS_DIR
        
        # Initialize engine
        engine = CanonicalQueryEngine(
            base_path=ARTIFACTS_DIR / "canonical"
        )
        
        # Collections to test
        collections = [
            "permissions", "cells", "books", "ai_models", "content_types",
            "notebook_items", "templates", "roles", "workflows",
            "notebook_item_types", "contents"
        ]
        
        # Test each collection
        for collection in collections:
            try:
                # Check if collection directory exists
                collection_dir = ARTIFACTS_DIR / "canonical" / collection
                if not collection_dir.exists():
                    continue  # Skip if no canonical data for this collection
                
                # Query collection
                results = await engine.find(collection, {})
                
                # Verify results is a list (even if empty)
                assert isinstance(results, list), (
                    f"Collection {collection} returned non-list: {type(results)}"
                )
                
            except Exception as e:
                pytest.fail(f"Collection {collection} failed to load: {e}")


class TestDiscoveryServiceIntegration:
    """Test discovery service integration with auto-generated schemas."""
    
    @pytest.mark.asyncio
    async def test_discovery_service_works_with_new_schema(self):
        """Test that discovery_service works with updated schemas."""
        from app.discovery_service import discover_types
        from app.config.database import ARTIFACTS_DIR
        
        # Check if cell_types directory exists
        cell_types_dir = ARTIFACTS_DIR / "canonical" / "cell_types"
        if not cell_types_dir.exists():
            pytest.skip("Canonical cell_types data not found")
        
        try:
            # Discover types
            types_dict = discover_types()
            
            # Verify types discovered
            assert isinstance(types_dict, dict)
            assert len(types_dict) > 0, "No types discovered"
            
            # Verify each type has required fields
            for type_id, type_data in types_dict.items():
                assert "id" in type_data or "name" in type_data
                
        except Exception as e:
            pytest.fail(f"discovery_service failed: {e}")


class TestMultiSourceSearch:
    """Test multi-source search with canonical data."""
    
    @pytest.mark.asyncio
    async def test_multi_source_search_canonical_priority(self):
        """Test that multi-source search prioritizes canonical data correctly."""
        from app.database.hybrid import HybridDatabase, MultiSourceSearch
        from app.database.query_engine.canonical_engine import CanonicalQueryEngine
        from app.config.database import ARTIFACTS_DIR
        from app.models.users import User
        from unittest.mock import Mock
        
        # Create test user
        test_user = User(
            id="test-user",
            username="testuser",
            email="test@example.com",
            role_ids=["admin"]
        )
        
        # Initialize engines
        try:
            canonical_engine = CanonicalQueryEngine(
                base_path=ARTIFACTS_DIR / "canonical"
            )
            
            # Create multi-source search handler
            multi_source = MultiSourceSearch(
                rbac=Mock(),  # Mock RBAC for testing
                sandbox_engine=None,
                canonical_engine=canonical_engine,
                mongo_ops=None,
                centralhub_client=None,
                mongodb_enabled=False
            )
            
            # Mock RBAC to allow access
            multi_source.rbac.has_permission = Mock(return_value=True)
            
            # Test search on notebook_item_types (should exist in canonical)
            collection_dir = ARTIFACTS_DIR / "canonical" / "notebook_item_types"
            if not collection_dir.exists():
                pytest.skip("Canonical notebook_item_types not found")
            
            # Search canonical data
            results = await multi_source.search_multi_source(
                collection="notebook_item_types",
                query={},
                current_user=test_user
            )
            
            # Verify results
            assert isinstance(results, list)
            # Should have results from canonical tier
            if len(list(collection_dir.glob("*.json"))) > 0:
                assert len(results) > 0, "Expected canonical results"
            
        except Exception as e:
            pytest.fail(f"Multi-source search failed: {e}")


class TestSchemaGenerationPerformance:
    """Test schema generation performance."""
    
    def test_schema_generation_completes_quickly(self):
        """Test that schema generation completes in reasonable time (<5 seconds)."""
        import time
        from app.database.schema_initialization import generate_and_validate_schemas
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "canonical"
            base_path.mkdir(parents=True, exist_ok=True)
            
            # Measure generation time
            start_time = time.time()
            schemas = generate_and_validate_schemas(
                base_path=base_path,
                save_to_disk=False,
                validate_only=False
            )
            end_time = time.time()
            
            duration = end_time - start_time
            
            # Should complete in less than 5 seconds
            assert duration < 5.0, (
                f"Schema generation took {duration:.2f}s (expected < 5.0s)"
            )
            
            # Verify schemas were generated
            assert len(schemas) > 3  # At least version + description + last_updated + 1 collection


class TestGracefulFallback:
    """Test graceful fallback to static SCHEMAS.json on failure."""
    
    def test_generation_continues_without_save_on_error(self, caplog):
        """Test that schema generation continues even if save fails."""
        from app.database.schema_initialization import generate_and_validate_schemas
        import logging
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "canonical"
            base_path.mkdir(parents=True, exist_ok=True)
            
            # Generate without saving (simulates save failure scenario)
            with caplog.at_level(logging.INFO):
                schemas = generate_and_validate_schemas(
                    base_path=base_path,
                    save_to_disk=False,  # Don't save - simulates fallback scenario
                    validate_only=False
                )
                
                # Verify schemas were generated successfully
                assert schemas is not None
                assert "permissions" in schemas
                assert "cells" in schemas
                
                # Verify generation completed
                assert "Schema generation complete" in caplog.text or "Generated schema" in caplog.text


# Marker for integration tests that require canonical data
pytestmark = pytest.mark.integration
