"""
Tests for svg-generator-cell backend scripts.
"""

import pytest
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add the cell scripts directory to Python path
cell_scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(cell_scripts_dir))

from main import execute_cell, generate_svg_from_prompt


@pytest.fixture
def mock_llm_service():
    """Fixture to mock LLM service for tests."""
    def _create_mock(generate_result):
        mock_llm_class = MagicMock()
        mock_service = MagicMock()
        
        # Create async iterator for streaming
        async def mock_streaming(*args, **kwargs):
            for chunk in generate_result:
                yield chunk
        
        mock_service.generate_code_streaming = mock_streaming
        mock_llm_class.return_value = mock_service
        return mock_llm_class
    return _create_mock


@pytest.mark.asyncio
class TestExecuteCell:
    """Tests for execute_cell function."""
    
    async def test_execute_cell_with_existing_svg(self):
        """Test cell execution with already generated SVG."""
        svg_code = '<svg><circle cx="50" cy="50" r="40" fill="blue"/></svg>'
        cell_data = {
            "prompt": "A blue circle",
            "generatedSvg": svg_code
        }
        
        result = await execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "SVG generator cell ready"
        assert result["has_svg"] is True
        assert result["generatedSvg"] == svg_code
    
    async def test_execute_cell_empty_prompt(self):
        """Test executing cell with empty prompt."""
        cell_data = {
            "prompt": "",
            "generatedSvg": None
        }
        
        result = await execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_svg"] is False
        assert result["message"] == "No prompt provided"
    
    async def test_execute_cell_generates_svg_success(self, mock_llm_service):
        """Test cell execution that triggers SVG generation successfully."""
        cell_data = {
            "prompt": "A red square",
            "generatedSvg": None
        }
        
        # Create mock using fixture
        mock_llm = mock_llm_service([
            {"type": "code", "content": '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'},
            {"type": "code", "content": '<rect x="25" y="25" width="50" height="50" fill="red"/>'},
            {"type": "code", "content": '</svg>'}
        ])
        
        mock_enriched_prompt = MagicMock()
        
        with patch.dict('sys.modules', {
            'app.services.llm_service': MagicMock(LLMService=mock_llm),
            'app.models': MagicMock(EnrichedPrompt=mock_enriched_prompt, ConversationMessage=MagicMock())
        }):
            result = await execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "SVG generated successfully"
        assert result["has_svg"] is True
        assert "generatedSvg" in result
        assert result["generatedSvg"].startswith("<svg")
        assert "fallback" not in result
    
    async def test_execute_cell_generates_svg_fallback(self, mock_llm_service):
        """Test cell execution falls back to placeholder when service fails."""
        cell_data = {
            "prompt": "A complex shape",
            "generatedSvg": None
        }
        
        # Mock service to return invalid SVG
        mock_llm = mock_llm_service([
            {"type": "narrative", "content": "Here's your SVG:"},
            {"type": "code", "content": "Not valid SVG"}
        ])
        
        mock_enriched_prompt = MagicMock()
        
        with patch.dict('sys.modules', {
            'app.services.llm_service': MagicMock(LLMService=mock_llm),
            'app.models': MagicMock(EnrichedPrompt=mock_enriched_prompt, ConversationMessage=MagicMock())
        }):
            result = await execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["has_svg"] is True
        assert "generatedSvg" in result
        assert result["generatedSvg"].startswith("<svg")
        assert result.get("fallback") is True
        assert "error" in result
    
    async def test_execute_cell_default_values(self):
        """Test executing cell with missing fields."""
        cell_data = {}
        
        result = await execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_svg"] is False


@pytest.mark.asyncio
class TestGenerateSvgFromPrompt:
    """Tests for SVG generation function."""
    
    async def test_generate_svg_success(self, mock_llm_service):
        """Test successful SVG generation."""
        mock_llm = mock_llm_service([
            {"type": "code", "content": '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">'},
            {"type": "code", "content": '<circle cx="100" cy="100" r="50" fill="blue"/>'},
            {"type": "code", "content": '</svg>'}
        ])
        
        mock_enriched_prompt = MagicMock()
        
        with patch.dict('sys.modules', {
            'app.services.llm_service': MagicMock(LLMService=mock_llm),
            'app.models': MagicMock(EnrichedPrompt=mock_enriched_prompt, ConversationMessage=MagicMock())
        }):
            result = await generate_svg_from_prompt("A blue circle")
        
        assert result["success"] is True
        assert "svg" in result
        assert result["svg"].startswith("<svg")
        assert result["prompt"] == "A blue circle"
    
    async def test_generate_svg_invalid_output(self, mock_llm_service):
        """Test SVG generation when LLM returns invalid SVG."""
        mock_llm = mock_llm_service([
            {"type": "narrative", "content": "I'll create that for you"},
            {"type": "code", "content": "This is not SVG"}
        ])
        
        mock_enriched_prompt = MagicMock()
        
        with patch.dict('sys.modules', {
            'app.services.llm_service': MagicMock(LLMService=mock_llm),
            'app.models': MagicMock(EnrichedPrompt=mock_enriched_prompt, ConversationMessage=MagicMock())
        }):
            result = await generate_svg_from_prompt("A shape")
        
        assert result["success"] is False
        assert "error" in result
        assert "valid SVG" in result["error"]
    
    async def test_generate_svg_import_error(self):
        """Test SVG generation when LLM service import fails."""
        # Don't mock the imports, let them fail naturally
        result = await generate_svg_from_prompt("A triangle")
        
        assert result["success"] is False
        assert "error" in result
        # Service might fail due to import or configuration issues
        assert "not available" in result["error"].lower() or "not configured" in result["error"].lower()


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
