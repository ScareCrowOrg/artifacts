"""
Unit tests for log-toggle-cell backend main module.
"""

import sys
from pathlib import Path
import pytest

# Add the cell's backend scripts directory to Python path
cell_backend_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(cell_backend_path))

from main import (
    execute_cell,
    get_available_namespaces,
    validate_namespace
)


class TestExecuteCell:
    """Test execute_cell function."""
    
    def test_execute_cell_with_empty_namespaces(self):
        """Test execution with no enabled namespaces."""
        cell_data = {
            'enabled_namespaces': [],
            'debug_pattern': ''
        }
        
        result = execute_cell(cell_data)
        
        assert result['success'] is True
        assert result['current_pattern'] == ''
        assert result['enabled_namespaces'] == []
        assert 'No logs enabled' in result['message']
    
    def test_execute_cell_with_namespaces(self):
        """Test execution with multiple enabled namespaces."""
        cell_data = {
            'enabled_namespaces': ['auth', 'api', 'store'],
            'debug_pattern': ''
        }
        
        result = execute_cell(cell_data)
        
        assert result['success'] is True
        assert result['current_pattern'] == 'auth,api,store'
        assert result['enabled_namespaces'] == ['auth', 'api', 'store']
        assert 'auth,api,store' in result['message']
    
    def test_execute_cell_with_wildcard_namespace(self):
        """Test execution with wildcard namespace."""
        cell_data = {
            'enabled_namespaces': ['auth:*'],
            'debug_pattern': ''
        }
        
        result = execute_cell(cell_data)
        
        assert result['success'] is True
        assert result['current_pattern'] == 'auth:*'
        assert result['enabled_namespaces'] == ['auth:*']
    
    def test_execute_cell_with_existing_pattern(self):
        """Test execution when debug_pattern is already set."""
        cell_data = {
            'enabled_namespaces': ['auth', 'api'],
            'debug_pattern': 'store'  # Should be overridden
        }
        
        result = execute_cell(cell_data)
        
        # Namespaces take precedence over existing pattern
        assert result['current_pattern'] == 'auth,api'
    
    def test_execute_cell_with_missing_keys(self):
        """Test execution with missing cell_data keys."""
        cell_data = {}
        
        result = execute_cell(cell_data)
        
        assert result['success'] is True
        assert result['current_pattern'] == ''
        assert result['enabled_namespaces'] == []


class TestGetAvailableNamespaces:
    """Test get_available_namespaces function."""
    
    def test_returns_list(self):
        """Test that function returns a list."""
        result = get_available_namespaces()
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_returns_expected_namespaces(self):
        """Test that expected namespaces are present."""
        result = get_available_namespaces()
        
        expected = ['app', 'auth', 'api', 'store', 'router']
        
        for namespace in expected:
            assert namespace in result
    
    def test_namespaces_are_strings(self):
        """Test that all namespaces are strings."""
        result = get_available_namespaces()
        
        for namespace in result:
            assert isinstance(namespace, str)
            assert len(namespace) > 0


class TestValidateNamespace:
    """Test validate_namespace function."""
    
    def test_valid_simple_namespace(self):
        """Test validation of simple namespace."""
        assert validate_namespace('auth') is True
        assert validate_namespace('api') is True
        assert validate_namespace('store') is True
    
    def test_valid_nested_namespace(self):
        """Test validation of nested namespace."""
        assert validate_namespace('auth:login') is True
        assert validate_namespace('api:cells') is True
        assert validate_namespace('store:books') is True
    
    def test_valid_wildcard_namespace(self):
        """Test validation of wildcard namespace."""
        assert validate_namespace('auth:*') is True
        assert validate_namespace('*') is True
    
    def test_valid_with_hyphens_underscores(self):
        """Test validation with hyphens and underscores."""
        assert validate_namespace('log-toggle') is True
        assert validate_namespace('log_toggle') is True
        assert validate_namespace('my-namespace_v2') is True
    
    def test_invalid_empty_namespace(self):
        """Test validation rejects empty namespace."""
        assert validate_namespace('') is False
        assert validate_namespace(None) is False
    
    def test_invalid_special_characters(self):
        """Test validation rejects invalid characters."""
        assert validate_namespace('auth@login') is False
        assert validate_namespace('api#cells') is False
        assert validate_namespace('store$books') is False
        assert validate_namespace('test space') is False
    
    def test_invalid_type(self):
        """Test validation rejects non-string types."""
        assert validate_namespace(123) is False
        assert validate_namespace(['auth']) is False
        assert validate_namespace({'name': 'auth'}) is False


class TestIntegration:
    """Integration tests for complete workflow."""
    
    def test_enable_all_namespaces(self):
        """Test enabling all available namespaces."""
        all_namespaces = get_available_namespaces()
        
        cell_data = {
            'enabled_namespaces': all_namespaces,
            'debug_pattern': ''
        }
        
        result = execute_cell(cell_data)
        
        assert result['success'] is True
        assert len(result['enabled_namespaces']) == len(all_namespaces)
        # Pattern should contain all namespaces
        pattern_parts = result['current_pattern'].split(',')
        assert len(pattern_parts) == len(all_namespaces)
    
    def test_validate_all_default_namespaces(self):
        """Test that all default namespaces are valid."""
        namespaces = get_available_namespaces()
        
        for namespace in namespaces:
            assert validate_namespace(namespace) is True, \
                f"Default namespace '{namespace}' failed validation"
    
    def test_toggle_namespaces_workflow(self):
        """Test a typical toggle workflow."""
        # Start with no namespaces
        initial_data = {
            'enabled_namespaces': [],
            'debug_pattern': ''
        }
        
        result1 = execute_cell(initial_data)
        assert result1['current_pattern'] == ''
        
        # Enable some namespaces
        updated_data = {
            'enabled_namespaces': ['auth', 'api'],
            'debug_pattern': ''
        }
        
        result2 = execute_cell(updated_data)
        assert result2['current_pattern'] == 'auth,api'
        
        # Add more namespaces
        final_data = {
            'enabled_namespaces': ['auth', 'api', 'store'],
            'debug_pattern': ''
        }
        
        result3 = execute_cell(final_data)
        assert result3['current_pattern'] == 'auth,api,store'
        assert len(result3['enabled_namespaces']) == 3
