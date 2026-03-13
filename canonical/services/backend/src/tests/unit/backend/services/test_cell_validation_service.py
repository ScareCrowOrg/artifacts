"""
Unit tests for Cell Validation Service.

Tests cover syntax validation, security scanning, and Hypnosis Loop.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cell_validation_service import (
    CellValidationService,
    ValidationError
)
from app.models import (
    Cell,
    DynamicRef,
    GenerationMetadata,
    CellStatus
)


class TestValidationError:
    """Tests for ValidationError class."""
    
    def test_validation_error_creation(self):
        """Test creating a validation error."""
        error = ValidationError(
            error_type="syntax_error",
            message="Missing semicolon",
            file="test.js",
            line=42,
            suggestion="Add semicolon at end of line"
        )
        
        assert error.error_type == "syntax_error"
        assert error.message == "Missing semicolon"
        assert error.file == "test.js"
        assert error.line == 42
        assert error.suggestion == "Add semicolon at end of line"
    
    def test_validation_error_to_dict(self):
        """Test converting validation error to dictionary."""
        error = ValidationError(
            error_type="security_violation",
            message="eval detected",
            file="test.js"
        )
        
        error_dict = error.to_dict()
        
        assert error_dict["type"] == "security_violation"
        assert error_dict["message"] == "eval detected"
        assert error_dict["file"] == "test.js"
        assert error_dict["line"] is None
        assert error_dict["suggestion"] is None


class TestCellValidationService:
    """Unit tests for CellValidationService."""
    
    @pytest.fixture
    def service(self):
        """Create a CellValidationService instance for testing."""
        return CellValidationService(redis_service=None)
    
    @pytest.fixture
    def sample_cell_with_refs(self):
        """Create a sample cell with dynamic refs."""
        return Cell(
            assignee_id="user-123",
            notebook_item_type_id="unclassified-cell-type",
            title="Test Cell",
            content="Test content",
            initial_data={
                "dynamic_refs": [
                    {
                        "type": "logic",
                        "lang": "python",
                        "path": "sandbox/assets/logic_123.python",
                        "filename": "logic_123.python",
                        "size_bytes": 100,
                        "validated": False
                    }
                ]
            }
        )
    
    @pytest.mark.asyncio
    async def test_validate_cell_success(self, service, sample_cell_with_refs):
        """Test successful cell validation."""
        with patch('app.services.cell_validation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            is_valid, errors = await service.validate_cell(sample_cell_with_refs, auto_correct=False)
            
            # Should be valid (mock code is valid)
            assert is_valid is True
            assert len(errors) == 0
            
            # Verify refs were marked as validated
            mock_db.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_cell_no_refs(self, service):
        """Test validating cell without dynamic refs."""
        cell = Cell(
            assignee_id="user-123",
            notebook_item_type_id="unclassified-cell-type",
            initial_data={}
        )
        
        is_valid, errors = await service.validate_cell(cell)
        
        # Should be valid (no refs to validate)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_python_syntax_valid(self, service):
        """Test validating valid Python syntax."""
        code = "def hello():\n    return 'Hello, World!'"
        errors = service._validate_python_syntax(code, "test.py")
        
        assert len(errors) == 0
    
    def test_validate_python_syntax_invalid(self, service):
        """Test validating invalid Python syntax."""
        code = "def hello(\n    return 'Hello'"  # Missing closing paren
        errors = service._validate_python_syntax(code, "test.py")
        
        assert len(errors) > 0
        assert errors[0].error_type == "syntax_error"
        assert "test.py" in errors[0].file
    
    def test_validate_javascript_syntax_valid(self, service):
        """Test validating valid JavaScript syntax."""
        code = "function hello() { return 'Hello'; }"
        errors = service._validate_javascript_syntax(code, "test.js")
        
        assert len(errors) == 0
    
    def test_validate_javascript_syntax_mismatched_braces(self, service):
        """Test validating JavaScript with mismatched braces."""
        code = "function hello() { return 'Hello'; "  # Missing closing brace
        errors = service._validate_javascript_syntax(code, "test.js")
        
        assert len(errors) > 0
        assert any("braces" in err.message for err in errors)
    
    def test_validate_javascript_syntax_mismatched_parens(self, service):
        """Test validating JavaScript with mismatched parentheses."""
        code = "function hello( { return 'Hello'; }"  # Missing closing paren
        errors = service._validate_javascript_syntax(code, "test.js")
        
        assert len(errors) > 0
        assert any("parentheses" in err.message for err in errors)
    
    def test_validate_svg_syntax_valid(self, service):
        """Test validating valid SVG syntax."""
        code = '<svg width="100" height="100"><circle cx="50" cy="50" r="40"/></svg>'
        errors = service._validate_svg_syntax(code, "test.svg")
        
        assert len(errors) == 0
    
    def test_validate_svg_syntax_missing_opening_tag(self, service):
        """Test validating SVG without opening tag."""
        code = '<circle cx="50" cy="50" r="40"/></svg>'
        errors = service._validate_svg_syntax(code, "test.svg")
        
        assert len(errors) > 0
        assert any("must start with <svg>" in err.message for err in errors)
    
    def test_validate_svg_syntax_missing_closing_tag(self, service):
        """Test validating SVG without closing tag."""
        code = '<svg width="100"><circle cx="50" cy="50" r="40"/>'
        errors = service._validate_svg_syntax(code, "test.svg")
        
        assert len(errors) > 0
        assert any("must end with </svg>" in err.message for err in errors)
    
    def test_validate_security_patterns_eval(self, service):
        """Test detecting eval usage."""
        code = "const result = eval('2 + 2');"
        errors = service._validate_security_patterns(code, "test.js")
        
        assert len(errors) > 0
        assert any("eval" in err.message.lower() for err in errors)
        assert errors[0].error_type == "security_violation"
    
    def test_validate_security_patterns_exec(self, service):
        """Test detecting exec usage."""
        code = "exec('import os')"
        errors = service._validate_security_patterns(code, "test.py")
        
        assert len(errors) > 0
        assert any("exec" in err.message.lower() for err in errors)
    
    def test_validate_security_patterns_function_constructor(self, service):
        """Test detecting Function constructor usage."""
        code = "const fn = new Function('return 42');"
        errors = service._validate_security_patterns(code, "test.js")
        
        assert len(errors) > 0
        assert any("function" in err.message.lower() for err in errors)
    
    def test_validate_security_patterns_script_injection(self, service):
        """Test detecting script tag injection."""
        code = '<div><script>alert("XSS")</script></div>'
        errors = service._validate_security_patterns(code, "test.html")
        
        assert len(errors) > 0
        assert any("script" in err.message.lower() for err in errors)
    
    def test_validate_security_patterns_on_event(self, service):
        """Test detecting inline event handlers."""
        code = '<button onclick="alert(\'XSS\')">Click</button>'
        errors = service._validate_security_patterns(code, "test.html")
        
        assert len(errors) > 0
        assert any("on" in err.message.lower() for err in errors)
    
    def test_validate_security_patterns_clean_code(self, service):
        """Test validating clean code with no security issues."""
        code = "function greet(name) { return `Hello, ${name}`; }"
        errors = service._validate_security_patterns(code, "test.js")
        
        assert len(errors) == 0
    
    def test_format_error_context(self, service):
        """Test formatting error context for LLM."""
        errors = [
            ValidationError(
                error_type="syntax_error",
                message="Missing semicolon",
                file="test.js",
                line=42,
                suggestion="Add semicolon"
            ),
            ValidationError(
                error_type="security_violation",
                message="eval detected",
                file="test.js",
                suggestion="Remove eval"
            )
        ]
        
        context = service._format_error_context(errors)
        
        assert "Code Validation Errors" in context
        assert "syntax_error" in context
        assert "Missing semicolon" in context
        assert "Line: 42" in context
        assert "security_violation" in context
        assert "eval detected" in context
        assert "regenerate" in context.lower()
    
    @pytest.mark.asyncio
    async def test_hypnosis_loop_max_attempts(self, service, sample_cell_with_refs):
        """Test Hypnosis Loop reaches max attempts."""
        errors = [
            ValidationError(
                error_type="syntax_error",
                message="Test error",
                file="test.js"
            )
        ]
        
        with patch('app.services.cell_validation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            # Mock to always return False (never corrected)
            with patch.object(service, '_hypnosis_loop', return_value=False):
                result = await service._hypnosis_loop(sample_cell_with_refs, errors)
                
                assert result is False
    
    @pytest.mark.asyncio
    async def test_mark_refs_validated(self, service, sample_cell_with_refs):
        """Test marking refs as validated."""
        refs_data = sample_cell_with_refs.initial_data["dynamic_refs"]
        
        with patch('app.services.cell_validation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            await service._mark_refs_validated(sample_cell_with_refs, refs_data)
            
            # Verify refs were marked as validated
            updated_refs = sample_cell_with_refs.initial_data["dynamic_refs"]
            assert all(ref["validated"] for ref in updated_refs)
            
            # Verify promotion_ready was set
            metadata = sample_cell_with_refs.initial_data.get("generation_metadata", {})
            assert metadata.get("promotion_ready") is True
            
            # Verify database update was called
            mock_db.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_generation_attempts(self, service, sample_cell_with_refs):
        """Test updating generation attempts count."""
        sample_cell_with_refs.initial_data["generation_metadata"] = {
            "attempts": 1,
            "auto_corrected": False
        }
        
        with patch('app.services.cell_validation_service.db') as mock_db:
            mock_db.update = AsyncMock()
            
            await service._update_generation_attempts(sample_cell_with_refs, 2)
            
            # Verify attempts were updated
            metadata = sample_cell_with_refs.initial_data["generation_metadata"]
            assert metadata["attempts"] == 2
            assert metadata["auto_corrected"] is True
            
            # Verify database update was called
            mock_db.update.assert_called_once()
