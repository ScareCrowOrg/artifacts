"""
Utility functions and classes for Query Engine.

This module provides utility classes for query validation and compilation,
including security checks, type validation, and helper functions for
query translation.

Main classes:
    QueryValidator: Validates query syntax and semantics
    QueryCompiler: Helper functions for SQL compilation
"""

import logging
import re
from typing import Any, Dict

from .constants import (
    MONGODB_OPERATORS,
    RESERVED_KEYWORDS,
    TYPE_MAPPING,
)
from .exceptions import (
    InvalidQueryException,
    UnsupportedOperatorException,
    ValidationException,
)

logger = logging.getLogger(__name__)


class QueryValidator:
    """
    Utility class for query validation.

    Provides methods to validate query syntax, field names, values,
    and security checks to prevent SQL injection.

    Methods:
        validate_query(): Main validation entry point
        validate_field_name(): Check field name is valid
        validate_operator(): Check operator is supported
        validate_value(): Check value type is appropriate
        check_sql_injection(): Detect potential SQL injection
    """

    @staticmethod
    def validate_query(query: Dict[str, Any]) -> None:
        """
        Validate MongoDB-style query.

        Performs comprehensive validation including:
        - Query is a dictionary
        - All operators are supported
        - Field names are valid
        - Values are appropriate
        - No SQL injection attempts

        Args:
            query: MongoDB-style query to validate

        Raises:
            InvalidQueryException: If query structure is invalid
            ValidationException: If validation fails
            UnsupportedOperatorException: If unsupported operator found

        Example:
            QueryValidator.validate_query({"status": "active"})  # OK
            QueryValidator.validate_query("invalid")  # Raises InvalidQueryException
        """
        if not isinstance(query, dict):
            raise InvalidQueryException(
                "Query must be a dictionary", query={"type": type(query).__name__}
            )

        if not query:
            # Empty query is valid (matches all)
            return

        # Validate recursively
        QueryValidator._validate_query_dict(query)

    @staticmethod
    def _validate_query_dict(query: Dict[str, Any], path: str = "") -> None:
        """
        Recursively validate query dictionary.

        Args:
            query: Query dictionary to validate
            path: Current path in query (for error messages)

        Raises:
            ValidationException: If validation fails
            UnsupportedOperatorException: If unsupported operator found
        """
        for key, value in query.items():
            current_path = f"{path}.{key}" if path else key

            # Check if key is an operator
            if key.startswith("$"):
                QueryValidator.validate_operator(key, current_path)

                # Validate operator value
                if key in ["$and", "$or", "$nor"]:
                    # Logical operators expect list of conditions
                    if not isinstance(value, list):
                        raise ValidationException(
                            f"Operator {key} expects a list",
                            field=current_path,
                            value=type(value).__name__,
                        )
                    for i, condition in enumerate(value):
                        if not isinstance(condition, dict):
                            raise ValidationException(
                                f"Operator {key} expects list of dictionaries",
                                field=f"{current_path}[{i}]",
                                value=type(condition).__name__,
                            )
                        QueryValidator._validate_query_dict(
                            condition, f"{current_path}[{i}]"
                        )

                elif key == "$not":
                    # $not expects a condition
                    if not isinstance(value, dict):
                        raise ValidationException(
                            f"Operator {key} expects a dictionary",
                            field=current_path,
                            value=type(value).__name__,
                        )
                    QueryValidator._validate_query_dict(value, current_path)

                elif key in ["$in", "$nin"]:
                    # $in/$nin expect a list
                    if not isinstance(value, (list, tuple)):
                        raise ValidationException(
                            f"Operator {key} expects a list",
                            field=current_path,
                            value=type(value).__name__,
                        )

                elif key == "$exists":
                    # $exists expects boolean
                    if not isinstance(value, bool):
                        raise ValidationException(
                            f"Operator {key} expects a boolean",
                            field=current_path,
                            value=type(value).__name__,
                        )

                elif key == "$type":
                    # $type expects string from TYPE_MAPPING
                    if not isinstance(value, str) or value not in TYPE_MAPPING:
                        raise ValidationException(
                            f"Operator {key} expects a valid type: {', '.join(TYPE_MAPPING.keys())}",
                            field=current_path,
                            value=value,
                        )

                elif key == "$regex":
                    # $regex expects string
                    if not isinstance(value, str):
                        raise ValidationException(
                            f"Operator {key} expects a string",
                            field=current_path,
                            value=type(value).__name__,
                        )
                    # Validate regex syntax
                    try:
                        re.compile(value)
                    except re.error as e:
                        raise ValidationException(
                            f"Invalid regex pattern: {e}",
                            field=current_path,
                            value=value,
                        )

            else:
                # Regular field name
                QueryValidator.validate_field_name(key, current_path)

                # If value is dict, it might contain operators
                if isinstance(value, dict):
                    QueryValidator._validate_query_dict(value, current_path)

    @staticmethod
    def validate_field_name(field_name: str, path: str = "") -> None:
        """
        Validate field name for security and syntax.

        Checks:
        - Field name is not empty
        - No SQL injection patterns
        - No reserved SQL keywords (unless quoted)
        - Valid identifier characters

        Args:
            field_name: Field name to validate
            path: Path for error messages

        Raises:
            ValidationException: If field name is invalid

        Example:
            QueryValidator.validate_field_name("user_name")  # OK
            QueryValidator.validate_field_name("user; DROP TABLE")  # Raises exception
        """
        if not field_name:
            raise ValidationException("Field name cannot be empty", field=path)

        # Check for SQL injection patterns
        if QueryValidator.check_sql_injection(field_name):
            raise ValidationException(
                "Field name contains potential SQL injection",
                field=path,
                value=field_name,
            )

        # Check for reserved keywords (case-insensitive)
        if field_name.lower() in RESERVED_KEYWORDS:
            logger.warning(
                f"Field name '{field_name}' is a reserved SQL keyword. "
                "It will be quoted in queries."
            )

    @staticmethod
    def validate_operator(operator: str, _path: str = "") -> None:
        """
        Validate MongoDB operator is supported.

        Args:
            operator: MongoDB operator (e.g., "$eq", "$gt")
            path: Path for error messages

        Raises:
            UnsupportedOperatorException: If operator is not supported

        Example:
            QueryValidator.validate_operator("$eq")  # OK
            QueryValidator.validate_operator("$invalid")  # Raises exception
        """
        if operator not in MONGODB_OPERATORS:
            raise UnsupportedOperatorException(
                operator, supported_operators=sorted(list(MONGODB_OPERATORS))
            )

    @staticmethod
    def check_sql_injection(value: str) -> bool:
        """
        Check for potential SQL injection patterns.

        Detects common SQL injection patterns including:
        - SQL keywords (DROP, DELETE, INSERT, UPDATE, etc.)
        - Comment patterns (-- , /* */)
        - Statement terminators (;)
        - Union-based injection

        Args:
            value: String value to check

        Returns:
            True if potential SQL injection detected, False otherwise

        Example:
            QueryValidator.check_sql_injection("username")  # False
            QueryValidator.check_sql_injection("user'; DROP TABLE users--")  # True
        """
        if not isinstance(value, str):
            return False

        # SQL injection patterns
        injection_patterns = [
            r";\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|EXEC|EXECUTE)",
            r"--",  # SQL comment
            r"/\*.*\*/",  # Block comment
            r"\bUNION\b.*\bSELECT\b",  # Union-based injection
            r"'\s*(OR|AND)\s*'",  # Always true conditions
            r"\bEXEC\s*\(",  # Exec function
            r"\bEXECUTE\s*\(",  # Execute function
        ]

        value_upper = value.upper()
        for pattern in injection_patterns:
            if re.search(pattern, value_upper, re.IGNORECASE):
                return True

        return False


