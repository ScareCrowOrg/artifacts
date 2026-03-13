"""
MongoDB Backup Script for RBAC Deployment.

This script creates a backup of the MongoDB database before RBAC migration,
ensuring we can rollback if needed.

Features:
- Creates timestamped backups
- Validates backup integrity
- Supports both local and remote MongoDB instances
- Compresses backups to save space
- Provides detailed logging

Usage:
    cd backend
    python -m scripts.backup_mongodb
    
    # With custom backup directory
    python -m scripts.backup_mongodb --backup-dir /path/to/backups
    
    # Backup specific database
    python -m scripts.backup_mongodb --database scareverse_staging

Output:
    ✅ Backup created: /backups/pre-rbac-migration-20251127-140530
    ✅ Backup size: 15.3 MB
    ✅ Collections backed up: 8
    ✅ Backup validated successfully
"""

import sys
import logging
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import json
import os

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_path))

from app.config import MONGODB_URI, BASE_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Backup MongoDB database before RBAC migration'
    )
    parser.add_argument(
        '--backup-dir',
        type=str,
        default='/backups',
        help='Directory to store backups (default: /backups)'
    )
    parser.add_argument(
        '--database',
        type=str,
        default=None,
        help='Specific database to backup (default: from MONGODB_URI)'
    )
    parser.add_argument(
        '--compress',
        action='store_true',
        default=True,
        help='Compress backup with gzip (default: True)'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        default=True,
        help='Validate backup after creation (default: True)'
    )
    return parser.parse_args()


def get_backup_path(backup_dir: str) -> Path:
    """
    Generate timestamped backup path.
    
    Args:
        backup_dir: Base directory for backups
    
    Returns:
        Path object for backup location
    """
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_name = f'pre-rbac-migration-{timestamp}'
    backup_path = Path(backup_dir) / backup_name
    
    # Create backup directory if it doesn't exist
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    
    return backup_path


def run_mongodump(
    mongodb_uri: str,
    backup_path: Path,
    database: str = None,
    compress: bool = True
) -> bool:
    """
    Execute mongodump command to create backup.
    
    Args:
        mongodb_uri: MongoDB connection URI
        backup_path: Path to store backup
        database: Specific database to backup (optional)
        compress: Whether to compress backup with gzip
    
    Returns:
        True if backup successful, False otherwise
    """
    logger.info("Starting MongoDB backup...")
    logger.info(f"Backup path: {backup_path}")
    
    # Build mongodump command
    cmd = [
        'mongodump',
        f'--uri={mongodb_uri}',
        f'--out={backup_path}',
        '--verbose'
    ]
    
    if database:
        cmd.append(f'--db={database}')
        logger.info(f"Backing up database: {database}")
    else:
        logger.info("Backing up all databases")
    
    if compress:
        cmd.append('--gzip')
        logger.info("Compression enabled")
    
    # Execute mongodump
    try:
        logger.info(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("mongodump completed successfully")
        logger.debug(f"Output: {result.stdout}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"mongodump failed: {e}")
        logger.error(f"stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("mongodump command not found. Please install MongoDB tools.")
        logger.error("Install: apt-get install mongodb-database-tools")
        return False


def validate_backup(backup_path: Path) -> bool:
    """
    Validate backup integrity by checking files and collections.
    
    Args:
        backup_path: Path to backup directory
    
    Returns:
        True if backup is valid, False otherwise
    """
    logger.info("Validating backup...")
    
    if not backup_path.exists():
        logger.error(f"Backup path does not exist: {backup_path}")
        return False
    
    # Check if backup has content
    backup_files = list(backup_path.rglob('*'))
    if not backup_files:
        logger.error("Backup directory is empty")
        return False
    
    logger.info(f"Backup contains {len(backup_files)} files")
    
    # Check for critical collections
    critical_collections = ['usuarios', 'roles', 'permissions']
    found_collections = []
    
    for collection in critical_collections:
        # Look for .bson or .bson.gz files
        bson_files = list(backup_path.rglob(f'{collection}.bson*'))
        if bson_files:
            found_collections.append(collection)
            logger.debug(f"Found collection: {collection}")
    
    if len(found_collections) < len(critical_collections):
        missing = set(critical_collections) - set(found_collections)
        logger.warning(f"Some critical collections missing: {missing}")
        logger.warning("This may be normal if collections don't exist yet")
    else:
        logger.info(f"All critical collections backed up: {found_collections}")
    
    # Calculate backup size
    total_size = sum(f.stat().st_size for f in backup_files if f.is_file())
    size_mb = total_size / (1024 * 1024)
    logger.info(f"Backup size: {size_mb:.2f} MB")
    
    return True


def create_backup_metadata(backup_path: Path, args: argparse.Namespace):
    """
    Create metadata file with backup information.
    
    Args:
        backup_path: Path to backup directory
        args: Command line arguments
    """
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'backup_path': str(backup_path),
        'mongodb_uri': MONGODB_URI.split('@')[-1],  # Hide credentials
        'database': args.database,
        'compressed': args.compress,
        'purpose': 'pre-rbac-migration',
        'created_by': 'backup_mongodb.py',
        'version': '1.0.0'
    }
    
    metadata_file = backup_path.parent / f'{backup_path.name}.json'
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Metadata saved: {metadata_file}")


def main():
    """
    Main execution function.
    
    Creates MongoDB backup with validation and metadata.
    """
    try:
        logger.info("=" * 60)
        logger.info("ScareVerse MongoDB Backup Script")
        logger.info("=" * 60)
        
        # Parse arguments
        args = parse_args()
        
        # Generate backup path
        backup_path = get_backup_path(args.backup_dir)
        
        # Create backup
        success = run_mongodump(
            mongodb_uri=MONGODB_URI,
            backup_path=backup_path,
            database=args.database,
            compress=args.compress
        )
        
        if not success:
            logger.error("❌ Backup failed")
            sys.exit(1)
        
        logger.info("-" * 60)
        
        # Validate backup
        if args.validate:
            valid = validate_backup(backup_path)
            if not valid:
                logger.error("❌ Backup validation failed")
                sys.exit(1)
        
        # Create metadata
        create_backup_metadata(backup_path, args)
        
        logger.info("=" * 60)
        logger.info("✅ Backup completed successfully!")
        logger.info(f"   - Backup path: {backup_path}")
        logger.info(f"   - Compressed: {args.compress}")
        logger.info(f"   - Validated: {args.validate}")
        logger.info("")
        logger.info("To restore this backup, run:")
        logger.info(f"   python -m scripts.restore_mongodb --backup-path {backup_path}")
        logger.info("=" * 60)
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Backup failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
