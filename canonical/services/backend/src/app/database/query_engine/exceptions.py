"""
Custom exceptions for Query Engine.

This module defines exception classes for query engine operations,
following the ScareVerse exception pattern with i18n support.

Exception hierarchy:
    QueryEngineException (base)
    ├── InvalidQueryException (query syntax errors)
    ├── UnsupportedOperatorException (unsupported MongoDB operators)
    ├── ValidationException (query validation failures)
    └── CompilationException (SQL compilation errors)
"""

from typing import Any, Dict, Optional


class QueryEngineException(Exception):
    """
    Base exception for query engine operations.

    All query engine exceptions inherit from this class to enable
    consistent error handling and logging.

    Attributes:
        message: Technical error message (English)
        details: Additional error context
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize query engine exception.

        Args:
            message: Technical error message in English
            details: Additional context (e.g., {'operator': '$invalid'})
        """
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        """String representation with details."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class InvalidQueryException(QueryEngineException):
    """
    Exception raised when query syntax is invalid.

    This includes malformed queries, missing required fields,
    or invalid query structure.

    Examples:
        - Query is not a dictionary
        - Missing required operator
        - Nested query structure is invalid
    """

    def __init__(self, message: str, query: Optional[Dict] = None):
        """
        Initialize invalid query exception.

        Args:
            message: Description of what's invalid
            query: The invalid query for debugging
        """
        details = {"query": str(query)} if query else {}
        super().__init__(f"Invalid query: {message}", details)


class UnsupportedOperatorException(QueryEngineException):
    """
    Exception raised when an unsupported MongoDB operator is used.

    The query engine supports a subset of MongoDB operators.
    This exception is raised when a query uses an operator that
    hasn't been implemented yet.

    Examples:
        - Using $geoNear (not implemented)
        - Using $sample (not implemented)
        - Using custom operators
    """

    def __init__(self, operator: str, supported_operators: Optional[list] = None):
        """
        Initialize unsupported operator exception.

        Args:
            operator: The unsupported operator
            supported_operators: List of supported operators (optional)
        """
        message = f"Unsupported operator: {operator}"
        details = {"operator": operator}
        if supported_operators:
            details["supported_operators"] = supported_operators
            message += f". Supported operators: {', '.join(supported_operators)}"
        super().__init__(message, details)


class ValidationException(QueryEngineException):
    """
    Exception raised when query validation fails.

    This includes semantic validation errors, such as:
    - Invalid field names
    - Invalid value types
    - Security violations (SQL injection attempts)
    - Collection name validation failures

    Examples:
        - Field name contains SQL injection
        - Value type doesn't match operator
        - Collection name is reserved keyword
    """

    def __init__(
        self, message: str, field: Optional[str] = None, value: Optional[Any] = None
    ):
        """
        Initialize validation exception.

        Args:
            message: Description of validation failure
            field: The field that failed validation (optional)
            value: The invalid value (optional)
        """
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(f"Validation error: {message}", details)


class CompilationException(QueryEngineException):
    """
    Exception raised when query compilation to SQL fails.

    This includes errors during the translation process from
    MongoDB query syntax to SQL, such as:
    - Unable to generate SQL for operator
    - Template rendering failures
    - Complex nested query compilation errors

    Examples:
        - Missing required template variables
        - Circular reference in nested queries
        - Unable to resolve field mapping
    """

    def __init__(
        self,
        message: str,
        query: Optional[Dict] = None,
        partial_sql: Optional[str] = None,
    ):
        """
        Initialize compilation exception.

        Args:
            message: Description of compilation failure
            query: The query being compiled (optional)
            partial_sql: Partially compiled SQL (optional, for debugging)
        """
        details = {}
        if query:
            details["query"] = str(query)
        if partial_sql:
            details["partial_sql"] = partial_sql
        super().__init__(f"Compilation error: {message}", details)


# Export all exceptions
__all__ = [
    "QueryEngineException",
    "InvalidQueryException",
    "UnsupportedOperatorException",
    "ValidationException",
    "CompilationException",
]
