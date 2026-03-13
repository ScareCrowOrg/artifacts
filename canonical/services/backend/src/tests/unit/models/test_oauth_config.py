"""
Tests for OAuth configuration models.

Ensures OAuth configuration models validate correctly.
"""

import pytest
from pydantic import ValidationError

from app.models.oauth_config import OAuthConfiguration, UpdateOAuthConfigRequest


class TestOAuthConfiguration:
    """Tests for OAuthConfiguration model."""
    
    def test_create_empty_oauth_config(self):
        """Test creating OAuth config with no parameters."""
        config = OAuthConfiguration()
        
        assert config.googleClientId is None
        assert config.googleClientSecret is None
        assert config.authEnabled is False
    
    def test_create_oauth_config_with_credentials(self):
        """Test creating OAuth config with credentials."""
        config = OAuthConfiguration(
            googleClientId="test-client-id",
            googleClientSecret="test-client-secret",
            authEnabled=True
        )
        
        assert config.googleClientId == "test-client-id"
        assert config.googleClientSecret == "test-client-secret"
        assert config.authEnabled is True
    
    def test_create_oauth_config_with_partial_credentials(self):
        """Test creating OAuth config with only client ID."""
        config = OAuthConfiguration(
            googleClientId="test-client-id"
        )
        
        assert config.googleClientId == "test-client-id"
        assert config.googleClientSecret is None
        assert config.authEnabled is False
    
    def test_oauth_config_auth_enabled_default(self):
        """Test that authEnabled defaults to False."""
        config = OAuthConfiguration(
            googleClientId="test-client-id",
            googleClientSecret="test-secret"
        )
        
        assert config.authEnabled is False
    
    def test_oauth_config_serialization(self):
        """Test OAuth config can be serialized to dict."""
        config = OAuthConfiguration(
            googleClientId="test-id",
            googleClientSecret="test-secret",
            authEnabled=True
        )
        
        data = config.model_dump()
        
        assert data["googleClientId"] == "test-id"
        assert data["googleClientSecret"] == "test-secret"
        assert data["authEnabled"] is True


class TestUpdateOAuthConfigRequest:
    """Tests for UpdateOAuthConfigRequest model."""
    
    def test_create_empty_update_request(self):
        """Test creating update request with no parameters."""
        request = UpdateOAuthConfigRequest()
        
        assert request.googleClientId is None
        assert request.googleClientSecret is None
    
    def test_create_update_request_with_client_id_only(self):
        """Test updating only client ID."""
        request = UpdateOAuthConfigRequest(
            googleClientId="new-client-id"
        )
        
        assert request.googleClientId == "new-client-id"
        assert request.googleClientSecret is None
    
    def test_create_update_request_with_both_fields(self):
        """Test updating both fields."""
        request = UpdateOAuthConfigRequest(
            googleClientId="new-client-id",
            googleClientSecret="new-secret"
        )
        
        assert request.googleClientId == "new-client-id"
        assert request.googleClientSecret == "new-secret"
    
    def test_update_request_serialization(self):
        """Test update request serialization."""
        request = UpdateOAuthConfigRequest(
            googleClientId="update-id",
            googleClientSecret="update-secret"
        )
        
        data = request.model_dump()
        
        assert data["googleClientId"] == "update-id"
        assert data["googleClientSecret"] == "update-secret"
    
    def test_update_request_allows_none_values(self):
        """Test that None values are allowed for partial updates."""
        request = UpdateOAuthConfigRequest(
            googleClientId="id-only"
        )
        
        data = request.model_dump()
        assert data["googleClientId"] == "id-only"
        assert data["googleClientSecret"] is None
