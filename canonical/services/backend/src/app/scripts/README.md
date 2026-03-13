---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - architecture
  - database
  - services
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Utility Scripts

Utility and maintenance scripts for the ScareVerse backend. These scripts are used for database management, data migration, debugging, and system maintenance.

## Index

### Database Scripts
- `seed_data.py` - Database initialization and seed data
- `notebook_item_type_loader.py` - Helper module for loading NotebookItemType definitions from JSON
- `import_json_to_tinydb.py` - Import JSON data to TinyDB
- `dump_tinydb_contents.py` - Export TinyDB contents for debugging

### Data Migration
- (To be organized - currently in root)

### Debugging & Utilities
- `dump_refs_soft.py` - Dump software references
- `refs_soft_loader.py` - Load software reference data

## Script Conventions

### Structure
```python
#!/usr/bin/env python3
"""
Script description and usage.

Usage:
    python script_name.py [options]

Examples:
    python script_name.py --option value
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_database
from app.config import MONGODB_URI

def main():
    """Main script logic."""
    pass

if __name__ == "__main__":
    main()
```

### Best Practices
- Include docstring with usage instructions
- Add proper error handling and logging
- Use argparse for command-line arguments
- Provide dry-run mode for destructive operations
- Log actions and results
- Return appropriate exit codes

### Command-Line Arguments
```python
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Script description")
    parser.add_argument('--input', required=True, help='Input file path')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    return parser.parse_args()

def main():
    args = parse_args()
    if args.dry_run:
        print("DRY RUN: No changes will be made")
    # ... rest of logic
```

## Script Categories

### Database Scripts

#### seed_data.py
Seeds the database with initial/test data.

Loads canonical artifacts from:
- `artifacts/canonical/notebook_item_types/` - NotebookItemType definitions
- `artifacts/canonical/cell_types/` - Legacy cell type definitions (backward compatibility)
- `artifacts/canonical/books/` - Canonical book definitions
- `artifacts/canonical/ai_models/` - AI model definitions
- `artifacts/canonical/agent_types/` - Agent type definitions
- `artifacts/canonical/agents/` - Agent instance definitions

```bash
# Seed database with default data
python backend/app/scripts/seed_data.py

# Programmatic usage
from app.scripts.seed_data import init_seed_data
result = init_seed_data()
print(f"Seeded: {result}")
```

**Features**:
- Idempotent: Can be run multiple times without creating duplicates
- Loads from JSON files in canonical artifacts directories
- Supports both new and legacy formats
- Comprehensive logging of seed operations

**Current State**: Located in `backend/app/scripts/seed_data.py` (570 lines)
**Compliance**: ✓ Under 500-line limit after refactoring

#### notebook_item_type_loader.py
Helper module for loading NotebookItemType definitions from JSON files.

Provides utilities to load and process NotebookItemType definitions from the canonical
artifacts directory structure. Supports both new structured format (with `default_refs`
and `default_initial_data`) and legacy format (with `python_refs`, `workflows`, etc.).

```python
from app.scripts.notebook_item_type_loader import (
    load_notebook_item_types_from_directory,
    create_notebook_item_type_from_spec
)

# Load from directory
types = load_notebook_item_types_from_directory(Path("artifacts/canonical/notebook_item_types"))

# Create from spec
with open("my-type.json") as f:
    spec = json.load(f)
notebook_type = create_notebook_item_type_from_spec(spec)
```

**Functions**:
- `load_notebook_item_types_from_directory(directory)` - Load all types from a directory
- `create_notebook_item_type_from_spec(spec)` - Create a NotebookItemType from JSON spec

**Current State**: Located in `backend/app/scripts/notebook_item_type_loader.py` (171 lines)
**Compliance**: ✓ Under 500-line limit

#### import_json_to_tinydb.py
Imports JSON data into TinyDB database.

```bash
# Import data from JSON file
python backend/app/scripts/import_json_to_tinydb.py --input data.json
```

**Current State**: Located in `backend/app/import_json_to_tinydb.py`
**Action**: Move to `scripts/` directory

#### dump_tinydb_contents.py
Dumps TinyDB contents for debugging.

```bash
# Dump all TinyDB contents
python backend/app/scripts/dump_tinydb_contents.py

# Dump specific table
python backend/app/scripts/dump_tinydb_contents.py --table users
```

**Current State**: Located in `backend/app/dump_tinydb_contents.py`
**Action**: Move to `scripts/` directory

### Reference Data Scripts

#### refs_soft_loader.py
Loads software reference data.

**Current State**: Located in `backend/app/refs_soft_loader.py`
**Action**: Move to `scripts/` directory

#### dump_refs_soft.py
Dumps software references.

**Current State**: Located in `backend/app/dump_refs_soft.py`
**Action**: Move to `scripts/` directory

## Usage

### Running Scripts

```bash
# From project root
cd /home/runner/work/ScareVerseLab/ScareVerse

# Run script with Python
python3 backend/app/scripts/seed_data.py

# Make script executable (Unix/Linux)
chmod +x backend/app/scripts/seed_data.py
./backend/app/scripts/seed_data.py
```

### Environment Configuration

Scripts that require database access should load environment variables:

```python
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access configuration
mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
```

### Logging

Use Python's logging module:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("Starting script...")
logger.warning("Warning message")
logger.error("Error occurred")
```

## Testing

Scripts should have basic tests:

```python
# In tests/unit/backend/test_scripts.py
def test_seed_data_script():
    """Test seed_data script execution."""
    result = subprocess.run(
        ['python', 'backend/app/scripts/seed_data.py', '--dry-run'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
```

## Safety Guidelines

### Destructive Operations
Scripts that modify data should:
- Require explicit confirmation
- Provide dry-run mode
- Create backups before changes
- Log all operations
- Support rollback where possible

Example:
```python
def confirm_action(message: str) -> bool:
    """Ask user to confirm action."""
    response = input(f"{message} (y/N): ").lower()
    return response == 'y'

def main():
    if not args.force:
        if not confirm_action("This will delete all data. Continue?"):
            print("Aborted.")
            return
    # ... perform operation
```

### Data Validation
Validate input data before processing:
```python
def validate_json_file(filepath: Path) -> bool:
    """Validate JSON file before import."""
    try:
        with open(filepath) as f:
            data = json.load(f)
        # Validate schema
        required_keys = ['name', 'type', 'data']
        return all(key in data for key in required_keys)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {filepath}")
        return False
```

## Migration Plan

### Phase 5: Move Script Files
- [ ] Move `seed_data.py` to `scripts/`
- [ ] Move `import_json_to_tinydb.py` to `scripts/`
- [ ] Move `dump_tinydb_contents.py` to `scripts/`
- [ ] Move `dump_refs_soft.py` to `scripts/`
- [ ] Move `refs_soft_loader.py` to `scripts/`
- [ ] Update any imports or references
- [ ] Add shebang lines and make executable
- [ ] Update this README with complete documentation

## Related Documentation

- [Main Application](../README.md) - Backend application overview
- [Database Documentation](../database/README.md) - Database operations
- [Configuration Guide](../../docs/config/) - Environment configuration
- [Development Guide](../../docs/development/) - Development setup

## Notes

- Scripts should be idempotent where possible
- Use English for script names and functions
- Documentation and help text can be in Portuguese
- Maximum 500 lines per script (RULESET.md compliance)
- Always validate inputs and handle errors gracefully
