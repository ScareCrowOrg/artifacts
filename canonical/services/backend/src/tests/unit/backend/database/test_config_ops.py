"""
Unit tests for app/database/config_ops.py

Tests configuration get/set operations for JSONDatabase.
Tests both successful operations and error handling.
"""

import pytest
import json
from pathlib import Path


class TestGetConfig:
    """Test configuration retrieval operations."""
    
    def test_get_config_existing(self, test_db):
        """Test getting an existing configuration."""
        # Create config file directly
        config_dir = test_db.base_path / "config"
        config_file = config_dir / "test_config.json"
        
        test_data = {
            "setting1": "value1",
            "setting2": 42,
            "nested": {"key": "value"}
        }
        
        with open(config_file, 'w') as f:
            json.dump(test_data, f)
        
        # Get config
        config = test_db.get_config("test_config")
        
        assert config is not None
        assert config["setting1"] == "value1"
        assert config["setting2"] == 42
        assert config["nested"]["key"] == "value"
    
    def test_get_config_nonexistent(self, test_db):
        """Test getting non-existent configuration returns None."""
        config = test_db.get_config("nonexistent_config")
        
        assert config is None
    
    def test_get_config_with_special_characters(self, test_db):
        """Test getting config with special characters in key."""
        # Save config with underscores (common pattern)
        test_data = {"enabled": True, "api_key": "test"}
        test_db.set_config("oauth_settings", test_data)
        
        # Retrieve
        config = test_db.get_config("oauth_settings")
        
        assert config is not None
        assert config["enabled"] is True
    
    def test_get_config_with_complex_data(self, test_db):
        """Test getting config with complex nested data."""
        complex_data = {
            "providers": [
                {"name": "provider1", "enabled": True},
                {"name": "provider2", "enabled": False}
            ],
            "settings": {
                "timeout": 30,
                "retries": 3,
                "advanced": {
                    "debug": True,
                    "log_level": "INFO"
                }
            }
        }
        
        # Save
        test_db.set_config("complex_config", complex_data)
        
        # Retrieve
        config = test_db.get_config("complex_config")
        
        assert config is not None
        assert len(config["providers"]) == 2
        assert config["settings"]["advanced"]["debug"] is True
    
    def test_get_config_corrupted_file_returns_none(self, test_db):
        """Test that corrupted config file returns None and logs error."""
        # Create invalid JSON file
        config_dir = test_db.base_path / "config"
        config_file = config_dir / "corrupted.json"
        
        with open(config_file, 'w') as f:
            f.write("{ invalid json }")
        
        # Should return None and log error
        config = test_db.get_config("corrupted")
        
        assert config is None


