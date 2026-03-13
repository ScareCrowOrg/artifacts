"""
Custom exceptions for ScareVerse API with i18n support.

This module defines exception classes that include i18n keys for frontend localization.
Technical error messages remain in English in logs and API responses,
while i18n keys enable frontend to display localized user messages.

All technical terms (parameters, class names, attributes) are in English.
User-facing messages are localized via i18n keys.
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException


class ScareVerseException(HTTPException):
    """
    Base exception class with i18n support.

    All ScareVerse exceptions should inherit from this class to ensure
    consistent error responses with i18n keys for frontend localization.

    Attributes:
        status_code: HTTP status code
        message: Technical error message (English, for logs and debugging)
        i18n_key: Translation key for frontend localization
        details: Additional error details/context
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        i18n_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize ScareVerse exception.

        Args:
            status_code: HTTP status code (e.g., 404, 400, 500)
            message: Technical error message in English
            i18n_key: Translation key (e.g., 'errors.cellNotFound')
            details: Additional context (e.g., {'cell_id': 'abc123'})
        """
        detail = {
            "message": message,
            "i18n_key": i18n_key or "errors.generic",
            "details": details or {},
        }
        super().__init__(status_code=status_code, detail=detail)


# === Resource Not Found Exceptions ===


class CellNotFoundException(ScareVerseException):
    """Exception raised when a cell is not found."""

    def __init__(self, cell_id: str):
        super().__init__(
            status_code=404,
            message=f"Cell not found: {cell_id}",
            i18n_key="errors.cellNotFound",
            details={"cell_id": cell_id},
        )


class BookNotFoundException(ScareVerseException):
    """Exception raised when a book is not found."""

    def __init__(self, book_id: str):
        super().__init__(
            status_code=404,
            message=f"Book not found: {book_id}",
            i18n_key="errors.bookNotFound",
            details={"book_id": book_id},
        )


class FragmentNotFoundException(ScareVerseException):
    """Exception raised when a fragment is not found."""

    def __init__(self, fragment_id: str):
        super().__init__(
            status_code=404,
            message=f"Fragment not found: {fragment_id}",
            i18n_key="errors.fragmentNotFound",
            details={"fragment_id": fragment_id},
        )


class ResourceNotFoundException(ScareVerseException):
    """Generic resource not found exception."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            status_code=404,
            message=f"{resource_type} not found: {resource_id}",
            i18n_key="errors.resourceNotFound",
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


# === Validation Exceptions ===


class ValidationException(ScareVerseException):
    """Exception raised when validation fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            status_code=400,
            message=f"Validation error: {message}",
            i18n_key="errors.validationError",
            details={"field": field, "error": message},
        )


class InvalidDataException(ScareVerseException):
    """Exception raised when data is invalid."""

    def __init__(self, message: str):
        super().__init__(
            status_code=400,
            message=f"Invalid data: {message}",
            i18n_key="errors.invalidData",
            details={"error": message},
        )


# === Operation Exceptions ===


class SaveFailedException(ScareVerseException):
    """Exception raised when save operation fails."""

    def __init__(self, entity_type: str, entity_id: Optional[str] = None):
        super().__init__(
            status_code=500,
            message=f"Failed to save {entity_type}"
            + (f": {entity_id}" if entity_id else ""),
            i18n_key="errors.saveFailed",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class LoadFailedException(ScareVerseException):
    """Exception raised when load operation fails."""

    def __init__(self, entity_type: str, entity_id: Optional[str] = None):
        super().__init__(
            status_code=500,
            message=f"Failed to load {entity_type}"
            + (f": {entity_id}" if entity_id else ""),
            i18n_key="errors.loadFailed",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class DeleteFailedException(ScareVerseException):
    """Exception raised when delete operation fails."""

    def __init__(self, entity_type: str, entity_id: str):
        super().__init__(
            status_code=500,
            message=f"Failed to delete {entity_type}: {entity_id}",
            i18n_key="errors.deleteFailed",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


# === Authorization Exceptions ===


class UnauthorizedException(ScareVerseException):
    """Exception raised when user is not authenticated."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            status_code=401, message=message, i18n_key="errors.unauthorized"
        )


class ForbiddenException(ScareVerseException):
    """Exception raised when user lacks permission."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(status_code=403, message=message, i18n_key="errors.forbidden")


# === Server Exceptions ===


class ServerException(ScareVerseException):
    """Exception raised for internal server errors."""

    def __init__(self, message: str):
        super().__init__(
            status_code=500,
            message=f"Internal server error: {message}",
            i18n_key="errors.serverError",
            details={"error": message},
        )


class NetworkException(ScareVerseException):
    """Exception raised for network-related errors."""

    def __init__(self, message: str):
        super().__init__(
            status_code=503,
            message=f"Network error: {message}",
            i18n_key="errors.networkError",
            details={"error": message},
        )
