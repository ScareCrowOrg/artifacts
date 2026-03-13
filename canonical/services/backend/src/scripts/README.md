---
processed: true
processed_date: 2025-12-09
themes:
  - scripts
  - rbac
  - deployment
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Backend Scripts

Utility scripts for backend development, testing, deployment, and maintenance.

## Index

### RBAC Deployment Scripts (Sprint 4.1)
- [`backup_mongodb.py`](./backup_mongodb.py) - Create MongoDB backup before RBAC migration
- [`restore_mongodb.py`](./restore_mongodb.py) - Restore MongoDB from backup (rollback)
- [`validate_rbac_deployment.py`](./validate_rbac_deployment.py) - Validate RBAC deployment
- [`deploy_rbac.sh`](./deploy_rbac.sh) - Automated RBAC deployment to staging/production

### RBAC Migration and Seeding
- [`migrate_user_roles.py`](./migrate_user_roles.py) - Migrate existing users to RBAC roles
- [`seed_permissions.py`](./seed_permissions.py) - Seed permissions and roles in database

### Other Scripts
- Database seeding scripts
- Testing utilities
- Development helpers
- Maintenance scripts

## Purpose

Backend scripts automate common tasks:
- Database initialization and seeding
- Data migration and transformation
- Test data generation
- Performance testing
- Maintenance and cleanup

## Script Categories

### RBAC Deployment Scripts
- **Backup**: `backup_mongodb.py` - Create timestamped MongoDB backups
- **Restore**: `restore_mongodb.py` - Restore MongoDB from backup
- **Migration**: `migrate_user_roles.py` - Migrate users to RBAC model
- **Seeding**: `seed_permissions.py` - Seed permissions and roles
- **Validation**: `validate_rbac_deployment.py` - Validate RBAC deployment
- **Deployment**: `deploy_rbac.sh` - Automated deployment orchestration

### Database Scripts
- **Seeding**: Initialize database with test data
- **Migration**: Update database schema
- **Backup**: Create database backups
- **Cleanup**: Remove old/test data

### Testing Scripts
- **Test Data**: Generate test fixtures
- **Mock Data**: Create mock API responses
- **Load Testing**: Performance testing scripts

### Development Scripts
- **Setup**: Local environment setup
- **Reset**: Reset development environment
- **Validation**: Validate configuration

## Usage Pattern

Scripts should follow this pattern:
```python
#!/usr/bin/env python3
"""
Script description and purpose.
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import BASE_DIR, settings
from app.database import get_database

def main():
    """Main script logic."""
    # Implementation
    pass

if __name__ == '__main__':
    main()
```

## Configuration

Scripts should use centralized configuration:
```python
from app.config import BASE_DIR, settings

# Use BASE_DIR for paths
data_file = BASE_DIR / 'data' / 'seed.json'

# Use settings for configuration
db_url = settings.MONGODB_URI
```

## Best Practices

### Script Development
- Use descriptive names (e.g., `seed_database.py`)
- Include docstrings and help text
- Use argparse for CLI arguments
- Implement proper error handling
- Log progress and results

### Example Script Structure
```python
#!/usr/bin/env python3
"""Seed database with initial data."""
import argparse
import logging
from app.database import get_database
from app.models import User, Cell

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_users(db, count=10):
    """Create test users."""
    logger.info(f"Creating {count} test users...")
    # Implementation
    logger.info("Users created successfully")

def seed_cells(db, count=50):
    """Create test cells."""
    logger.info(f"Creating {count} test cells...")
    # Implementation
    logger.info("Cells created successfully")

def main():
    parser = argparse.ArgumentParser(description='Seed database')
    parser.add_argument('--users', type=int, default=10)
    parser.add_argument('--cells', type=int, default=50)
    args = parser.parse_args()

    db = get_database()
    seed_users(db, args.users)
    seed_cells(db, args.cells)
    
    logger.info("Database seeding complete!")

if __name__ == '__main__':
    main()
```

## Running Scripts

### RBAC Deployment Scripts

#### Backup MongoDB
```bash
cd backend
python -m scripts.backup_mongodb --backup-dir /backups

# With custom database
python -m scripts.backup_mongodb --database scareverse_staging
```

#### Restore MongoDB
```bash
cd backend
python -m scripts.restore_mongodb \
  --backup-path /backups/pre-rbac-migration-20251127 \
  --drop \
  --confirm
```

#### Seed Permissions and Roles
```bash
cd backend
python -m scripts.seed_permissions
# Output: ✅ 20 permissions created, ✅ 4 roles created
```

#### Migrate User Roles
```bash
cd backend
python -m scripts.migrate_user_roles
# Output: ✅ X users migrated
```

#### Validate RBAC Deployment
```bash
cd backend
python -m scripts.validate_rbac_deployment --environment production --verbose
# Output: ✅ All validations passed (12/12)
```

#### Automated Deployment
```bash
cd backend
./scripts/deploy_rbac.sh --environment staging

# Production with canary
./scripts/deploy_rbac.sh --environment production --canary-percent 10 --confirm
```

### From Backend Directory
```bash
cd backend
python scripts/script_name.py
```

### With Arguments
```bash
python scripts/seed_database.py --users 20 --cells 100
```

### With Virtual Environment
```bash
source venv/bin/activate
python scripts/script_name.py
```

## Testing Scripts

Scripts should be tested:
```python
# tests/test_scripts.py
import pytest
from scripts.seed_database import seed_users

def test_seed_users(mock_db):
    """Test user seeding."""
    seed_users(mock_db, count=5)
    assert mock_db.users.count() == 5
```

## Related Documentation

- [Backend App](../app/) - Application code
- [Backend Docs](../docs/) - Backend documentation
- [Test Architecture](../../docs/ARQUITETURA_TESTES.md) - Testing strategy

## Notes

- Keep scripts modular and reusable
- Use proper error handling
- Log operations for debugging
- Document script purpose and usage
- Test scripts before committing
- Technical names use English
- Comments may be in Portuguese
