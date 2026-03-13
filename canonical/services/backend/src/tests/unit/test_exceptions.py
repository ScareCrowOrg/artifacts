"""
Unit tests for custom exception classes.

Tests exception creation, i18n support, and proper HTTP status codes.
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
    """Tests for base exception class."""
    
    def test_base_exception_creation(self):
        """Test creating base ScareVerseException."""
        exc = ScareVerseException(
            status_code=400,
            message="Test error",
            i18n_key="errors.test",
            details={"key": "value"}
        )
        
        assert exc.status_code == 400
        assert exc.detail["message"] == "Test error"
        assert exc.detail["i18n_key"] == "errors.test"
        assert exc.detail["details"]["key"] == "value"
    
    def test_base_exception_default_i18n_key(self):
        """Test base exception uses default i18n key when not provided."""
        exc = ScareVerseException(
            status_code=500,
            message="Test error"
        )
        
        assert exc.detail["i18n_key"] == "errors.generic"
    
    def test_base_exception_default_details(self):
        """Test base exception uses empty dict for details when not provided."""
        exc = ScareVerseException(
            status_code=500,
            message="Test error"
        )
        
        assert exc.detail["details"] == {}
    
    def test_base_exception_is_http_exception(self):
        """Test that ScareVerseException is an HTTPException."""
        exc = ScareVerseException(
            status_code=400,
            message="Test error"
        )
        
        assert isinstance(exc, HTTPException)


class TestResourceNotFoundExceptions:
    """Tests for resource not found exceptions."""
    
    def test_cell_not_found_exception(self):
        """Test CellNotFoundException."""
        exc = CellNotFoundException(cell_id="cell-123")
        
        assert exc.status_code == 404
        assert "cell-123" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.cellNotFound"
        assert exc.detail["details"]["cell_id"] == "cell-123"
    
    def test_book_not_found_exception(self):
        """Test BookNotFoundException."""
        exc = BookNotFoundException(book_id="book-456")
        
        assert exc.status_code == 404
        assert "book-456" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.bookNotFound"
        assert exc.detail["details"]["book_id"] == "book-456"
    
    def test_fragment_not_found_exception(self):
        """Test FragmentNotFoundException."""
        exc = FragmentNotFoundException(fragment_id="fragment-789")
        
        assert exc.status_code == 404
        assert "fragment-789" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.fragmentNotFound"
        assert exc.detail["details"]["fragment_id"] == "fragment-789"
    
    def test_resource_not_found_exception(self):
        """Test generic ResourceNotFoundException."""
        exc = ResourceNotFoundException(
            resource_type="user",
            resource_id="user-123"
        )
        
        assert exc.status_code == 404
        assert "user" in exc.detail["message"]
        assert "user-123" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.resourceNotFound"
        assert exc.detail["details"]["resource_type"] == "user"
        assert exc.detail["details"]["resource_id"] == "user-123"
    
    def test_resource_not_found_with_different_types(self):
        """Test ResourceNotFoundException with various resource types."""
        resource_types = ["session", "permission", "role", "config"]
        
        for resource_type in resource_types:
            exc = ResourceNotFoundException(
                resource_type=resource_type,
                resource_id="test-id"
            )
            
            assert exc.status_code == 404
            assert resource_type in exc.detail["message"]


class TestValidationExceptions:
    """Tests for validation exceptions."""
    
    def test_validation_exception_with_field(self):
        """Test ValidationException with field name."""
        exc = ValidationException(
            message="Invalid email format",
            field="email"
        )
        
        assert exc.status_code == 400
        assert "Invalid email format" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.validationError"
        assert exc.detail["details"]["field"] == "email"
        assert exc.detail["details"]["error"] == "Invalid email format"
    
    def test_validation_exception_without_field(self):
        """Test ValidationException without field name."""
        exc = ValidationException(message="Invalid data")
        
        assert exc.status_code == 400
        assert exc.detail["details"]["field"] is None
    
    def test_invalid_data_exception(self):
        """Test InvalidDataException."""
        exc = InvalidDataException(message="Data must be JSON")
        
        assert exc.status_code == 400
        assert "Data must be JSON" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.invalidData"
        assert exc.detail["details"]["error"] == "Data must be JSON"
    
    def test_validation_different_messages(self):
        """Test validation exceptions with various error messages."""
        messages = [
            "Field is required",
            "Value must be positive",
            "Invalid format",
            "Length exceeds maximum"
        ]
        
        for message in messages:
            exc = ValidationException(message=message)
            assert message in exc.detail["message"]


class TestOperationExceptions:
    """Tests for operation failure exceptions."""
    
    def test_save_failed_exception_with_id(self):
        """Test SaveFailedException with entity ID."""
        exc = SaveFailedException(
            entity_type="cell",
            entity_id="cell-123"
        )
        
        assert exc.status_code == 500
        assert "cell" in exc.detail["message"]
        assert "cell-123" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.saveFailed"
        assert exc.detail["details"]["entity_type"] == "cell"
        assert exc.detail["details"]["entity_id"] == "cell-123"
    
    def test_save_failed_exception_without_id(self):
        """Test SaveFailedException without entity ID."""
        exc = SaveFailedException(entity_type="book")
        
        assert exc.status_code == 500
        assert "book" in exc.detail["message"]
        assert exc.detail["details"]["entity_id"] is None
    
    def test_load_failed_exception_with_id(self):
        """Test LoadFailedException with entity ID."""
        exc = LoadFailedException(
            entity_type="fragment",
            entity_id="fragment-456"
        )
        
        assert exc.status_code == 500
        assert "fragment" in exc.detail["message"]
        assert "fragment-456" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.loadFailed"
        assert exc.detail["details"]["entity_type"] == "fragment"
        assert exc.detail["details"]["entity_id"] == "fragment-456"
    
    def test_load_failed_exception_without_id(self):
        """Test LoadFailedException without entity ID."""
        exc = LoadFailedException(entity_type="user")
        
        assert exc.status_code == 500
        assert exc.detail["details"]["entity_id"] is None
    
    def test_delete_failed_exception(self):
        """Test DeleteFailedException."""
        exc = DeleteFailedException(
            entity_type="session",
            entity_id="session-789"
        )
        
        assert exc.status_code == 500
        assert "session" in exc.detail["message"]
        assert "session-789" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.deleteFailed"
        assert exc.detail["details"]["entity_type"] == "session"
        assert exc.detail["details"]["entity_id"] == "session-789"
    
    def test_operation_exceptions_different_entity_types(self):
        """Test operation exceptions with various entity types."""
        entity_types = ["cell", "book", "fragment", "user", "session", "config"]
        
        for entity_type in entity_types:
            save_exc = SaveFailedException(entity_type=entity_type, entity_id="test-id")
            load_exc = LoadFailedException(entity_type=entity_type, entity_id="test-id")
            delete_exc = DeleteFailedException(entity_type=entity_type, entity_id="test-id")
            
            assert entity_type in save_exc.detail["message"]
            assert entity_type in load_exc.detail["message"]
            assert entity_type in delete_exc.detail["message"]


class TestAuthorizationExceptions:
    """Tests for authorization exceptions."""
    
    def test_unauthorized_exception_default_message(self):
        """Test UnauthorizedException with default message."""
        exc = UnauthorizedException()
        
        assert exc.status_code == 401
        assert "Authentication required" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.unauthorized"
    
    def test_unauthorized_exception_custom_message(self):
        """Test UnauthorizedException with custom message."""
        exc = UnauthorizedException(message="Invalid token")
        
        assert exc.status_code == 401
        assert "Invalid token" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.unauthorized"
    
    def test_forbidden_exception_default_message(self):
        """Test ForbiddenException with default message."""
        exc = ForbiddenException()
        
        assert exc.status_code == 403
        assert "Access denied" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.forbidden"
    
    def test_forbidden_exception_custom_message(self):
        """Test ForbiddenException with custom message."""
        exc = ForbiddenException(message="Admin access required")
        
        assert exc.status_code == 403
        assert "Admin access required" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.forbidden"
    
    def test_unauthorized_vs_forbidden(self):
        """Test distinction between 401 and 403 errors."""
        unauthorized = UnauthorizedException()
        forbidden = ForbiddenException()
        
        assert unauthorized.status_code == 401
        assert forbidden.status_code == 403
        assert unauthorized.detail["i18n_key"] != forbidden.detail["i18n_key"]


class TestServerExceptions:
    """Tests for server error exceptions."""
    
    def test_server_exception(self):
        """Test ServerException."""
        exc = ServerException(message="Database connection failed")
        
        assert exc.status_code == 500
        assert "Database connection failed" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.serverError"
        assert exc.detail["details"]["error"] == "Database connection failed"
    
    def test_network_exception(self):
        """Test NetworkException."""
        exc = NetworkException(message="Timeout connecting to external API")
        
        assert exc.status_code == 503
        assert "Timeout connecting to external API" in exc.detail["message"]
        assert exc.detail["i18n_key"] == "errors.networkError"
        assert exc.detail["details"]["error"] == "Timeout connecting to external API"
    
    def test_server_vs_network_status_codes(self):
        """Test distinction between 500 and 503 errors."""
        server_exc = ServerException(message="Internal error")
        network_exc = NetworkException(message="Network error")
        
        assert server_exc.status_code == 500
        assert network_exc.status_code == 503


class TestExceptionI18nSupport:
    """Tests for i18n key support in exceptions."""
    
    def test_all_exceptions_have_i18n_keys(self):
        """Test that all exceptions provide i18n keys."""
        exceptions = [
            CellNotFoundException("cell-123"),
            BookNotFoundException("book-123"),
            FragmentNotFoundException("fragment-123"),
            ResourceNotFoundException("user", "user-123"),
            ValidationException("error"),
            InvalidDataException("error"),
            SaveFailedException("cell", "cell-123"),
            LoadFailedException("book", "book-123"),
            DeleteFailedException("fragment", "fragment-123"),
            UnauthorizedException(),
            ForbiddenException(),
            ServerException("error"),
            NetworkException("error"),
        ]
        
        for exc in exceptions:
            assert "i18n_key" in exc.detail
            assert exc.detail["i18n_key"] is not None
            assert exc.detail["i18n_key"].startswith("errors.")
    
    def test_i18n_keys_are_unique(self):
        """Test that different exception types have different i18n keys."""
        exceptions = [
            (CellNotFoundException("id"), "errors.cellNotFound"),
            (BookNotFoundException("id"), "errors.bookNotFound"),
            (FragmentNotFoundException("id"), "errors.fragmentNotFound"),
            (ValidationException("msg"), "errors.validationError"),
            (UnauthorizedException(), "errors.unauthorized"),
            (ForbiddenException(), "errors.forbidden"),
            (ServerException("msg"), "errors.serverError"),
            (NetworkException("msg"), "errors.networkError"),
        ]
        
        for exc, expected_key in exceptions:
            assert exc.detail["i18n_key"] == expected_key


class TestExceptionDetails:
    """Tests for exception detail structures."""
    
    def test_exception_detail_structure(self):
        """Test that all exceptions have consistent detail structure."""
        exc = CellNotFoundException("cell-123")
        
        assert "message" in exc.detail
        assert "i18n_key" in exc.detail
        assert "details" in exc.detail
        assert isinstance(exc.detail["message"], str)
        assert isinstance(exc.detail["i18n_key"], str)
        assert isinstance(exc.detail["details"], dict)
    
    def test_exception_details_contain_context(self):
        """Test that exception details contain relevant context."""
        # Test with ID
        exc1 = CellNotFoundException("cell-123")
        assert "cell_id" in exc1.detail["details"]
        
        # Test with multiple fields
        exc2 = ResourceNotFoundException("user", "user-456")
        assert "resource_type" in exc2.detail["details"]
        assert "resource_id" in exc2.detail["details"]
        
        # Test with custom details
        exc3 = ValidationException("error", field="email")
        assert "field" in exc3.detail["details"]
        assert "error" in exc3.detail["details"]
    
    def test_exception_messages_are_descriptive(self):
        """Test that exception messages are descriptive."""
        exceptions_with_expected_content = [
            (CellNotFoundException("cell-123"), ["Cell", "not found", "cell-123"]),
            (ValidationException("Invalid format"), ["Validation error", "Invalid format"]),
            (SaveFailedException("book", "book-456"), ["Failed to save", "book", "book-456"]),
            (UnauthorizedException("Token expired"), ["Token expired"]),
        ]
        
        for exc, expected_terms in exceptions_with_expected_content:
            message = exc.detail["message"]
            for term in expected_terms:
                assert term in message, f"Expected '{term}' in message: {message}"


class TestExceptionUsagePatterns:
    """Tests for common exception usage patterns."""
    
    def test_exception_can_be_raised(self):
        """Test that exceptions can be raised properly."""
        with pytest.raises(CellNotFoundException):
            raise CellNotFoundException("cell-123")
    
    def test_exception_can_be_caught_as_http_exception(self):
        """Test that exceptions can be caught as HTTPException."""
        try:
            raise CellNotFoundException("cell-123")
        except HTTPException as e:
            assert e.status_code == 404
    
    def test_exception_can_be_caught_as_base_exception(self):
        """Test that exceptions can be caught as ScareVerseException."""
        try:
            raise CellNotFoundException("cell-123")
        except ScareVerseException as e:
            assert e.status_code == 404
    
    def test_multiple_exception_types_can_be_distinguished(self):
        """Test that different exception types can be distinguished."""
        try:
            raise CellNotFoundException("cell-123")
        except CellNotFoundException:
            caught_cell = True
        except BookNotFoundException:
            caught_cell = False
        
        assert caught_cell is True
        
        try:
            raise BookNotFoundException("book-456")
        except CellNotFoundException:
            caught_book = False
        except BookNotFoundException:
            caught_book = True
        
        assert caught_book is True
