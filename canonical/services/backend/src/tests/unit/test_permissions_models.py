"""
Unit tests for RBAC permission models.

Tests the Permission, Role, UserRole, and RoleEnum models
to ensure proper validation, field constraints, and business logic.
Also tests User model updates for RBAC integration.

Coverage target: ≥90%
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.permissions import (
    Permission,
    Role,
    UserRole,
    RoleEnum
)
from app.models.users import User


class TestRoleEnum:
    """Test RoleEnum enumeration."""
    
    def test_role_enum_values(self):
        """Test that all expected role values exist."""
        assert RoleEnum.ADMIN == "admin"
        assert RoleEnum.USER == "user"
        assert RoleEnum.VIEWER == "viewer"
        assert RoleEnum.GUEST == "guest"
    
    def test_role_enum_membership(self):
        """Test role enum membership checks."""
        assert "admin" in [role.value for role in RoleEnum]
        assert "user" in [role.value for role in RoleEnum]
        assert "viewer" in [role.value for role in RoleEnum]
        assert "guest" in [role.value for role in RoleEnum]
        assert "invalid" not in [role.value for role in RoleEnum]


class TestPermission:
    """Test Permission model."""
    
    def test_permission_creation_valid(self):
        """Test creating a valid permission."""
        permission = Permission(
            name="cells.create",
            description="Create new cells",
            resource="cells",
            action="create",
            scope=None
        )
        
        assert permission.name == "cells.create"
        assert permission.description == "Create new cells"
        assert permission.resource == "cells"
        assert permission.action == "create"
        assert permission.scope is None
        assert permission.id is not None  # UUID generated
    
    def test_permission_with_scope(self):
        """Test creating a permission with scope."""
        permission = Permission(
            name="cells.read_own",
            description="Read own cells",
            resource="cells",
            action="read",
            scope="own"
        )
        
        assert permission.scope == "own"
        assert permission.name == "cells.read_own"
    
    def test_permission_name_format_validation(self):
        """Test permission name format validation."""
        # Valid format
        permission = Permission(
            name="books.update_any",
            description="Update any books",
            resource="books",
            action="update",
            scope="any"
        )
        assert permission.name == "books.update_any"
        
        # Invalid format - missing dot
        with pytest.raises(ValidationError) as exc_info:
            Permission(
                name="invalid_name",
                description="Invalid",
                resource="cells",
                action="create"
            )
        assert "must follow format 'resource.action" in str(exc_info.value)
        
        # Invalid format - too many dots
        with pytest.raises(ValidationError) as exc_info:
            Permission(
                name="cells.read.extra",
                description="Invalid",
                resource="cells",
                action="read"
            )
        assert "must follow format 'resource.action" in str(exc_info.value)
        
        # Invalid format - empty parts
        with pytest.raises(ValidationError) as exc_info:
            Permission(
                name="cells.",
                description="Invalid",
                resource="cells",
                action="read"
            )
        assert "cannot have empty resource or action" in str(exc_info.value)
    
    def test_permission_resource_validation(self):
        """Test resource validation."""
        # Valid resources
        valid_resources = ['cells', 'books', 'users', 'system', 'ai_models']
        for resource in valid_resources:
            permission = Permission(
                name=f"{resource}.read",
                description=f"Read {resource}",
                resource=resource,
                action="read"
            )
            assert permission.resource == resource
        
        # Invalid resource
        with pytest.raises(ValidationError) as exc_info:
            Permission(
                name="invalid.read",
                description="Invalid resource",
                resource="invalid",
                action="read"
            )
        assert "Resource must be one of" in str(exc_info.value)
    
    def test_permission_action_validation(self):
        """Test action validation."""
        # Valid actions
        valid_actions = ['create', 'read', 'update', 'delete', 'use', 'configure', 'manage', 'view_logs']
        for action in valid_actions:
            permission = Permission(
                name=f"cells.{action}",
                description=f"Action: {action}",
                resource="cells",
                action=action
            )
            assert permission.action == action
        
        # Invalid action
        with pytest.raises(ValidationError) as exc_info:
            Permission(
                name="cells.invalid",
                description="Invalid action",
                resource="cells",
                action="invalid_action"
            )
        assert "Action must be one of" in str(exc_info.value)
    
    def test_permission_all_resources_actions(self):
        """Test permission creation for all resource/action combinations."""
        test_cases = [
            ("cells", "create", None, "cells.create"),
            ("books", "read", "own", "books.read_own"),
            ("users", "manage", None, "users.manage"),
            ("system", "configure", None, "system.configure"),
            ("ai_models", "use", None, "ai_models.use"),
        ]
        
        for resource, action, scope, expected_name in test_cases:
            permission = Permission(
                name=expected_name,
                description=f"Test {expected_name}",
                resource=resource,
                action=action,
                scope=scope
            )
            assert permission.name == expected_name
            assert permission.resource == resource
            assert permission.action == action
            assert permission.scope == scope


class TestRole:
    """Test Role model."""
    
    def test_role_creation_valid(self):
        """Test creating a valid role."""
        role = Role(
            name=RoleEnum.USER,
            description="Standard user role",
            permissions=["cells.create", "cells.read_own"],
            priority=10
        )
        
        assert role.name == RoleEnum.USER
        assert role.description == "Standard user role"
        assert len(role.permissions) == 2
        assert role.priority == 10
        assert role.id is not None  # UUID generated
    
    def test_role_with_wildcard_permissions(self):
        """Test role with wildcard permissions (admin)."""
        role = Role(
            name=RoleEnum.ADMIN,
            description="Administrator role",
            permissions=["*"],
            priority=100
        )
        
        assert role.permissions == ["*"]
        assert role.priority == 100
    
    def test_role_empty_permissions(self):
        """Test role with empty permissions (guest)."""
        role = Role(
            name=RoleEnum.GUEST,
            description="Guest role",
            permissions=[],
            priority=1
        )
        
        assert role.permissions == []
        assert role.priority == 1
    
    def test_role_priority_validation(self):
        """Test role priority validation."""
        # Valid priority
        role = Role(
            name=RoleEnum.USER,
            description="Test",
            permissions=[],
            priority=50
        )
        assert role.priority == 50
        
        # Negative priority should fail
        with pytest.raises(ValidationError) as exc_info:
            Role(
                name=RoleEnum.USER,
                description="Test",
                permissions=[],
                priority=-1
            )
        assert "cannot be negative" in str(exc_info.value)
        
        # Excessively high priority should fail
        with pytest.raises(ValidationError) as exc_info:
            Role(
                name=RoleEnum.USER,
                description="Test",
                permissions=[],
                priority=1001
            )
        assert "cannot exceed 1000" in str(exc_info.value)
    
    def test_role_permissions_validation(self):
        """Test permissions list validation."""
        # Valid permissions list
        role = Role(
            name=RoleEnum.USER,
            description="Test",
            permissions=["cells.create", "books.read_own"],
            priority=10
        )
        assert len(role.permissions) == 2
        
        # Invalid permission format should fail
        with pytest.raises(ValidationError) as exc_info:
            Role(
                name=RoleEnum.USER,
                description="Test",
                permissions=["invalid_permission"],  # Missing dot
                priority=10
            )
        assert "must be a string in format 'resource.action" in str(exc_info.value)
        
        # Non-list permissions should fail
        with pytest.raises(ValidationError) as exc_info:
            Role(
                name=RoleEnum.USER,
                description="Test",
                permissions="not_a_list",
                priority=10
            )
        # Pydantic will handle this as type error
    
    def test_role_all_enum_values(self):
        """Test creating roles with all enum values."""
        test_cases = [
            (RoleEnum.ADMIN, 100),
            (RoleEnum.USER, 10),
            (RoleEnum.VIEWER, 5),
            (RoleEnum.GUEST, 1),
        ]
        
        for role_enum, priority in test_cases:
            role = Role(
                name=role_enum,
                description=f"{role_enum.value} role",
                permissions=[],
                priority=priority
            )
            assert role.name == role_enum
            assert role.priority == priority


class TestUserRole:
    """Test UserRole model."""
    
    def test_user_role_creation_valid(self):
        """Test creating a valid user-role association."""
        user_role = UserRole(
            userId="user-123",
            roleId="role-456",
            assignedBy="admin-789"
        )
        
        assert user_role.userId == "user-123"
        assert user_role.roleId == "role-456"
        assert user_role.assignedBy == "admin-789"
        assert user_role.id is not None  # UUID generated
        assert isinstance(user_role.assignedAt, datetime)
    
    def test_user_role_assigned_at_auto(self):
        """Test that assignedAt is automatically set."""
        before = datetime.utcnow()
        user_role = UserRole(
            userId="user-123",
            roleId="role-456",
            assignedBy="admin-789"
        )
        after = datetime.utcnow()
        
        assert before <= user_role.assignedAt <= after
    
    def test_user_role_id_validation(self):
        """Test that ID fields cannot be empty."""
        # Empty userId should fail
        with pytest.raises(ValidationError) as exc_info:
            UserRole(
                userId="",
                roleId="role-456",
                assignedBy="admin-789"
            )
        assert "cannot be empty" in str(exc_info.value)
        
        # Empty roleId should fail
        with pytest.raises(ValidationError) as exc_info:
            UserRole(
                userId="user-123",
                roleId="",
                assignedBy="admin-789"
            )
        assert "cannot be empty" in str(exc_info.value)
        
        # Empty assignedBy should fail
        with pytest.raises(ValidationError) as exc_info:
            UserRole(
                userId="user-123",
                roleId="role-456",
                assignedBy=""
            )
        assert "cannot be empty" in str(exc_info.value)
        
        # Whitespace-only should also fail
        with pytest.raises(ValidationError) as exc_info:
            UserRole(
                userId="   ",
                roleId="role-456",
                assignedBy="admin-789"
            )
        assert "cannot be empty" in str(exc_info.value)
    
    def test_user_role_multiple_assignments(self):
        """Test creating multiple user-role associations."""
        user_roles = [
            UserRole(
                userId=f"user-{i}",
                roleId=f"role-{i}",
                assignedBy="admin-1"
            )
            for i in range(5)
        ]
        
        assert len(user_roles) == 5
        # Each should have unique ID
        ids = [ur.id for ur in user_roles]
        assert len(ids) == len(set(ids))


class TestUserWithRoles:
    """Test User model with RBAC roles field."""
    
    def test_user_default_role(self):
        """Test that new users get default 'user' role."""
        user = User(
            name="Test User",
            email="test@example.com"
        )
        
        assert hasattr(user, 'roles')
        assert user.roles == ["user"]
    
    def test_user_custom_roles(self):
        """Test creating user with custom roles."""
        user = User(
            name="Admin User",
            email="admin@example.com",
            roles=["admin", "user"]
        )
        
        assert user.roles == ["admin", "user"]
    
    def test_user_single_role(self):
        """Test user with single role."""
        user = User(
            name="Viewer",
            email="viewer@example.com",
            roles=["viewer"]
        )
        
        assert user.roles == ["viewer"]
        assert len(user.roles) == 1
    
    def test_user_multiple_roles(self):
        """Test user with multiple roles."""
        user = User(
            name="Power User",
            email="power@example.com",
            roles=["user", "viewer", "admin"]
        )
        
        assert len(user.roles) == 3
        assert "user" in user.roles
        assert "viewer" in user.roles
        assert "admin" in user.roles
    
    def test_user_empty_roles(self):
        """Test user with empty roles list."""
        user = User(
            name="Guest",
            email="guest@example.com",
            roles=[]
        )
        
        assert user.roles == []
    
    def test_user_backward_compatibility(self):
        """Test that existing User fields still work."""
        user = User(
            name="Test User",
            email="test@example.com",
            googleId="google-123",
            galaxy="TestGalaxy",
            level=5
        )
        
        # Existing fields should work
        assert user.name == "Test User"
        assert user.email == "test@example.com"
        assert user.googleId == "google-123"
        assert user.galaxy == "TestGalaxy"
        assert user.level == 5
        
        # New field should have default
        assert user.roles == ["user"]
    
    def test_user_all_fields_with_roles(self):
        """Test user with all fields including roles."""
        user = User(
            name="Complete User",
            email="complete@example.com",
            googleId="google-456",
            hashedPassword="hashed_pwd",
            galaxy="MainGalaxy",
            level=10,
            roles=["admin", "user"]
        )
        
        assert user.name == "Complete User"
        assert user.email == "complete@example.com"
        assert user.googleId == "google-456"
        assert user.hashedPassword == "hashed_pwd"
        assert user.galaxy == "MainGalaxy"
        assert user.level == 10
        assert user.roles == ["admin", "user"]
