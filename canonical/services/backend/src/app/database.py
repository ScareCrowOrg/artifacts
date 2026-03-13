"""
JSON-based database facade for ScareVerse MVP1.

COMPATIBILITY LAYER: This module maintains backward compatibility by re-exporting
the modularized database components from the app.database package.

The database functionality has been split into multiple modules for better
maintainability and adherence to the 500-line file size limit (Rule 1.1).

For new code, prefer importing directly from app.database:
    from app.database import JSONDatabase, get_db_instance, db

This file exists to ensure existing imports continue to work:
    from app.database import JSONDatabase  # Still works
"""

from .database import JSONDatabase, db, get_db_instance

# Preserve module docstring for backwards compatibility
__doc__ = JSONDatabase.__doc__

# Export public API
__all__ = ["JSONDatabase", "get_db_instance", "db"]