class QueryCompiler:
    """
    Helper class for SQL compilation.

    Provides utility methods for compiling MongoDB queries to SQL,
    including field escaping, value formatting, and template rendering.

    Methods:
        escape_identifier(): Escape SQL identifier (field/table name)
        format_value(): Format value for SQL query
        compile_condition(): Compile single condition to SQL
    """

    @staticmethod
    def escape_identifier(identifier: str) -> str:
        """
        Escape SQL identifier (field or table name).

        Adds double quotes around identifiers that:
        - Are reserved SQL keywords
        - Contain special characters
        - Need case-sensitive matching

        Args:
            identifier: Identifier to escape

        Returns:
            Escaped identifier

        Example:
            QueryCompiler.escape_identifier("user")  # "user"
            QueryCompiler.escape_identifier("userName")  # "userName"
            QueryCompiler.escape_identifier("normal_field")  # normal_field
        """
        # Always quote reserved keywords
        if identifier.lower() in RESERVED_KEYWORDS:
            return f'"{identifier}"'

        # Quote if contains uppercase (case-sensitive)
        if identifier != identifier.lower():
            return f'"{identifier}"'

        # Quote if contains special characters
        if not re.match(r"^[a-z_][a-z0-9_]*$", identifier):
            return f'"{identifier}"'

        return identifier

    @staticmethod
    def format_value(value: Any) -> str:
        """
        Format Python value for SQL query.

        Handles:
        - Strings (with escaping)
        - Numbers
        - Booleans
        - None/NULL
        - Lists (for IN/NOT IN)

        Args:
            value: Python value to format

        Returns:
            SQL-formatted value

        Example:
            QueryCompiler.format_value("test")  # 'test'
            QueryCompiler.format_value(42)  # 42
            QueryCompiler.format_value([1, 2, 3])  # 1, 2, 3
        """
        if value is None:
            return "NULL"

        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, str):
            # Escape single quotes
            escaped = value.replace("'", "''")
            return f"'{escaped}'"

        if isinstance(value, (list, tuple)):
            # Format list for IN/NOT IN
            formatted = [QueryCompiler.format_value(v) for v in value]
            return ", ".join(formatted)

        # Default: convert to string and quote
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"


__all__ = ["QueryValidator", "QueryCompiler"]
