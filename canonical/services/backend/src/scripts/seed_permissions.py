"""
Seed script for RBAC permissions and roles.

This script populates the database with initial permissions and roles
for the ScareVerse RBAC (Role-Based Access Control) system.

Usage:
    cd backend
    python -m scripts.seed_permissions

Output:
    ✅ 20 permissions created
    ✅ 4 roles created
    ✅ Seed of permissions completed
"""

import sys
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.models.permissions import Permission, Role, RoleEnum
from app.database import db

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def seed_permissions() -> int:
    """
    Create initial permissions for the RBAC system.
    
    Permissions are organized by resource:
    - Cells: Document/artifact cells
    - Books: Collections of cells
    - Users: User management
    - System: System administration
    - AI Models: AI model configuration
    
    Returns:
        Number of permissions created
    """
    logger.info("Starting permissions seed...")
    
    # Define all permissions
    permissions_data = [
        # Cells permissions
        {
            "name": "cells.create",
            "description": "Create new cells",
            "resource": "cells",
            "action": "create",
            "scope": None
        },
        {
            "name": "cells.read_own",
            "description": "Read own cells",
            "resource": "cells",
            "action": "read",
            "scope": "own"
        },
        {
            "name": "cells.read_any",
            "description": "Read any user's cells",
            "resource": "cells",
            "action": "read",
            "scope": "any"
        },
        {
            "name": "cells.update_own",
            "description": "Update own cells",
            "resource": "cells",
            "action": "update",
            "scope": "own"
        },
        {
            "name": "cells.update_any",
            "description": "Update any user's cells",
            "resource": "cells",
            "action": "update",
            "scope": "any"
        },
        {
            "name": "cells.delete_own",
            "description": "Delete own cells",
            "resource": "cells",
            "action": "delete",
            "scope": "own"
        },
        {
            "name": "cells.delete_any",
            "description": "Delete any user's cells",
            "resource": "cells",
            "action": "delete",
            "scope": "any"
        },
        
        # Books permissions
        {
            "name": "books.create",
            "description": "Create new books",
            "resource": "books",
            "action": "create",
            "scope": None
        },
        {
            "name": "books.read_own",
            "description": "Read own books",
            "resource": "books",
            "action": "read",
            "scope": "own"
        },
        {
            "name": "books.read_any",
            "description": "Read any user's books",
            "resource": "books",
            "action": "read",
            "scope": "any"
        },
        {
            "name": "books.update_own",
            "description": "Update own books",
            "resource": "books",
            "action": "update",
            "scope": "own"
        },
        {
            "name": "books.update_any",
            "description": "Update any user's books",
            "resource": "books",
            "action": "update",
            "scope": "any"
        },
        {
            "name": "books.delete_own",
            "description": "Delete own books",
            "resource": "books",
            "action": "delete",
            "scope": "own"
        },
        {
            "name": "books.delete_any",
            "description": "Delete any user's books",
            "resource": "books",
            "action": "delete",
            "scope": "any"
        },
        
        # Users permissions
        {
            "name": "users.read_own",
            "description": "Read own user profile",
            "resource": "users",
            "action": "read",
            "scope": "own"
        },
        {
            "name": "users.read_any",
            "description": "Read any user's profile",
            "resource": "users",
            "action": "read",
            "scope": "any"
        },
        {
            "name": "users.manage",
            "description": "Manage users (create, update, delete, assign roles)",
            "resource": "users",
            "action": "manage",
            "scope": None
        },
        
        # System permissions
        {
            "name": "system.configure",
            "description": "Configure system settings",
            "resource": "system",
            "action": "configure",
            "scope": None
        },
        {
            "name": "system.view_logs",
            "description": "View system logs and diagnostics",
            "resource": "system",
            "action": "view_logs",
            "scope": None
        },
        {
            "name": "system.manage",
            "description": "Manage roles and permissions",
            "resource": "system",
            "action": "manage",
            "scope": None
        },
        
        # AI Models permissions
        {
            "name": "ai_models.use",
            "description": "Use AI models for chat and processing",
            "resource": "ai_models",
            "action": "use",
            "scope": None
        },
        {
            "name": "ai_models.configure",
            "description": "Configure AI models and settings",
            "resource": "ai_models",
            "action": "configure",
            "scope": None
        }
    ]
    
    created_count = 0
    
    # Get existing permissions to check for duplicates
    existing_perms = db.find_many("permissions", Permission, is_canonical=True)
    existing_names = {p.name for p in existing_perms}
    
    for perm_data in permissions_data:
        # Build permission name with scope if present
        perm_name = perm_data["name"]
        
        # Check if permission already exists
        if perm_name in existing_names:
            logger.debug(f"Permission '{perm_name}' already exists, skipping")
            continue
        
        # Create permission
        permission = Permission(
            name=perm_name,
            description=perm_data["description"],
            resource=perm_data["resource"],
            action=perm_data["action"],
            scope=perm_data["scope"]
        )
        
        db.insert("permissions", permission, is_canonical=True)
        created_count += 1
        logger.debug(f"Created permission: {perm_name}")
    
    logger.info(f"✅ {created_count} permissions created")
    return created_count


