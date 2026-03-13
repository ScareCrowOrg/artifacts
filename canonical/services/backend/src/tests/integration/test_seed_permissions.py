"""
Integration tests for RBAC seed and migration scripts.

Tests the seed_permissions.py and migrate_user_roles.py scripts
to ensure proper database operations and idempotency.

Coverage target: ≥90%
"""

import pytest
from pathlib import Path
import sys

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_path))

from app.models.permissions import Permission, Role, RoleEnum
from app.models.users import User
from app.database import JSONDatabase
from scripts.seed_permissions import seed_permissions, seed_roles
from scripts.migrate_user_roles import migrate_users, verify_migration


@pytest.fixture
def test_db():
    """Create a test database instance."""
    db = JSONDatabase(is_test_env=True)
    yield db
    db.cleanup_test_data()


@pytest.fixture
def mock_db_in_scripts(monkeypatch, test_db):
    """Mock the db instance in scripts to use test database."""
    import scripts.seed_permissions as seed_module
    import scripts.migrate_user_roles as migrate_module
    
    monkeypatch.setattr(seed_module, 'db', test_db)
    monkeypatch.setattr(migrate_module, 'db', test_db)
    
    return test_db


class TestSeedPermissions:
    """Test seed_permissions script."""
    
    def test_seed_permissions_creates_permissions(self, mock_db_in_scripts):
        """Test that seed_permissions creates all expected permissions."""
        # Run seed
        count = seed_permissions()
        
        # Should create exactly 22 permissions (based on permissions_data in script)
        assert count == 22
        
        # Verify permissions exist in database
        permissions = mock_db_in_scripts.find_many(
            "permissions",
            Permission,
            is_canonical=True
        )
        
        assert len(permissions) == 22
    
    def test_seed_permissions_creates_correct_structure(self, mock_db_in_scripts):
        """Test that created permissions have correct structure."""
        # Run seed
        seed_permissions()
        
        # Get all permissions
        permissions = mock_db_in_scripts.find_many(
            "permissions",
            Permission,
            is_canonical=True
        )
        
        # Check that we have permissions for all resources
        resources = set(p.resource for p in permissions)
        assert 'cells' in resources
        assert 'books' in resources
        assert 'users' in resources
        assert 'system' in resources
        assert 'ai_models' in resources
        
        # Check that we have various actions
        actions = set(p.action for p in permissions)
        assert 'create' in actions
        assert 'read' in actions
        assert 'update' in actions
        assert 'delete' in actions
        
        # Check that we have scoped and non-scoped permissions
        scopes = [p.scope for p in permissions]
        assert None in scopes  # Non-scoped
        assert 'own' in scopes  # Own scope
        assert 'any' in scopes  # Any scope
    
    def test_seed_permissions_idempotent(self, mock_db_in_scripts):
        """Test that seed_permissions can be run multiple times safely."""
        # First run
        count1 = seed_permissions()
        assert count1 > 0
        
        # Second run should create 0 new permissions
        count2 = seed_permissions()
        assert count2 == 0
        
        # Third run should also create 0
        count3 = seed_permissions()
        assert count3 == 0
        
        # Total permissions should remain the same
        permissions_after = mock_db_in_scripts.find_many(
            "permissions",
            Permission,
            is_canonical=True
        )
        assert len(permissions_after) == count1
    
    def test_seed_permissions_specific_permissions(self, mock_db_in_scripts):
        """Test that specific expected permissions are created."""
        # Run seed
        seed_permissions()
        
        # Get all permissions
        permissions = mock_db_in_scripts.find_many(
            "permissions",
            Permission,
            is_canonical=True
        )
        
        #Create a mapping for easier lookup
        perm_dict = {p.name: p for p in permissions}
        
        # Check for specific permissions
        expected_permissions = [
            "cells.create",
            "cells.read_own",
            "cells.read_any",
            "cells.delete_any",
            "books.create",
            "users.manage",
            "system.configure",
            "ai_models.use"
        ]
        
        for perm_name in expected_permissions:
            assert perm_name in perm_dict, f"Permission {perm_name} should exist"


