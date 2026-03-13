"""
Pytest configuration for scripts tests.

This conftest.py ensures that imports from backend/scripts work correctly
for all tests in tests/unit/scripts/.

The scripts directory is added to sys.path so that tests can import from
pipeline_monitoring and other script modules directly.
"""

import sys
from pathlib import Path

# Add backend/scripts to Python path
# This conftest is at backend/tests/unit/scripts/, so we go up 3 levels to backend/
backend_root = Path(__file__).parent.parent.parent.parent
scripts_dir = backend_root / "scripts"

if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

# Verify the path was added correctly
if not scripts_dir.exists():
    raise RuntimeError(f"Scripts directory not found: {scripts_dir}")