class TestSetConfig:
    """Test configuration save operations."""
    
    def test_set_config_new(self, test_db):
        """Test saving a new configuration."""
        config_data = {
            "key1": "value1",
            "key2": 123,
            "key3": True
        }
        
        success = test_db.set_config("new_config", config_data)
        
        assert success is True
        
        # Verify file was created
        config_file = test_db.base_path / "config" / "new_config.json"
        assert config_file.exists()
        
        # Verify content
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data == config_data
    
    def test_set_config_overwrite_existing(self, test_db):
        """Test overwriting existing configuration."""
        # Save initial config
        initial_data = {"version": 1, "setting": "old"}
        test_db.set_config("overwrite_test", initial_data)
        
        # Overwrite with new data
        new_data = {"version": 2, "setting": "new", "extra": "field"}
        success = test_db.set_config("overwrite_test", new_data)
        
        assert success is True
        
        # Verify new data
        config = test_db.get_config("overwrite_test")
        assert config["version"] == 2
        assert config["setting"] == "new"
        assert config["extra"] == "field"
    
    def test_set_config_creates_config_directory(self, test_db):
        """Test that set_config creates config directory if it doesn't exist."""
        # Remove config directory
        import shutil
        config_dir = test_db.base_path / "config"
        if config_dir.exists():
            shutil.rmtree(config_dir)
        
        assert not config_dir.exists()
        
        # Save config
        success = test_db.set_config("test", {"data": "value"})
        
        assert success is True
        assert config_dir.exists()
    
    def test_set_config_with_nested_dict(self, test_db):
        """Test saving configuration with nested dictionaries."""
        nested_config = {
            "level1": {
                "level2": {
                    "level3": {
                        "deep_value": "found"
                    }
                }
            }
        }
        
        success = test_db.set_config("nested", nested_config)
        
        assert success is True
        
        # Verify
        retrieved = test_db.get_config("nested")
        assert retrieved["level1"]["level2"]["level3"]["deep_value"] == "found"
    
    def test_set_config_with_lists(self, test_db):
        """Test saving configuration with list values."""
        list_config = {
            "items": ["item1", "item2", "item3"],
            "numbers": [1, 2, 3, 4, 5],
            "mixed": [1, "two", 3.0, True, None]
        }
        
        success = test_db.set_config("list_config", list_config)
        
        assert success is True
        
        # Verify
        retrieved = test_db.get_config("list_config")
        assert retrieved["items"] == ["item1", "item2", "item3"]
        assert retrieved["numbers"] == [1, 2, 3, 4, 5]
        assert retrieved["mixed"] == [1, "two", 3.0, True, None]
    
    def test_set_config_empty_dict(self, test_db):
        """Test saving empty configuration."""
        success = test_db.set_config("empty", {})
        
        assert success is True
        
        # Verify
        retrieved = test_db.get_config("empty")
        assert retrieved == {}
    
    def test_set_config_with_unicode(self, test_db):
        """Test saving configuration with Unicode characters."""
        unicode_config = {
            "português": "Configuração em português",
            "emoji": "🔧 ⚙️ 🛠️",
            "chinese": "中文配置",
            "special": "Spëçiål Çhârāçtêrs"
        }
        
        success = test_db.set_config("unicode", unicode_config)
        
        assert success is True
        
        # Verify
        retrieved = test_db.get_config("unicode")
        assert retrieved["português"] == "Configuração em português"
        assert retrieved["emoji"] == "🔧 ⚙️ 🛠️"
        assert retrieved["chinese"] == "中文配置"


class TestConfigRoundTrip:
    """Test configuration save and load round trips."""
    
    def test_oauth_config_scenario(self, test_db):
        """Test realistic OAuth configuration scenario."""
        oauth_config = {
            "google_client_id": "test_client_id",
            "google_client_secret": "test_secret",
            "enabled": True,
            "redirect_uri": "http://localhost:8080/auth/callback",
            "scopes": ["email", "profile"]
        }
        
        # Save
        test_db.set_config("oauth", oauth_config)
        
        # Load
        loaded = test_db.get_config("oauth")
        
        assert loaded == oauth_config
        assert loaded["enabled"] is True
        assert len(loaded["scopes"]) == 2
    
    def test_llm_provider_config_scenario(self, test_db):
        """Test realistic LLM provider configuration scenario."""
        provider_config = {
            "providers": {
                "openai": {
                    "enabled": True,
                    "model": "gpt-4",
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                "gemini": {
                    "enabled": False,
                    "model": "gemini-pro"
                }
            },
            "default_provider": "openai"
        }
        
        # Save
        test_db.set_config("llm_providers", provider_config)
        
        # Load
        loaded = test_db.get_config("llm_providers")
        
        assert loaded["default_provider"] == "openai"
        assert loaded["providers"]["openai"]["temperature"] == 0.7
        assert loaded["providers"]["gemini"]["enabled"] is False
    
    def test_multiple_configs_independent(self, test_db):
        """Test that multiple configurations are independent."""
        config1 = {"setting": "value1"}
        config2 = {"setting": "value2"}
        
        test_db.set_config("config1", config1)
        test_db.set_config("config2", config2)
        
        # Verify independence
        loaded1 = test_db.get_config("config1")
        loaded2 = test_db.get_config("config2")
        
        assert loaded1["setting"] == "value1"
        assert loaded2["setting"] == "value2"
    
    def test_config_update_preserves_formatting(self, test_db):
        """Test that saved config has proper JSON formatting."""
        config = {"key": "value", "number": 42}
        test_db.set_config("formatted", config)
        
        # Read raw file
        config_file = test_db.base_path / "config" / "formatted.json"
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Should be indented (pretty-printed)
        assert "\n" in content
        assert "  " in content or "\t" in content  # Has indentation
