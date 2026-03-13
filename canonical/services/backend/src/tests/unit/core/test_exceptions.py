"""
Unit tests for core.exceptions module.

Tests all custom exception classes including:
- ScareVerseException base class
- Resource not found exceptions
- Validation exceptions
- Operation exceptions
- Authorization exceptions
- Server exceptions
"""

import pytest
from fastapi import HTTPException

from app.core.exceptions import (
    ScareVerseException,
    CellNotFoundException,
    BookNotFoundException,
    FragmentNotFoundException,
    ResourceNotFoundException,
    ValidationException,
    InvalidDataException,
    SaveFailedException,
    LoadFailedException,
    DeleteFailedException,
    UnauthorizedException,
    ForbiddenException,
    ServerException,
    NetworkException,
)


class TestScareVerseException:
    """Tests for the base ScareVerseException class."""
    
    def test_base_exception_with_all_parameters(self):
        """Test creating exception with all parameters."""
        exc = ScareVerseException(
            status_code=400,
            message="Test error message",
            i18n_key="errors.test",
            details={"field": "value"}
        )
        
        assert exc.status_code == 400
        assert exc.detail["message"] == "Test error message"
        assert exc.detail["i18n_key"] == "errors.test"
        assert exc.detail["details"]["field"] == "value"
    
    def test_base_exception_with_minimal_parameters(self):
        """Test creating exception with only required parameters."""
        exc = ScareVerseException(
            status_code=500,
            message="Minimal error"
        )
        
        assert exc.status_code == 500
        assert exc.detail["message"] == "Minimal error"
        assert exc.detail["i18n_key"] == "errors.generic"
        assert exc.detail["details"] == {}
    
    def test_base_exception_inherits_from_http_exception(self):
        """Test that ScareVerseException inherits from HTTPException."""
        exc = ScareVerseException(status_code=400, message="Test")
        assert isinstance(exc, HTTPException)


class TestResourceNotFoundExceptions:
    """Tests for resource not found exception classes."""
    
    def test_cell_not_found_exception(self):
        """Test CellNotFoundException structure and values."""
        cell_id = "cell-123"
        exc = CellNotFoundException(cell_id)
        
        assert exc.status_code == 404
        assert "Cell not found" in exc.detail["message"]
        assert cell_id in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.cellNotFound"
        assert exc.detail["details"]["cell_id"] == cell_id
    
    def test_book_not_found_exception(self):
        """Test BookNotFoundException structure and values."""
        book_id = "book-456"
        exc = BookNotFoundException(book_id)
        
        assert exc.status_code == 404
        assert "Book not found" in exc.detail["message"]
        assert book_id in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.bookNotFound"
        assert exc.detail["details"]["book_id"] == book_id
    
    def test_fragment_not_found_exception(self):
        """Test FragmentNotFoundException structure and values."""
        fragment_id = "fragment-789"
        exc = FragmentNotFoundException(fragment_id)
        
        assert exc.status_code == 404
        assert "Fragment not found" in exc.detail["message"]
        assert fragment_id in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.fragmentNotFound"
        assert exc.detail["details"]["fragment_id"] == fragment_id
    
    def test_resource_not_found_exception(self):
        """Test generic ResourceNotFoundException."""
        exc = ResourceNotFoundException("User", "user-999")
        
        assert exc.status_code == 404
        assert "User not found" in exc.detail["message"]
        assert "user-999" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.resourceNotFound"
        assert exc.detail["details"]["resource_type"] == "User"
        assert exc.detail["details"]["resource_id"] == "user-999"


class TestValidationExceptions:
    """Tests for validation exception classes."""
    
    def test_validation_exception_with_field(self):
        """Test ValidationException with field specified."""
        exc = ValidationException("Value must be positive", field="amount")
        
        assert exc.status_code == 400
        assert "Validation error" in exc.detail["message"]
        assert "Value must be positive" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.validationError"
        assert exc.detail["details"]["field"] == "amount"
        assert exc.detail["details"]["error"] == "Value must be positive"
    
    def test_validation_exception_without_field(self):
        """Test ValidationException without field."""
        exc = ValidationException("Invalid input format")
        
        assert exc.status_code == 400
        assert "Validation error" in exc.detail["message"]
        assert exc.detail["details"]["field"] is None
        assert exc.detail["details"]["error"] == "Invalid input format"
    
    def test_invalid_data_exception(self):
        """Test InvalidDataException structure."""
        exc = InvalidDataException("Data format not supported")
        
        assert exc.status_code == 400
        assert "Invalid data" in exc.detail["message"]
        assert "Data format not supported" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.invalidData"
        assert exc.detail["details"]["error"] == "Data format not supported"


