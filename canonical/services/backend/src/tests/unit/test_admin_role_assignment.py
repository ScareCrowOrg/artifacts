"""
Unit tests for admin role assignment functionality.

Tests cover:
- get_initial_user_roles() function
- Admin role assignment during user creation
- Admin role assignment during OAuth login
- Migration of existing users

Technical naming: All functions and variables in English.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from app.auth import get_initial_user_roles
from app.models import User


class TestGetInitialUserRoles:
    """Tests for get_initial_user_roles helper function."""
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_admin_email_gets_admin_role(self):
        """Test that matching ADMIN_EMAIL gets admin role."""
        roles = get_initial_user_roles('admin@scareverse.com')
        assert roles == ['admin']
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_admin_email_case_insensitive(self):
        """Test that ADMIN_EMAIL comparison is case-insensitive."""
        roles = get_initial_user_roles('ADMIN@SCAREVERSE.COM')
        assert roles == ['admin']
        
        roles = get_initial_user_roles('AdMiN@ScArEvErSe.CoM')
        assert roles == ['admin']
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_non_admin_email_gets_user_role(self):
        """Test that non-matching email gets user role."""
        roles = get_initial_user_roles('user@example.com')
        assert roles == ['user']
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_empty_email_gets_user_role(self):
        """Test that empty email gets user role."""
        roles = get_initial_user_roles('')
        assert roles == ['user']
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_different_domain_gets_user_role(self):
        """Test that admin email with different domain gets user role."""
        roles = get_initial_user_roles('admin@different.com')
        assert roles == ['user']
    
    @patch('app.auth.ADMIN_EMAIL', None)
    def test_none_admin_email_returns_user_role(self):
        """Test that None ADMIN_EMAIL defaults to user role."""
        roles = get_initial_user_roles('any@example.com')
        assert roles == ['user']
    
    @patch('app.auth.ADMIN_EMAIL', '')
    def test_empty_admin_email_returns_user_role(self):
        """Test that empty ADMIN_EMAIL defaults to user role."""
        roles = get_initial_user_roles('any@example.com')
        assert roles == ['user']
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_none_email_input_returns_user_role(self):
        """Test that None email input returns user role."""
        roles = get_initial_user_roles(None)
        assert roles == ['user']
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_empty_string_email_input_returns_user_role(self):
        """Test that empty string email input returns user role."""
        roles = get_initial_user_roles('')
        assert roles == ['user']


class TestUserCreationWithRoles:
    """Tests for user creation with proper role assignment."""
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_user_model_with_admin_email(self):
        """Test creating User with admin email assigns admin role."""
        roles = get_initial_user_roles('admin@scareverse.com')
        user = User(
            name='Admin User',
            email='admin@scareverse.com',
            roles=roles
        )
        
        assert 'admin' in user.roles
        assert len(user.roles) == 1
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_user_model_with_regular_email(self):
        """Test creating User with regular email assigns user role."""
        roles = get_initial_user_roles('user@example.com')
        user = User(
            name='Regular User',
            email='user@example.com',
            roles=roles
        )
        
        assert 'user' in user.roles
        assert len(user.roles) == 1
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_user_default_role_without_explicit_assignment(self):
        """Test that User model has default user role."""
        user = User(
            name='Default User',
            email='default@example.com'
        )
        
        # Default should be ['user'] as per model definition
        assert 'user' in user.roles


class TestOAuthAdminRoleAssignment:
    """Tests for admin role assignment during OAuth flow."""
    
    @pytest.fixture(autouse=True)
    def cleanup_overrides(self):
        """Clean up app dependency overrides after each test."""
        from app.main import app
        yield
        app.dependency_overrides.clear()
    
    @patch('app.routers.auth_router.get_initial_user_roles')
    @patch('app.routers.auth_router.db')
    @patch('app.routers.auth_router.httpx.AsyncClient')
    @patch('app.routers.auth_router.create_access_token')
    def test_oauth_callback_creates_admin_user(self, mock_create_token, mock_httpx, mock_db, mock_get_roles):
        """Test that OAuth callback creates user with admin role when email matches."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        # Use context manager for environment variables
        with patch.dict('os.environ', {
            'GOOGLE_CLIENT_ID': 'test-id',
            'GOOGLE_CLIENT_SECRET': 'test-secret',
            'ADMIN_EMAIL': 'admin@scareverse.com'
        }):
            client = TestClient(app)
            
            # Mock get_initial_user_roles to return admin role
            mock_get_roles.return_value = ['admin']
            
            # Mock HTTP client responses
            mock_client = MagicMock()
            mock_httpx.return_value.__aenter__.return_value = mock_client
            
            # Mock token exchange
            token_response = Mock()
            token_response.status_code = 200
            token_response.json.return_value = {"access_token": "google-token"}
            mock_client.post = AsyncMock(return_value=token_response)
            
            # Mock user info with admin email
            user_response = Mock()
            user_response.status_code = 200
            user_response.json.return_value = {
                "id": "google-admin-123",
                "email": "admin@scareverse.com",
                "name": "Admin User"
            }
            mock_client.get = AsyncMock(return_value=user_response)
            
            # Mock database - no existing user
            mock_db.find_by_field = AsyncMock(return_value=None)
            mock_db.insert = AsyncMock(return_value=None)
            mock_create_token.return_value = "jwt-token-123"
            
            response = client.post("/api/auth/google/callback", json={
                "code": "auth-code",
                "redirect_uri": "http://localhost:8080/callback"
            })
            
            assert response.status_code == 200
            
            # Verify get_initial_user_roles was called with admin email
            mock_get_roles.assert_called_once_with('admin@scareverse.com')