def seed_roles() -> int:
    """
    Create initial roles for the RBAC system.
    
    Roles:
    - admin: Full system access (all permissions)
    - user: Standard user permissions (own resources + create)
    - viewer: Read-only access (read_any permissions)
    - guest: Minimal permissions (no access)
    
    Returns:
        Number of roles created
    """
    logger.info("Starting roles seed...")
    
    # Define all roles
    roles_data = [
        {
            "name": RoleEnum.ADMIN,
            "description": "Administrator with full system access",
            "permissions": ["*"],  # Wildcard for all permissions
            "priority": 100
        },
        {
            "name": RoleEnum.USER,
            "description": "Standard user with access to own resources",
            "permissions": [
                "cells.create",
                "cells.read_own",
                "cells.update_own",
                "cells.delete_own",
                "books.create",
                "books.read_own",
                "books.update_own",
                "books.delete_own",
                "users.read_own",
                "ai_models.use"
            ],
            "priority": 10
        },
        {
            "name": RoleEnum.VIEWER,
            "description": "Read-only access to resources",
            "permissions": [
                "cells.read_any",
                "books.read_any",
                "users.read_own"
            ],
            "priority": 5
        },
        {
            "name": RoleEnum.GUEST,
            "description": "Guest with minimal access",
            "permissions": [],
            "priority": 1
        }
    ]
    
    created_count = 0
    
    # Get existing roles to check for duplicates
    existing_roles = db.find_many("roles", Role, is_canonical=True)
    existing_names = {r.name.value for r in existing_roles}
    
    for role_data in roles_data:
        # Check if role already exists
        if role_data["name"].value in existing_names:
            logger.debug(f"Role '{role_data['name'].value}' already exists, skipping")
            continue
        
        # Create role
        role = Role(
            name=role_data["name"],
            description=role_data["description"],
            permissions=role_data["permissions"],
            priority=role_data["priority"]
        )
        
        db.insert("roles", role, is_canonical=True)
        created_count += 1
        logger.info(f"Created role: {role_data['name'].value} (priority={role_data['priority']})")
    
    logger.info(f"✅ {created_count} roles created")
    return created_count


def main():
    """
    Main execution function.
    
    Executes permission and role seeding in sequence.
    """
    try:
        logger.info("=" * 60)
        logger.info("ScareVerse RBAC Seed Script")
        logger.info("=" * 60)
        
        # Seed permissions first
        perm_count = seed_permissions()
        
        # Seed roles second
        role_count = seed_roles()
        
        logger.info("=" * 60)
        logger.info(f"✅ Seed completed successfully!")
        logger.info(f"   - Permissions created: {perm_count}")
        logger.info(f"   - Roles created: {role_count}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Seed failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
