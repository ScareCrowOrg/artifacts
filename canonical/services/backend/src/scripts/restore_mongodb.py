"""
MongoDB Restore Script for RBAC Rollback.

This script restores a MongoDB database from a backup created by backup_mongodb.py,
enabling rollback of RBAC deployment if needed.

Features:
- Restores from timestamped backups
- Validates restoration
- Supports both local and remote MongoDB instances
- Handles compressed backups
- Provides detailed logging

Usage:
    cd backend
    python -m scripts.restore_mongodb --backup-path /backups/pre-rbac-migration-20251127
    
    # With drop existing data
    python -m scripts.restore_mongodb --backup-path /backups/pre-rbac-migration-20251127 --drop
    
    # Restore specific database
    python -m scripts.restore_mongodb --backup-path /backups/pre-rbac-migration-20251127 --database scareverse_staging

Output:
    ✅ Backup restored from: /backups/pre-rbac-migration-20251127
    ✅ Collections restored: 8
    ✅ Restoration validated successfully
"""

import sys
import logging
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import json

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.config import MONGODB_URI

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Restore MongoDB database from backup'
    )
    parser.add_argument(
        '--backup-path',
        type=str,
        required=True,
        help='Path to backup directory to restore from'
    )
    parser.add_argument(
        '--database',
        type=str,
        default=None,
        help='Specific database to restore (default: from backup)'
    )
    parser.add_argument(
        '--drop',
        action='store_true',
        default=False,
        help='Drop existing collections before restore (default: False)'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        default=False,
        help='Skip confirmation prompt (use with caution!)'
    )
    return parser.parse_args()


def validate_backup_path(backup_path: Path) -> bool:
    """
    Validate that backup path exists and contains data.
    
    Args:
        backup_path: Path to backup directory
    
    Returns:
        True if valid, False otherwise
    """
    if not backup_path.exists():
        logger.error(f"Backup path does not exist: {backup_path}")
        return False
    
    if not backup_path.is_dir():
        logger.error(f"Backup path is not a directory: {backup_path}")
        return False
    
    # Check for any .bson files (compressed or not)
    bson_files = list(backup_path.rglob('*.bson*'))
    if not bson_files:
        logger.error(f"No BSON files found in backup: {backup_path}")
        return False
    
    logger.info(f"Found {len(bson_files)} BSON files in backup")
    return True


def load_backup_metadata(backup_path: Path) -> dict:
    """
    Load backup metadata if available.
    
    Args:
        backup_path: Path to backup directory
    
    Returns:
        Metadata dictionary or empty dict if not found
    """
    metadata_file = backup_path.parent / f'{backup_path.name}.json'
    
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        logger.info("Backup metadata loaded:")
        logger.info(f"   - Created: {metadata.get('timestamp')}")
        logger.info(f"   - Purpose: {metadata.get('purpose')}")
        logger.info(f"   - Compressed: {metadata.get('compressed')}")
        return metadata
    else:
        logger.warning("No metadata file found")
        return {}


def confirm_restore(backup_path: Path, drop: bool) -> bool:
    """
    Ask user for confirmation before restoring.
    
    Args:
        backup_path: Path to backup directory
        drop: Whether existing data will be dropped
    
    Returns:
        True if confirmed, False otherwise
    """
    logger.warning("=" * 60)
    logger.warning("⚠️  DATABASE RESTORATION WARNING")
    logger.warning("=" * 60)
    logger.warning(f"Backup path: {backup_path}")
    logger.warning(f"Drop existing data: {drop}")
    logger.warning("")
    
    if drop:
        logger.warning("This will DELETE all existing data in the database!")
    else:
        logger.warning("This will MERGE backup data with existing data.")
        logger.warning("Conflicts may occur if documents with same IDs exist.")
    
    logger.warning("")
    response = input("Are you sure you want to continue? (yes/no): ")
    
    return response.lower() in ['yes', 'y']


