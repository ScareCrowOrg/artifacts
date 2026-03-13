"""
Schema loader and initialization for CanonicalQueryEngine.

Handles loading schemas from JSON files, validating them,
and initializing SQLite tables and indices.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict

from .exceptions import ValidationException

logger = logging.getLogger(__name__)


class SchemaLoader:
    """
    Schema loader for canonical collections.

    Loads, validates, and manages schemas from artifacts/canonical/SCHEMAS.json.
    """

    @staticmethod
    def load_schemas(schemas_path: Path = None) -> Dict:
        """
        Load schemas from artifacts/canonical/SCHEMAS.json.

        Args:
            schemas_path: Path to schema file (optional)

        Returns:
            Dictionary with schema definitions

        Raises:
            ValidationException: If schema file is invalid
        """
        if schemas_path is None:
            # Default path relative to project root
            current_dir = Path(__file__).resolve()
            project_root = current_dir.parent.parent.parent.parent.parent
            schemas_path = project_root / "artifacts" / "canonical" / "SCHEMAS.json"

        try:
            with open(schemas_path, "r") as f:
                schemas = json.load(f)
        except FileNotFoundError:
            raise ValidationException(
                f"Schema file not found: {schemas_path}",
                field="schemas_path",
                value=str(schemas_path),
            )
        except json.JSONDecodeError as e:
            raise ValidationException(
                f"Invalid JSON in schema file: {e}",
                field="schemas_path",
                value=str(schemas_path),
            )

        # Validate schema version
        if "version" not in schemas:
            raise ValidationException("Schema file missing 'version' field")

        if schemas["version"] != 1:
            raise ValidationException(
                f"Unsupported schema version: {schemas['version']}",
                field="version",
                value=schemas["version"],
            )

        logger.info("Loaded schemas from %s (version %s)", schemas_path, schemas['version'])
        return schemas

    @staticmethod
    def init_tables(conn: sqlite3.Connection, schemas: Dict):
        """
        Initialize SQLite tables for each collection from schemas.

        Args:
            conn: SQLite connection
            schemas: Schema dictionary

        Creates tables with columns and constraints defined in schema.
        """
        for collection_name, schema in schemas.items():
            # Skip metadata fields
            if collection_name in ["version", "description", "last_updated"]:
                continue

            # Build CREATE TABLE statement
            columns = []
            for field_name, field_spec in schema.items():
                col_def = f"{field_name} {field_spec['type']}"
                if "constraints" in field_spec:
                    col_def += f" {field_spec['constraints']}"
                columns.append(col_def)

            create_sql = f"""
                CREATE TABLE IF NOT EXISTS {collection_name} (
                    {", ".join(columns)}
                )
            """

            conn.execute(create_sql)
            logger.debug("Created table %s", collection_name)

        conn.commit()

    @staticmethod
    def create_indices(conn: sqlite3.Connection, schemas: Dict):
        """
        Create indices on critical fields for query performance.

        Args:
            conn: SQLite connection
            schemas: Schema dictionary

        Creates indices on fields marked with 'indexed': true in schema.
        """
        for collection_name, schema in schemas.items():
            # Skip metadata fields
            if collection_name in ["version", "description", "last_updated"]:
                continue

            for field_name, field_spec in schema.items():
                if field_spec.get("indexed", False):
                    index_name = f"idx_{collection_name}_{field_name}"
                    index_sql = f"""
                        CREATE INDEX IF NOT EXISTS {index_name}
                        ON {collection_name} ({field_name})
                    """
                    conn.execute(index_sql)
                    logger.debug("Created index %s", index_name)

        conn.commit()


__all__ = ["SchemaLoader"]