class TestSeedRoles:
    """Test seed_roles script."""
    
    def test_seed_roles_creates_four_roles(self, mock_db_in_scripts):
        """Test that seed_roles creates exactly 4 roles."""
        # Run seed (need permissions first)
        seed_permissions()
        count = seed_roles()
        
        # Should create 4 roles
        assert count == 4
        
        # Verify roles exist in database
        roles = mock_db_in_scripts.find_many(
            "roles",
            Role,
            is_canonical=True
        )
        
        assert len(roles) == 4
    
    def test_seed_roles_creates_correct_roles(self, mock_db_in_scripts):
        """Test that all expected roles are created."""
        # Run seed
        seed_permissions()
        seed_roles()
        
        # Get all roles
        roles = mock_db_in_scripts.find_many(
            "roles",
            Role,
            is_canonical=True
        )
        
        role_names = [r.name.value for r in roles]
        assert 'admin' in role_names
        assert 'user' in role_names
        assert 'viewer' in role_names
        assert 'guest' in role_names
    
    def test_seed_roles_admin_has_wildcard(self, mock_db_in_scripts):
        """Test that admin role has wildcard permissions."""
        # Run seed
        seed_permissions()
        seed_roles()
        
        # Get all roles
        roles = mock_db_in_scripts.find_many(
            "roles",
            Role,
            is_canonical=True
        )
        
        # Find admin role
        admin_role = None
        for r in roles:
            if r.name == RoleEnum.ADMIN:
                admin_role = r
                break
        
        assert admin_role is not None
        assert admin_role.permissions == ["*"]
        assert admin_role.priority == 100
    
    def test_seed_roles_user_permissions(self, mock_db_in_scripts):
        """Test that user role has correct permissions."""
        # Run seed
        seed_permissions()
        seed_roles()
        
        # Get all roles
        roles = mock_db_in_scripts.find_many(
            "roles",
            Role,
            is_canonical=True
        )
        
        # Find user role
        user_role = None
        for r in roles:
            if r.name == RoleEnum.USER:
                user_role = r
                break
        
        assert user_role is not None
        assert user_role.priority == 10
        
        # Should have own-scoped permissions and create permissions
        assert "cells.create" in user_role.permissions
        assert "cells.read_own" in user_role.permissions
        assert "books.create" in user_role.permissions
        assert "ai_models.use" in user_role.permissions
        
        # Should NOT have any-scoped permissions
        assert "cells.read_any" not in user_role.permissions
        assert "cells.delete_any" not in user_role.permissions
    
    def test_seed_roles_viewer_permissions(self, mock_db_in_scripts):
        """Test that viewer role has correct permissions."""
        # Run seed
        seed_permissions()
        seed_roles()
        
        # Get all roles
        roles = mock_db_in_scripts.find_many(
            "roles",
            Role,
            is_canonical=True
        )
        
        # Find viewer role
        viewer_role = None
        for r in roles:
            if r.name == RoleEnum.VIEWER:
                viewer_role = r
                break
        
        assert viewer_role is not None
        assert viewer_role.priority == 5
        
        # Should have read_any permissions
        assert "cells.read_any" in viewer_role.permissions
        assert "books.read_any" in viewer_role.permissions
        
        # Should NOT have write permissions
        assert "cells.create" not in viewer_role.permissions
        assert "cells.update_own" not in viewer_role.permissions
    
    def test_seed_roles_guest_no_permissions(self, mock_db_in_scripts):
        """Test that guest role has no permissions."""
        # Run seed
        seed_permissions()
        seed_roles()
        
        # Get all roles
        roles = mock_db_in_scripts.find_many(
            "roles",
            Role,
            is_canonical=True
        )
        
        # Find guest role
        guest_role = None
        for r in roles:
            if r.name == RoleEnum.GUEST:
                guest_role = r
                break
        
        assert guest_role is not None
        assert guest_role.permissions == []
        assert guest_role.priority == 1
    
    def test_seed_roles_idempotent(self, mock_db_in_scripts):
        """Test that seed_roles can be run multiple times safely."""
        # Run permissions seed first
        seed_permissions()
        
        # First run
        count1 = seed_roles()
        assert count1 == 4
        
        # Second run should create 0 new roles
        count2 = seed_roles()
        assert count2 == 0
        
        # Total roles should remain 4
        roles_after = mock_db_in_scripts.find_many(
            "roles",
            Role,
            is_canonical=True
        )
        assert len(roles_after) == 4