class TestOperationExceptions:
    """Tests for operation exception classes."""
    
    def test_save_failed_exception_with_id(self):
        """Test SaveFailedException with entity ID."""
        exc = SaveFailedException("Cell", "cell-123")
        
        assert exc.status_code == 500
        assert "Failed to save Cell" in exc.detail["message"]
        assert "cell-123" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.saveFailed"
        assert exc.detail["details"]["entity_type"] == "Cell"
        assert exc.detail["details"]["entity_id"] == "cell-123"
    
    def test_save_failed_exception_without_id(self):
        """Test SaveFailedException without entity ID."""
        exc = SaveFailedException("Book")
        
        assert exc.status_code == 500
        assert "Failed to save Book" in exc.detail["message"]
        assert exc.detail["details"]["entity_type"] == "Book"
        assert exc.detail["details"]["entity_id"] is None
    
    def test_load_failed_exception_with_id(self):
        """Test LoadFailedException with entity ID."""
        exc = LoadFailedException("Fragment", "frag-456")
        
        assert exc.status_code == 500
        assert "Failed to load Fragment" in exc.detail["message"]
        assert "frag-456" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.loadFailed"
        assert exc.detail["details"]["entity_type"] == "Fragment"
        assert exc.detail["details"]["entity_id"] == "frag-456"
    
    def test_load_failed_exception_without_id(self):
        """Test LoadFailedException without entity ID."""
        exc = LoadFailedException("Session")
        
        assert exc.status_code == 500
        assert "Failed to load Session" in exc.detail["message"]
        assert exc.detail["details"]["entity_type"] == "Session"
        assert exc.detail["details"]["entity_id"] is None
    
    def test_delete_failed_exception(self):
        """Test DeleteFailedException structure."""
        exc = DeleteFailedException("User", "user-789")
        
        assert exc.status_code == 500
        assert "Failed to delete User" in exc.detail["message"]
        assert "user-789" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.deleteFailed"
        assert exc.detail["details"]["entity_type"] == "User"
        assert exc.detail["details"]["entity_id"] == "user-789"


class TestAuthorizationExceptions:
    """Tests for authorization exception classes."""
    
    def test_unauthorized_exception_default_message(self):
        """Test UnauthorizedException with default message."""
        exc = UnauthorizedException()
        
        assert exc.status_code == 401
        assert exc.detail["message"] == "Authentication required"
        assert exc.detail["i18n_key"] == "errors.unauthorized"
    
    def test_unauthorized_exception_custom_message(self):
        """Test UnauthorizedException with custom message."""
        exc = UnauthorizedException("Invalid token")
        
        assert exc.status_code == 401
        assert exc.detail["message"] == "Invalid token"
        assert exc.detail["i18n_key"] == "errors.unauthorized"
    
    def test_forbidden_exception_default_message(self):
        """Test ForbiddenException with default message."""
        exc = ForbiddenException()
        
        assert exc.status_code == 403
        assert exc.detail["message"] == "Access denied"
        assert exc.detail["i18n_key"] == "errors.forbidden"
    
    def test_forbidden_exception_custom_message(self):
        """Test ForbiddenException with custom message."""
        exc = ForbiddenException("Insufficient permissions")
        
        assert exc.status_code == 403
        assert exc.detail["message"] == "Insufficient permissions"
        assert exc.detail["i18n_key"] == "errors.forbidden"


class TestServerExceptions:
    """Tests for server exception classes."""
    
    def test_server_exception(self):
        """Test ServerException structure."""
        exc = ServerException("Database connection failed")
        
        assert exc.status_code == 500
        assert "Internal server error" in exc.detail["message"]
        assert "Database connection failed" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.serverError"
        assert exc.detail["details"]["error"] == "Database connection failed"
    
    def test_network_exception(self):
        """Test NetworkException structure."""
        exc = NetworkException("Connection timeout")
        
        assert exc.status_code == 503
        assert "Network error" in exc.detail["message"]
        assert "Connection timeout" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.networkError"
        assert exc.detail["details"]["error"] == "Connection timeout"


class TestExceptionEdgeCases:
    """Tests for edge cases and special scenarios."""
    
    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        exc = ScareVerseException(status_code=400, message="")
        assert exc.detail["message"] == ""
        assert exc.detail["i18n_key"] == "errors.generic"
    
    def test_exception_with_special_characters(self):
        """Test exception with special characters in message."""
        message = "Error: <script>alert('xss')</script>"
        exc = ScareVerseException(status_code=400, message=message)
        assert exc.detail["message"] == message
    
    def test_exception_with_unicode_characters(self):
        """Test exception with unicode characters."""
        exc = ValidationException("El valor debe ser numérico ñáéíóú")
        assert "numérico" in exc.detail["message"]
        assert "ñáéíóú" in exc.detail["message"]
    
    def test_exception_details_with_nested_dict(self):
        """Test exception with nested dictionary in details."""
        details = {
            "user": {
                "id": "123",
                "roles": ["admin", "user"]
            },
            "action": "delete"
        }
        exc = ScareVerseException(
            status_code=403,
            message="Action not allowed",
            details=details
        )
        assert exc.detail["details"]["user"]["id"] == "123"
        assert "admin" in exc.detail["details"]["user"]["roles"]
        assert exc.detail["details"]["action"] == "delete"