class TestMigrationScriptLogic:
    """Tests for user role migration logic."""
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_migration_assigns_admin_role_to_matching_email(self):
        """Test migration logic assigns admin to matching email."""
        # Simulate what migration script does
        test_users = [
            {'email': 'admin@scareverse.com', 'roles': []},
            {'email': 'user1@example.com', 'roles': []},
            {'email': 'user2@example.com', 'roles': []}
        ]
        
        # Apply migration logic
        for user in test_users:
            if not user['roles']:
                user['roles'] = get_initial_user_roles(user['email'])
        
        # Verify results
        assert test_users[0]['roles'] == ['admin']
        assert test_users[1]['roles'] == ['user']
        assert test_users[2]['roles'] == ['user']
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_migration_preserves_existing_roles(self):
        """Test migration doesn't override existing roles."""
        # Simulate user with existing roles
        test_users = [
            {'email': 'admin@scareverse.com', 'roles': ['user']},
            {'email': 'user1@example.com', 'roles': ['moderator']}
        ]
        
        # Migration should only update users without roles
        for user in test_users:
            if not user['roles']:
                user['roles'] = get_initial_user_roles(user['email'])
        
        # Verify existing roles are preserved
        assert test_users[0]['roles'] == ['user']  # Not updated
        assert test_users[1]['roles'] == ['moderator']  # Not updated
    
    @patch('app.auth.ADMIN_EMAIL', 'admin@scareverse.com')
    def test_migration_case_insensitive_email_match(self):
        """Test migration handles case variations in email."""
        test_users = [
            {'email': 'ADMIN@SCAREVERSE.COM', 'roles': []},
            {'email': 'AdMiN@ScArEvErSe.CoM', 'roles': []}
        ]
        
        for user in test_users:
            if not user['roles']:
                user['roles'] = get_initial_user_roles(user['email'])
        
        # All should get admin role despite case variations
        assert all(user['roles'] == ['admin'] for user in test_users)


class TestPermissionValidation:
    """Tests for permission validation with admin roles."""
    
    def test_admin_user_has_admin_role(self):
        """Test that admin user has 'admin' in roles."""
        admin = User(
            name='Admin',
            email='admin@example.com',
            roles=['admin']
        )
        
        assert 'admin' in admin.roles
    
    def test_regular_user_does_not_have_admin_role(self):
        """Test that regular user does not have admin role."""
        user = User(
            name='User',
            email='user@example.com',
            roles=['user']
        )
        
        assert 'admin' not in user.roles
        assert 'user' in user.roles