class TestMigrateUsers:
    """Test migrate_user_roles script."""
    
    def test_migrate_users_no_users(self, mock_db_in_scripts, monkeypatch):
        """Test migration with no existing users."""
        # Run migration
        count = migrate_users()
        
        # Should migrate 0 users
        assert count == 0
    
    def test_migrate_users_adds_roles_field(self, mock_db_in_scripts, monkeypatch):
        """Test that migration adds roles field to users."""
        # Create test user with roles (since User model has default)
        user1 = User(
            name="Test User 1",
            email="user1@example.com",
            roles=[]  # Empty roles to simulate old user
        )
        
        # Insert user
        mock_db_in_scripts.insert("users", user1, is_canonical=True)
        
        # Run migration
        count = migrate_users()
        
        # Should migrate 1 user (from empty roles to "user")
        assert count == 1
        
        # Verify user now has roles
        users = mock_db_in_scripts.find_many(
            "users",
            User,
            is_canonical=True
        )
        
        assert len(users) == 1
        assert users[0].roles == ["user"]
    
    def test_migrate_users_admin_email(self, mock_db_in_scripts, monkeypatch):
        """Test that admin email gets admin role."""
        # Set admin email
        monkeypatch.setenv("ADMIN_EMAIL", "admin@scareverse.com")
        
        # Mock the ADMIN_EMAIL in migrate script
        import scripts.migrate_user_roles as migrate_module
        monkeypatch.setattr(migrate_module, 'ADMIN_EMAIL', "admin@scareverse.com")
        
        # Create admin user
        admin_user = User(
            name="Admin User",
            email="admin@scareverse.com",
            roles=[]  # Empty to trigger migration
        )
        
        mock_db_in_scripts.insert("users", admin_user, is_canonical=True)
        
        # Run migration
        count = migrate_users()
        
        assert count == 1
        
        # Verify admin has admin role
        users = mock_db_in_scripts.find_many(
            "users",
            User,
            is_canonical=True
        )
        
        admin = [u for u in users if u.email == "admin@scareverse.com"][0]
        assert admin.roles == ["admin"]
    
    def test_migrate_users_idempotent(self, mock_db_in_scripts):
        """Test that migration is idempotent."""
        # Create test user with empty roles
        user1 = User(
            name="Test User",
            email="test@example.com",
            roles=[]
        )
        
        mock_db_in_scripts.insert("users", user1, is_canonical=True)
        
        # First migration
        count1 = migrate_users()
        assert count1 == 1
        
        # Second migration should skip user (already has roles)
        count2 = migrate_users()
        assert count2 == 0
        
        # Third migration should also skip
        count3 = migrate_users()
        assert count3 == 0
    
    def test_migrate_users_multiple_users(self, mock_db_in_scripts, monkeypatch):
        """Test migration with multiple users."""
        monkeypatch.setenv("ADMIN_EMAIL", "admin@scareverse.com")
        
        import scripts.migrate_user_roles as migrate_module
        monkeypatch.setattr(migrate_module, 'ADMIN_EMAIL', "admin@scareverse.com")
        
        # Create multiple users with empty roles
        users_data = [
            User(name="Admin", email="admin@scareverse.com", roles=[]),
            User(name="User 1", email="user1@example.com", roles=[]),
            User(name="User 2", email="user2@example.com", roles=[]),
        ]
        
        for user in users_data:
            mock_db_in_scripts.insert("users", user, is_canonical=True)
        
        # Run migration
        count = migrate_users()
        assert count == 3
        
        # Verify each user
        all_users = mock_db_in_scripts.find_many(
            "users",
            User,
            is_canonical=True
        )
        
        user_dict = {u.email: u for u in all_users}
        
        assert user_dict["admin@scareverse.com"].roles == ["admin"]
        assert user_dict["user1@example.com"].roles == ["user"]
        assert user_dict["user2@example.com"].roles == ["user"]


class TestVerifyMigration:
    """Test verify_migration function."""
    
    def test_verify_migration_all_users_have_roles(self, mock_db_in_scripts):
        """Test verification when all users have roles."""
        # Create users with roles
        user1 = User(name="User 1", email="user1@example.com", roles=["user"])
        user2 = User(name="User 2", email="user2@example.com", roles=["viewer"])
        
        mock_db_in_scripts.insert("users", user1, is_canonical=True)
        mock_db_in_scripts.insert("users", user2, is_canonical=True)
        
        # Verify
        result = verify_migration()
        assert result is True
