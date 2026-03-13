"""
Integration test for startup seed data initialization.

Tests that the backend properly initializes seed data (AI models,
notebook types, agents, etc.) during application startup.

Coverage target: ≥90%
"""

import pytest
from pathlib import Path
import sys
from unittest.mock import MagicMock, AsyncMock

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_path))

from app.models.ai_models import AIModel
from app.database import JSONDatabase


@pytest.fixture
def test_db():
    """Create a test database instance."""
    db = JSONDatabase(is_test_env=True)
    yield db
    db.cleanup_test_data()


@pytest.fixture
def mock_seed_db(test_db):
    """Mock db in seed_data module to use test database with async wrappers."""
    import app.scripts.seed_data as seed_module
    original_db = seed_module.db
    
    # Create a mock database that wraps test_db with AsyncMock for async methods
    # HybridDatabase has async methods, but test_db (JSONDatabase) has sync methods
    mock_db = MagicMock()
    
    # Wrap all database methods that are async in HybridDatabase
    async def async_find_one(collection, doc_id, model_class=None, is_canonical=False):
        return test_db.find_one(collection, doc_id, model_class, is_canonical=is_canonical)
    
    async def async_find_many(collection, model_class=None, is_canonical=False):
        return test_db.find_many(collection, model_class, is_canonical=is_canonical)
    
    async def async_find_by_field(collection, field, value, model_class, is_canonical=False):
        return test_db.find_by_field(collection, field, value, model_class, is_canonical=is_canonical)
    
    async def async_find_by_fields(collection, fields_dict, model_class, is_canonical=False):
        return test_db.find_by_fields(collection, fields_dict, model_class, is_canonical=is_canonical)
    
    async def async_insert(collection, data, is_canonical=False):
        return test_db.insert(collection, data, is_canonical=is_canonical)
    
    async def async_update(collection, doc_id, updates, is_canonical=False):
        return test_db.update(collection, doc_id, updates, is_canonical=is_canonical)
    
    async def async_delete(collection, doc_id, is_canonical=False):
        return test_db.delete(collection, doc_id, is_canonical=is_canonical)
    
    mock_db.find_one = AsyncMock(side_effect=async_find_one)
    mock_db.find_many = AsyncMock(side_effect=async_find_many)
    mock_db.find_by_field = AsyncMock(side_effect=async_find_by_field)
    mock_db.find_by_fields = AsyncMock(side_effect=async_find_by_fields)
    mock_db.insert = AsyncMock(side_effect=async_insert)
    mock_db.update = AsyncMock(side_effect=async_update)
    mock_db.delete = AsyncMock(side_effect=async_delete)
    
    seed_module.db = mock_db
    
    yield test_db
    
    # Restore original db
    seed_module.db = original_db


class TestStartupSeedData:
    """Test seed data initialization on startup."""
    
    @pytest.mark.asyncio
    async def test_seed_ai_models_creates_models(self, mock_seed_db):
        """Test that AI models are created during seed."""
        from app.scripts.seed_data import seed_ai_models
        
        # Run seed
        models = await seed_ai_models()
        
        # Should create at least one AI model
        assert len(models) > 0
        
        # Verify models exist in database
        db_models = mock_seed_db.find_many(
            "ai_models",
            AIModel,
            is_canonical=True
        )
        
        assert len(db_models) > 0
        
        # Verify at least one model is active
        active_models = [m for m in db_models if m.active]
        assert len(active_models) > 0
    
    @pytest.mark.asyncio
    async def test_init_seed_data_runs_successfully(self, mock_seed_db):
        """Test that init_seed_data runs without errors."""
        from app.scripts.seed_data import init_seed_data
        
        # Run init_seed_data
        result = await init_seed_data()
        
        # Should return a dict with counts
        assert isinstance(result, dict)
        assert "ai_models" in result
        assert "notebook_item_types" in result
        assert "agent_types" in result
        assert "agents" in result
        assert "books" in result
        
        # Should have created at least some data
        assert result["ai_models"] > 0
    
    @pytest.mark.asyncio
    async def test_ai_models_have_correct_structure(self, mock_seed_db):
        """Test that AI models have correct structure."""
        from app.scripts.seed_data import seed_ai_models
        
        # Run seed
        models = await seed_ai_models()
        
        if len(models) > 0:
            # Check first model has required fields
            model = models[0]
            assert hasattr(model, 'id')
            assert hasattr(model, 'name')
            assert hasattr(model, 'provider')
            assert hasattr(model, 'modelId')
            assert hasattr(model, 'active')
            
            # Verify ID is not empty
            assert model.id is not None
            assert len(model.id) > 0
