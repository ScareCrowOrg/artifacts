"""
Tests for svg-generator-cell backend scripts.
"""

import pytest
import json
import sys
from pathlib import Path

# Add the cell scripts directory to Python path
cell_scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(cell_scripts_dir))

from main import execute_cell


class TestExecuteCell:
    """Tests for execute_cell function."""
    
    def test_execute_cell_with_prompt(self):
        """Test executing cell with a prompt."""
        cell_data = {
            "prompt": "A simple circle",
            "generatedSvg": None
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "SVG generator cell ready"
        assert result["prompt"] == "A simple circle"
        assert result["has_svg"] is False
    
    def test_execute_cell_with_generated_svg(self):
        """Test executing cell with generated SVG."""
        svg_code = '<svg><circle cx="50" cy="50" r="40" fill="blue"/></svg>'
        cell_data = {
            "prompt": "A blue circle",
            "generatedSvg": svg_code
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["has_svg"] is True
        assert result["prompt"] == "A blue circle"
    
    def test_execute_cell_empty_prompt(self):
        """Test executing cell with empty prompt."""
        cell_data = {
            "prompt": "",
            "generatedSvg": None
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_svg"] is False
    
    def test_execute_cell_default_values(self):
        """Test executing cell with missing fields."""
        cell_data = {}
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_svg"] is False


@pytest.mark.asyncio
class TestGenerateSvgFromPrompt:
    """Tests for SVG generation function."""
    
    @pytest.mark.skip(reason="Requires LLM service mock - future enhancement")
    async def test_generate_svg_basic_shape(self):
        """Test generating SVG for a basic shape."""
        pass
    
    @pytest.mark.skip(reason="Requires LLM service mock - future enhancement")
    async def test_generate_svg_complex_prompt(self):
        """Test generating SVG for a complex prompt."""
        pass
    
    @pytest.mark.skip(reason="Requires LLM service mock - future enhancement")
    async def test_generate_svg_error_handling(self):
        """Test error handling in SVG generation."""
        pass


class TestCellDataStructure:
    """Tests for cell data structure validation."""
    
    def test_valid_cell_data_structure(self):
        """Test that cell data has expected structure."""
        cell_data = {
            "prompt": "Test prompt",
            "generatedSvg": "<svg></svg>",
            "isGenerating": False,
            "error": None
        }
        
        # All expected keys should be present
        assert "prompt" in cell_data
        assert "generatedSvg" in cell_data
        assert "isGenerating" in cell_data
        assert "error" in cell_data
    
    def test_cell_data_types(self):
        """Test that cell data types are correct."""
        cell_data = {
            "prompt": "Test prompt",
            "generatedSvg": "<svg></svg>",
            "isGenerating": False,
            "error": None
        }
        
        assert isinstance(cell_data["prompt"], str)
        assert isinstance(cell_data["generatedSvg"], str) or cell_data["generatedSvg"] is None
        assert isinstance(cell_data["isGenerating"], bool)
        assert isinstance(cell_data["error"], str) or cell_data["error"] is None
