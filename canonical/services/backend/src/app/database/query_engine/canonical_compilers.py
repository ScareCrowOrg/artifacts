"""
SQL Compilers for CanonicalQueryEngine.

This module provides SQL compilation functions for translating MongoDB
operators to SQLite SQL conditions. Separated from the main engine for
better modularity and maintainability.
"""

import json
from typing import Any, List


class SQLiteCompiler:
    """
    SQL compilation utilities for MongoDB operators.

    Provides static methods for compiling various MongoDB operators
    to SQLite SQL conditions.
    """

    @staticmethod
    def compile_in(field_accessor: str, values: List, escape_fn) -> str:
        """Compile $in operator."""
        if not values:
            return "1 = 0"  # Always false
        escaped_values = [escape_fn(v) for v in values]
        return f"{field_accessor} IN ({', '.join(escaped_values)})"

    @staticmethod
    def compile_nin(field_accessor: str, values: List, escape_fn) -> str:
        """Compile $nin operator."""
        if not values:
            return "1 = 1"  # Always true
        escaped_values = [escape_fn(v) for v in values]
        return f"{field_accessor} NOT IN ({', '.join(escaped_values)})"

    @staticmethod
    def compile_regex(field_accessor: str, pattern: str, escape_fn) -> str:
        """
        Compile $regex operator using SQLite LIKE.

        Converts MongoDB regex to SQLite LIKE pattern.
        """
        # Convert MongoDB regex to SQLite LIKE pattern
        like_pattern = pattern.replace("%", "\\%").replace("_", "\\_")
        like_pattern = f"%{like_pattern}%"
        return f"{field_accessor} LIKE {escape_fn(like_pattern)}"

    @staticmethod
    def compile_all(field_accessor: str, values: List, escape_fn) -> str:
        """
        Compile $all operator for arrays.

        Checks if JSON array contains all specified values.
        """
        conditions = []
        for value in values:
            # Check if array contains value
            conditions.append(
                (
                    f"EXISTS (SELECT 1 FROM json_each({field_accessor}) "
                    f"WHERE value = {escape_fn(value)})"
                )
            )
        return " AND ".join(conditions)

    @staticmethod
    def compile_elem_match(field_accessor: str, conditions: List[str]) -> str:
        """
        Compile $elemMatch operator for JSON arrays.

        Uses SQLite's json_each() to iterate array elements and match conditions.

        Args:
            field_accessor: SQL accessor for the array field
            conditions: List of SQL condition strings to match against array elements

        Returns:
            SQL condition string using EXISTS and json_each
        """
        if not conditions:
            # Empty conditions - match any non-empty array
            return f"json_array_length({field_accessor}) > 0"

        # Wrap conditions in EXISTS + json_each
        where_clause = " AND ".join(conditions)
        return (
            f"EXISTS (SELECT 1 FROM json_each({field_accessor}) WHERE {where_clause})"
        )

    @staticmethod
    def compile_exists(field: str, exists: bool, _field_type: str) -> str:
        """Compile $exists operator."""
        if "." in field:
            # Nested field in JSON
            parts = field.split(".")
            base_field = parts[0]
            json_path = "." + ".".join(parts[1:])

            if exists:
                return f"json_extract({base_field}, '${json_path}') IS NOT NULL"
            else:
                return f"json_extract({base_field}, '${json_path}') IS NULL"
        else:
            # Regular field
            if exists:
                return f"{field} IS NOT NULL"
            else:
                return f"{field} IS NULL"

    @staticmethod
    def compile_type(field_accessor: str, type_name: str) -> str:
        """
        Compile $type operator.

        Note: SQLite has limited type checking. Simplified implementation.
        """
        # Basic type checking using SQLite typeof()
        type_map = {
            "string": "text",
            "number": "real",
            "integer": "integer",
            "boolean": "integer",  # SQLite stores booleans as integers
            "null": "null",
        }

        sqlite_type = type_map.get(type_name, type_name)
        return f"typeof({field_accessor}) = '{sqlite_type}'"

    @staticmethod
    def compile_field_accessor(field: str, _field_type: str) -> str:
        """
        Compile field accessor for SQL, handling nested JSON fields.

        Args:
            field: Field name (may be nested like "metadata.level")
            field_type: Field type from schema

        Returns:
            SQL field accessor expression
        """
        if "." in field:
            # Nested field in JSON
            parts = field.split(".")
            base_field = parts[0]
            json_path = "." + ".".join(parts[1:])
            return f"json_extract({base_field}, '${json_path}')"
        else:
            return field

    @staticmethod
    def escape_value(value: Any) -> str:
        """
        Escape and format value for SQL query.

        Args:
            value: Python value to escape

        Returns:
            SQL-formatted value string
        """
        if value is None:
            return "NULL"

        if isinstance(value, bool):
            return "1" if value else "0"

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, str):
            # Escape single quotes
            escaped = value.replace("'", "''")
            return f"'{escaped}'"

        if isinstance(value, (list, tuple, dict)):
            # Convert to JSON string
            json_str = json.dumps(value)
            escaped = json_str.replace("'", "''")
            return f"'{escaped}'"

        # Default: convert to string and quote
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"


__all__ = ["SQLiteCompiler"]
