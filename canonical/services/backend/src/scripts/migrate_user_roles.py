"""
Migration script to add roles field to existing users.

This script updates all existing User documents to include the 'roles' field
following the RBAC implementation.

Logic:
- Users without 'roles' field receive the default 'user' role
- Admin user (identified by ADMIN_EMAIL env var) receives 'admin' role
- Script is idempotent (can be run multiple times safely)

Usage:
    cd backend
    python -m scripts.migrate_user_roles

Output:
    ✅ User admin@scareverse.com updated with role: ['admin']
    ✅ User user1@example.com updated with role: ['user']
    ✅ 5 users migrated
"""

import sys
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.models.users import User
from app.database import db
from app.config import ADMIN_EMAIL

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_users() -> int:
    """
    Add 'roles' field to all existing users in the database.
    
    Migration logic:
    1. Fetch all users from database
    2. For users without 'roles' field or with empty roles:
       - If email matches ADMIN_EMAIL: assign 'admin' role
       - Otherwise: assign default 'user' role
    3. Update user document in database
    4. Skip users who already have roles assigned
    
    Returns:
        Number of users migrated
    """
    logger.info("Starting user roles migration...")
    logger.info(f"Admin email (from config): {ADMIN_EMAIL}")
    
    # Fetch all users from both storages with tracking
    users_runtime = []
    users_canonical = []
    
    # Try to find users in runtime storage
    try:
        runtime_users = db.find_many("users", User, is_canonical=False)
        users_runtime.extend([(u, False) for u in runtime_users])  # (user, is_canonical)
        logger.info(f"Found {len(runtime_users)} users in runtime storage")
    except Exception as e:
        logger.debug(f"No runtime users found or error: {e}")
    
    # Try to find users in canonical storage
    try:
        canonical_users = db.find_many("users", User, is_canonical=True)
        users_canonical.extend([(u, True) for u in canonical_users])  # (user, is_canonical)
        logger.info(f"Found {len(canonical_users)} users in canonical storage")
    except Exception as e:
        logger.debug(f"No canonical users found or error: {e}")
    
    # Combine all users
    all_users = users_runtime + users_canonical
    
    if not all_users:
        logger.warning("⚠️  No users found in database. Migration complete (nothing to migrate).")
        return 0
    
    logger.info(f"Processing {len(all_users)} users...")
    
    migrated_count = 0
    skipped_count = 0
    
    for user, is_canonical_storage in all_users:
        # Check if user already has roles assigned and is not empty
        if hasattr(user, 'roles') and user.roles:
            logger.debug(f"User {user.email} already has roles: {user.roles}, skipping")
            skipped_count += 1
            continue
        
        # Determine role based on email
        # Note: Email comparison is case-insensitive to handle variations
        # The database should enforce unique lowercase emails to avoid issues
        if user.email.lower() == ADMIN_EMAIL.lower():
            new_roles = ["admin"]
            logger.info(f"Assigning admin role to: {user.email}")
        else:
            new_roles = ["user"]
            logger.debug(f"Assigning user role to: {user.email}")
        
        # Update user model
        user.roles = new_roles
        
        # Update in database using the same storage type
        try:
            db.update("users", user.id, {"roles": new_roles}, is_canonical=is_canonical_storage)
            migrated_count += 1
            logger.info(f"✅ User {user.email} updated with roles: {new_roles}")
        except Exception as e:
            logger.warning(f"Could not update user {user.email}: {e}")
            continue
    
    logger.info(f"Migration complete: {migrated_count} users migrated, {skipped_count} users skipped")
    return migrated_count


def verify_migration() -> bool:
    """
    Verify that all users now have the roles field.
    
    Returns:
        True if all users have roles, False otherwise
    """
    logger.info("Verifying migration...")
    
    # Fetch all users again
    users = []
    
    try:
        runtime_users = db.find_many("users", User, is_canonical=False)
        users.extend(runtime_users)
    except Exception:
        pass
    
    try:
        canonical_users = db.find_many("users", User, is_canonical=True)
        users.extend(canonical_users)
    except Exception:
        pass
    
    if not users:
        logger.info("No users to verify")
        return True
    
    users_without_roles = []
    
    for user in users:
        if not hasattr(user, 'roles') or not user.roles:
            users_without_roles.append(user.email)
    
    if users_without_roles:
        logger.warning(f"⚠️  {len(users_without_roles)} users still without roles:")
        for email in users_without_roles:
            logger.warning(f"   - {email}")
        return False
    else:
        logger.info(f"✅ All {len(users)} users have roles assigned")
        return True


def main():
    """
    Main execution function.
    
    Executes migration and verification.
    """
    try:
        logger.info("=" * 60)
        logger.info("ScareVerse User Roles Migration Script")
        logger.info("=" * 60)
        
        # Run migration
        migrated_count = migrate_users()
        
        logger.info("-" * 60)
        
        # Verify migration
        success = verify_migration()
        
        logger.info("=" * 60)
        if success:
            logger.info(f"✅ Migration completed successfully!")
            logger.info(f"   - Users migrated: {migrated_count}")
        else:
            logger.warning(f"⚠️  Migration completed with warnings")
            logger.warning(f"   - Users migrated: {migrated_count}")
            logger.warning(f"   - Some users may not have roles assigned")
        logger.info("=" * 60)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"❌ Migration failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
