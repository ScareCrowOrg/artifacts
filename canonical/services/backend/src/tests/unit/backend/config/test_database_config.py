"""
Unit tests for database configuration module.

Tests MongoDB and Redis configuration loading from environment variables,
URI building, and validation logic.
"""

import os
import pytest
from pathlib import Path
import importlib


@pytest.fixture
def reload_database_config(monkeypatch):
    """
    Fixture to reload database config module with new environment variables.
    
    Returns a function that accepts env var dict and reloads the module.
    Usage:
        reload_database_config({"MONGODB_HOST": "testhost"})
    """
    def _reload(env_vars: dict):
        # Set all provided environment variables
        for key, value in env_vars.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, str(value))
        
        # Reload module to pick up new env vars
        from app.config import database
        importlib.reload(database)
        return database
    
    return _reload


def test_mongodb_uri_with_credentials(reload_database_config):
    """Test MongoDB URI construction with username and password."""
    database = reload_database_config({
        "MONGODB_HOST": "mongodb.example.com",
        "MONGODB_PORT": "27017",
        "MONGODB_DATABASE": "testdb",
        "MONGODB_USERNAME": "testuser",
        "MONGODB_PASSWORD": "testpass",
        "MONGODB_ENABLED": "true"
    })
    
    uri = database.get_mongodb_uri()
    
    # URI should include authSource parameter pointing to the database where user was created
    assert uri == "mongodb://testuser:testpass@mongodb.example.com:27017/testdb?authSource=testdb"
    assert database.MONGODB_USERNAME == "testuser"
    assert database.MONGODB_PASSWORD == "testpass"
    assert database.MONGODB_HOST == "mongodb.example.com"
    assert database.MONGODB_PORT == 27017
    assert database.MONGODB_DATABASE == "testdb"
    assert database.MONGODB_ENABLED is True


def test_mongodb_uri_without_credentials(reload_database_config):
    """Test MongoDB URI construction without authentication."""
    database = reload_database_config({
        "MONGODB_HOST": "localhost",
        "MONGODB_PORT": "27017",
        "MONGODB_DATABASE": "scareverse",
        "MONGODB_USERNAME": None,
        "MONGODB_PASSWORD": None
    })
    
    uri = database.get_mongodb_uri()
    
    assert uri == "mongodb://localhost:27017/scareverse"
    assert database.MONGODB_USERNAME is None
    assert database.MONGODB_PASSWORD is None


def test_mongodb_config_dict(reload_database_config):
    """Test MongoDB configuration dictionary construction."""
    database = reload_database_config({
        "MONGODB_HOST": "testhost",
        "MONGODB_PORT": "27018",
        "MONGODB_DATABASE": "testdb",
        "MONGODB_USERNAME": "user",
        "MONGODB_PASSWORD": "pass",
        "MONGODB_ENABLED": "true"
    })
    
    config = database.MONGODB_CONFIG
    
    assert config["host"] == "testhost"
    assert config["port"] == 27018
    assert config["database"] == "testdb"
    assert config["username"] == "user"
    assert config["password"] == "pass"
    assert config["enabled"] is True


def test_mongodb_enabled_flag(reload_database_config):
    """Test MONGODB_ENABLED flag parsing."""
    # Test true values
    for value in ["true", "True", "TRUE"]:
        database = reload_database_config({"MONGODB_ENABLED": value})
        assert database.MONGODB_ENABLED is True
    
    # Test false values
    for value in ["false", "False", "FALSE", "0", ""]:
        database = reload_database_config({"MONGODB_ENABLED": value})
        assert database.MONGODB_ENABLED is False


def test_mongodb_validation_success(reload_database_config):
    """Test MongoDB configuration validation with valid settings."""
    database = reload_database_config({
        "MONGODB_ENABLED": "true",
        "MONGODB_HOST": "localhost",
        "MONGODB_PORT": "27017",
        "MONGODB_DATABASE": "scareverse"
    })
    
    # Should not raise
    assert database.validate_mongodb_config() is True


def test_mongodb_validation_disabled(reload_database_config):
    """Test MongoDB validation passes when disabled."""
    database = reload_database_config({"MONGODB_ENABLED": "false"})
    
    # Should not raise even with missing config
    assert database.validate_mongodb_config() is True


