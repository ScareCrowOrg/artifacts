"""
Tests for example cell backend scripts.

These tests validate the execution logic of the example cell type.
"""

import pytest
import json
import sys
from pathlib import Path

# Add the project root to path to allow imports
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from artifacts.canonical.cell_types.example.backend.scripts.main import execute_cell


class TestExampleCellScripts:
    """Test suite for example cell scripts"""
    
    def test_execute_cell_basic(self):
        """Test basic cell execution"""
        cell_data = {
            "message": "Hello World",
            "counter": 5
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["output"] == "Hello World (Count: 5)"
        assert result["new_counter"] == 6
    
    def test_execute_cell_default_values(self):
        """Test execution with default values"""
        cell_data = {}
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert "Hello from Example Cell" in result["output"]
        assert result["new_counter"] == 1
    
    def test_execute_cell_counter_increment(self):
        """Test counter increments correctly"""
        cell_data = {
            "message": "Test",
            "counter": 0
        }
        
        result = execute_cell(cell_data)
        
        assert result["new_counter"] == 1
        
        # Execute again with incremented counter
        cell_data["counter"] = result["new_counter"]
        result = execute_cell(cell_data)
        
        assert result["new_counter"] == 2
    
    def test_execute_cell_custom_message(self):
        """Test execution with custom message"""
        cell_data = {
            "message": "Custom Message",
            "counter": 10
        }
        
        result = execute_cell(cell_data)
        
        assert "Custom Message" in result["output"]
        assert "(Count: 10)" in result["output"]
    
    def test_execute_cell_returns_dict(self):
        """Test that execution returns a dictionary"""
        cell_data = {
            "message": "Test",
            "counter": 0
        }
        
        result = execute_cell(cell_data)
        
        assert isinstance(result, dict)
        assert "success" in result
        assert "output" in result
        assert "new_counter" in result
