"""
Schema Generator - Auto-generate SCHEMAS.json from Pydantic models.

This module implements the "Pydantic as Source of Truth" pattern, eliminating
the need for manual SCHEMAS.json maintenance by introspecting Pydantic models
and generating SQLite schemas automatically.

Key Features:
- Uses Pydantic TypeAdapter for robust type introspection
- Maps Python types to SQLite types with proper constraints
- Extracts field descriptions from Pydantic Field()
- Generates JSON validation constraints for complex types
- Maintains compatibility with existing CanonicalQueryEngine

Architecture:
    SchemaGenerator
    ├── generate_schema() - Main entry point for single model
    ├── generate_all_schemas() - Generate all canonical collection schemas
    ├── _python_type_to_sqlite() - Type mapping logic
    ├── _extract_constraints() - Extract field constraints
    └── _extract_description() - Extract field descriptions

Usage:
    from app.database.schema_generator import SchemaGenerator
    from app.models.content import NotebookItemType

    generator = SchemaGenerator()
    schema = generator.generate_schema(NotebookItemType, collection_name="notebook_item_types")
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """
    Generator for SQLite schemas from Pydantic models.

    This class introspects Pydantic models and generates schema definitions
    compatible with CanonicalQueryEngine's SCHEMAS.json format.
    """

    def __init__(self):
        """Initialize the schema generator."""
        self.type_mapping = {
            str: "TEXT",
            int: "INTEGER",
            float: "REAL",
            bool: "INTEGER",  # SQLite uses INTEGER for boolean (0/1)
            datetime: "DATETIME",
            dict: "JSON",
            list: "JSON",
            Dict: "JSON",
            type(None): "NULL",
        }

    def generate_schema(
        self,
        model_class: Type[BaseModel],
        collection_name: str,
        primary_key_field: str = "id",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate SQLite schema definition from a Pydantic model.

        Args:
            model_class: Pydantic model class to introspect
            collection_name: Name of the collection (for logging)
            primary_key_field: Name of the primary key field (default: "id")

        Returns:
            Dictionary with schema definition in SCHEMAS.json format:
            {
                "_id": {
                    "type": "TEXT",
                    "constraints": "PRIMARY KEY",
                    "description": "Field description"
                },
                ...
            }
        """
        logger.info("Generating schema for %s from %s", collection_name, model_class.__name__)

        schema = {}
        model_fields = model_class.model_fields

        for field_name, field_info in model_fields.items():
            # Map 'id' to '_id' for consistency with MongoDB-like collections
            db_field_name = "_id" if field_name == primary_key_field else field_name

            # Extract Python type
            field_type = field_info.annotation

            # Map to SQLite type
            sqlite_type = self._python_type_to_sqlite(field_type)

            # Extract constraints
            constraints = self._extract_constraints(
                _field_name=field_name,
                field_info=field_info,
                field_type=field_type,
                is_primary_key=(field_name == primary_key_field),
            )

            # Extract description
            description = self._extract_description(field_info)

            # Build field schema
            field_schema = {"type": sqlite_type}

            # Note: JSON validation CHECK constraints removed because:
            # - Many JSON fields store string representations like 'null'
            # - SQLite's json_valid() is strict and rejects these patterns
            # - Data integrity is enforced by Pydantic on input, not at DB level
            # if sqlite_type == "JSON":
            #     json_check = f"CHECK (json_valid({db_field_name}))"
            #     if constraints:
            #         constraints = f"{constraints} {json_check}"
            #     else:
            #         constraints = json_check

            if constraints:
                field_schema["constraints"] = constraints

            if description:
                field_schema["description"] = description

            # Add indexing hints for commonly queried fields
            if self._should_be_indexed(field_name, field_type):
                field_schema["indexed"] = True

            schema[db_field_name] = field_schema

        logger.debug("Generated schema for %s: %s fields", collection_name, len(schema))
        return schema

    def _python_type_to_sqlite(self, python_type: Any) -> str:
        """
        Map Python type annotation to SQLite type.

        Handles:
        - Basic types (str, int, float, bool, datetime)
        - Optional types (Optional[T])
        - Collection types (Dict, List)
        - Union types
        - Enum types
        - Literal types
        - Pydantic BaseModel (nested models)
        - Any type (untyped complex data)

        Args:
            python_type: Python type annotation from Pydantic field

        Returns:
            SQLite type string ("TEXT", "INTEGER", "REAL", "JSON", etc.)
        """
        # Handle None type
        if python_type is type(None):
            return "NULL"

        # Handle Enum types - store as TEXT
        if isinstance(python_type, type) and issubclass(python_type, Enum):
            return "TEXT"

        # Handle Pydantic BaseModel - complex nested structures store as JSON
        try:
            if isinstance(python_type, type) and issubclass(python_type, BaseModel):
                return "JSON"
        except TypeError:
            # issubclass can fail on some type hints, ignore
            pass

        # Handle Any type - complex untyped data stores as JSON
        if python_type is Any:
            return "JSON"

        # Get origin and args for generic types
        origin = get_origin(python_type)
        args = get_args(python_type)

        # Handle Union types (including Optional which is Union[T, None])
        if origin is Union:
            # Filter out None from args
            non_none_args = [arg for arg in args if arg is not type(None)]
            if non_none_args:
                # Recursively process the first non-None type
                return self._python_type_to_sqlite(non_none_args[0])
            return "NULL"

        # Handle Literal types - store as TEXT
        if origin is Literal:
            return "TEXT"

        # Handle Dict types
        if origin is dict or python_type is dict:
            return "JSON"

        # Handle List types
        if origin is list or python_type is list:
            return "JSON"

        # Direct type mapping for base types
        if python_type in self.type_mapping:
            return self.type_mapping[python_type]

        # Handle complex types by checking string representation
        type_str = str(python_type)
        if "dict" in type_str.lower() or "Dict" in type_str:
            return "JSON"
        if "list" in type_str.lower() or "List" in type_str:
            return "JSON"

        # Default to TEXT for unknown types
        logger.debug("Type %s mapped to TEXT (no explicit mapping found)", python_type)
        return "TEXT"

    def _extract_constraints(
        self,
        _field_name: str,
        field_info: FieldInfo,
        field_type: Any,
        is_primary_key: bool = False,
    ) -> str:
        """
        Extract SQLite constraints from Pydantic field definition.

        Args:
            field_name: Name of the field
            field_info: Pydantic FieldInfo object
            field_type: Python type annotation
            is_primary_key: Whether this field is the primary key

        Returns:
            Constraint string (e.g., "PRIMARY KEY", "NOT NULL", "NOT NULL UNIQUE")
        """
        constraints = []

        # Primary key constraint
        if is_primary_key:
            constraints.append("PRIMARY KEY")
            return " ".join(constraints)  # Primary key implies NOT NULL

        # NOT NULL constraint (field is required and not Optional)
        is_optional = self._is_optional(field_type)
        is_required = field_info.is_required()

        if is_required and not is_optional:
            constraints.append("NOT NULL")

        # UNIQUE constraint (if specified in Field)
        # Note: Pydantic v2 doesn't have a built-in unique constraint
        # This would need custom metadata if required

        return " ".join(constraints) if constraints else ""

    def _is_optional(self, field_type: Any) -> bool:
        """
        Check if a type annotation is Optional.

        Args:
            field_type: Python type annotation

        Returns:
            True if type is Optional[T], False otherwise
        """
        origin = get_origin(field_type)
        if origin is Optional:
            return True

        # Check for Union[T, None] which is equivalent to Optional[T]
        args = get_args(field_type)
        if args and type(None) in args:
            return True

        return False

    def _extract_description(self, field_info: FieldInfo) -> str:
        """
        Extract field description from Pydantic Field definition.

        Args:
            field_info: Pydantic FieldInfo object

        Returns:
            Field description string, or empty string if none
        """
        return field_info.description or ""

    def _should_be_indexed(self, field_name: str, _field_type: Any) -> bool:
        """
        Determine if a field should be indexed for query performance.

        Common indexing patterns:
        - Foreign keys (*_id fields)
        - Status/state fields
        - Timestamp fields (created_at, updated_at)
        - Name fields (for searching)

        Args:
            field_name: Name of the field
            field_type: Python type annotation

        Returns:
            True if field should be indexed, False otherwise
        """
        # Index foreign key fields
        if field_name.endswith("_id") or field_name == "assignee_id":
            return True

        # Index common query fields
        indexed_patterns = [
            "status",
            "state",
            "kind",
            "type",
            "name",
            "created_at",
            "updated_at",
            "owner",
            "active",
            "visibility",
        ]

        if field_name in indexed_patterns:
            return True

        return False

    def generate_all_schemas(
        self,
        model_mapping: Dict[str, Type[BaseModel]],
        primary_key_overrides: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Generate schemas for all canonical collections.

        Args:
            model_mapping: Dictionary mapping collection names to Pydantic model classes
                Example: {
                    "notebook_item_types": NotebookItemType,
                    "cells": Cell,
                    ...
                }
            primary_key_overrides: Dictionary mapping collection names to custom primary key field names
                Example: {
                    "job_types": "name",
                    ...
                }
                If not provided, defaults to "id" for all collections.

        Returns:
            Complete schema dictionary in SCHEMAS.json format with metadata:
            {
                "version": 1,
                "description": "Auto-generated from Pydantic models",
                "last_updated": "2026-03-02",
                "notebook_item_types": {...},
                "cells": {...},
                ...
            }
        """
        if primary_key_overrides is None:
            primary_key_overrides = {}

        logger.info("Generating schemas for %s collections", len(model_mapping))

        schemas = {
            "version": 1,
            "description": (
                "AUTO-GENERATED from Pydantic models - DO NOT EDIT MANUALLY. "
                "Canonical collection schemas - source of truth for ScareVerse canonical data. "
                "To update schemas, modify Pydantic models and run: "
                "python scripts/generate_canonical_schemas.py"
            ),
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
        }

        for collection_name, model_class in model_mapping.items():
            try:
                # Use custom primary key if provided, otherwise default to "id"
                primary_key_field = primary_key_overrides.get(collection_name, "id")
                schema = self.generate_schema(
                    model_class,
                    collection_name,
                    primary_key_field=primary_key_field,
                )
                schemas[collection_name] = schema
                logger.info("✓ Generated schema for %s (primary_key: %s)", collection_name, primary_key_field)
            except Exception as e:
                logger.error("✗ Failed to generate schema for %s: %s", collection_name, e, exc_info=True)
                # Continue with other collections

        logger.info(
            f"Schema generation complete: {len(schemas) - 3} collections "
            "(excluding version/description/last_updated)"
        )
        return schemas


# Type hints for typing module compatibility
try:
    from typing import Dict, List
except ImportError:
    Dict = dict
    List = list


__all__ = ["SchemaGenerator"]