def test_mongodb_validation_missing_host(reload_database_config):
    """Test MongoDB validation fails with missing host."""
    database = reload_database_config({
        "MONGODB_ENABLED": "true",
        "MONGODB_HOST": "",  # Empty string instead of None
        "MONGODB_PORT": "27017",
        "MONGODB_DATABASE": "scareverse"
    })
    
    with pytest.raises(ValueError, match="MONGODB_HOST is required"):
        database.validate_mongodb_config()


def test_mongodb_validation_missing_database(reload_database_config):
    """Test MongoDB validation fails with missing database."""
    database = reload_database_config({
        "MONGODB_ENABLED": "true",
        "MONGODB_HOST": "localhost",
        "MONGODB_PORT": "27017",
        "MONGODB_DATABASE": ""  # Empty string instead of None
    })
    
    with pytest.raises(ValueError, match="MONGODB_DATABASE is required"):
        database.validate_mongodb_config()


def test_mongodb_validation_invalid_port(reload_database_config):
    """Test MongoDB validation fails with invalid port."""
    database = reload_database_config({
        "MONGODB_ENABLED": "true",
        "MONGODB_HOST": "localhost",
        "MONGODB_PORT": "99999",  # Invalid port
        "MONGODB_DATABASE": "scareverse"
    })
    
    with pytest.raises(ValueError, match="Invalid MONGODB_PORT"):
        database.validate_mongodb_config()


def test_redis_config(reload_database_config):
    """Test Redis L1 configuration loading."""
    database = reload_database_config({
        "REDIS_L1_HOST": "redis.example.com",
        "REDIS_L1_PORT": "6380",
        "REDIS_L1_DB": "1",
        "REDIS_L1_PASSWORD": "redispass",
        "REDIS_L1_ENABLED": "true"
    })
    
    assert database.REDIS_L1_HOST == "redis.example.com"
    assert database.REDIS_L1_PORT == 6380
    assert database.REDIS_L1_DB == 1
    assert database.REDIS_L1_PASSWORD == "redispass"
    assert database.REDIS_L1_ENABLED is True


def test_base_dir_configuration(monkeypatch):
    """Test BASE_DIR is properly configured."""
    from app.config import database
    
    assert isinstance(database.BASE_DIR, Path)
    assert database.BASE_DIR.exists()
    
    # Verify path structure
    assert database.ARTIFACTS_DIR == database.BASE_DIR / "artifacts"
    assert database.CANONICAL_DIR == database.ARTIFACTS_DIR / "canonical"
    assert database.RUNTIME_DIR == database.ARTIFACTS_DIR / "runtime"


def test_collection_cache_ttls():
    """Test collection-specific cache TTL configuration."""
    from app.config.database import get_cache_ttl, COLLECTION_CACHE_TTLS
    
    # Test specific collections
    assert get_cache_ttl("cells") == COLLECTION_CACHE_TTLS["cells"]
    assert get_cache_ttl("books") == COLLECTION_CACHE_TTLS["books"]
    assert get_cache_ttl("config") == COLLECTION_CACHE_TTLS["config"]
    
    # Test canonical artifacts
    from app.config.database import REDIS_CACHE_TTL_CANONICAL
    assert get_cache_ttl("any_collection", is_canonical=True) == REDIS_CACHE_TTL_CANONICAL
    
    # Test default TTL for unknown collection
    from app.config.database import REDIS_CACHE_TTL
    assert get_cache_ttl("unknown_collection") == REDIS_CACHE_TTL


def test_canonical_and_runtime_collections():
    """Test canonical and runtime collection sets."""
    from app.config.database import CANONICAL_COLLECTIONS, RUNTIME_COLLECTIONS
    
    # Canonical collections
    assert "notebook_item_types" in CANONICAL_COLLECTIONS
    assert "workflows" in CANONICAL_COLLECTIONS
    assert "permissions" in CANONICAL_COLLECTIONS
    
    # Runtime collections
    assert "cells" in RUNTIME_COLLECTIONS
    assert "books" in RUNTIME_COLLECTIONS
    assert "users" in RUNTIME_COLLECTIONS
    assert "sessions" in RUNTIME_COLLECTIONS
    
    # Ensure no overlap
    assert len(CANONICAL_COLLECTIONS & RUNTIME_COLLECTIONS) == 0