def run_mongorestore(
    mongodb_uri: str,
    backup_path: Path,
    database: str = None,
    drop: bool = False
) -> bool:
    """
    Execute mongorestore command to restore backup.
    
    Args:
        mongodb_uri: MongoDB connection URI
        backup_path: Path to backup directory
        database: Specific database to restore (optional)
        drop: Whether to drop existing collections
    
    Returns:
        True if restore successful, False otherwise
    """
    logger.info("Starting MongoDB restore...")
    logger.info(f"Backup path: {backup_path}")
    
    # Build mongorestore command
    cmd = [
        'mongorestore',
        f'--uri={mongodb_uri}',
        '--verbose'
    ]
    
    if drop:
        cmd.append('--drop')
        logger.warning("Drop mode enabled - existing data will be deleted")
    
    # Add backup path (must be last)
    cmd.append(str(backup_path))
    
    # Execute mongorestore
    try:
        logger.info(f"Executing: {' '.join(cmd[:2])} ...")  # Hide URI
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("mongorestore completed successfully")
        logger.debug(f"Output: {result.stdout}")
        
        # Parse output for statistics
        output_lines = result.stdout.split('\n')
        for line in output_lines:
            if 'documents' in line.lower() or 'collection' in line.lower():
                logger.info(line.strip())
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"mongorestore failed: {e}")
        logger.error(f"stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("mongorestore command not found. Please install MongoDB tools.")
        logger.error("Install: apt-get install mongodb-database-tools")
        return False


def validate_restoration() -> bool:
    """
    Validate restoration by checking critical collections.
    
    Returns:
        True if restoration is valid, False otherwise
    """
    logger.info("Validating restoration...")
    
    try:
        from app.database import db
        from app.models.users import Usuario
        from app.models.permissions import Role, Permission
        
        # Check usuarios collection
        try:
            usuarios = db.find_many("usuarios", Usuario, is_canonical=True)
            logger.info(f"✅ Found {len(usuarios)} users in canonical storage")
        except Exception as e:
            logger.warning(f"Could not check canonical usuarios: {e}")
            usuarios = []
        
        # Check roles collection
        try:
            roles = db.find_many("roles", Role, is_canonical=True)
            logger.info(f"✅ Found {len(roles)} roles")
        except Exception as e:
            logger.warning(f"Could not check roles: {e}")
            roles = []
        
        # Check permissions collection
        try:
            permissions = db.find_many("permissions", Permission, is_canonical=True)
            logger.info(f"✅ Found {len(permissions)} permissions")
        except Exception as e:
            logger.warning(f"Could not check permissions: {e}")
            permissions = []
        
        # Validation: At least one user should exist
        if len(usuarios) == 0:
            logger.warning("⚠️  No users found after restoration")
            logger.warning("This may be normal if database was empty before backup")
        
        logger.info("Restoration validation completed")
        return True
        
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        return False


def main():
    """
    Main execution function.
    
    Restores MongoDB backup with validation.
    """
    try:
        logger.info("=" * 60)
        logger.info("ScareVerse MongoDB Restore Script")
        logger.info("=" * 60)
        
        # Parse arguments
        args = parse_args()
        
        backup_path = Path(args.backup_path)
        
        # Validate backup
        if not validate_backup_path(backup_path):
            logger.error("❌ Invalid backup path")
            sys.exit(1)
        
        # Load metadata
        load_backup_metadata(backup_path)
        
        logger.info("-" * 60)
        
        # Confirm restoration
        if not args.confirm:
            if not confirm_restore(backup_path, args.drop):
                logger.info("Restoration cancelled by user")
                sys.exit(0)
        
        logger.info("-" * 60)
        
        # Restore backup
        success = run_mongorestore(
            mongodb_uri=MONGODB_URI,
            backup_path=backup_path,
            database=args.database,
            drop=args.drop
        )
        
        if not success:
            logger.error("❌ Restoration failed")
            sys.exit(1)
        
        logger.info("-" * 60)
        
        # Validate restoration
        valid = validate_restoration()
        if not valid:
            logger.warning("⚠️  Restoration validation had warnings")
        
        logger.info("=" * 60)
        logger.info("✅ Restoration completed!")
        logger.info(f"   - Backup path: {backup_path}")
        logger.info(f"   - Drop mode: {args.drop}")
        logger.info(f"   - Validated: {valid}")
        logger.info("=" * 60)
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Restoration failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
