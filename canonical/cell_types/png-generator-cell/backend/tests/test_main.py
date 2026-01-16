"""
Tests for png-generator-cell backend.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

# Add the cell scripts directory to Python path
cell_root = Path(__file__).parent.parent
sys.path.insert(0, str(cell_root / "scripts"))

import main


class TestExecuteCell:
    """Tests for execute_cell function."""
    
    def test_execute_cell_with_existing_png(self):
        """Test cell execution with already generated PNG."""
        cell_data = {
            "prompt": "A blue crystal",
            "generatedPng": "data:image/png;base64,iVBORw0KGgoAAAANS..."
        }
        
        result = main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "PNG generator cell ready"
        assert result["has_png"] is True
        assert result["generatedPng"] == "data:image/png;base64,iVBORw0KGgoAAAANS..."
    
    def test_execute_cell_empty_prompt(self):
        """Test cell execution with empty prompt."""
        cell_data = {
            "prompt": "",
            "generatedPng": None
        }
        
        result = main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_png"] is False
        assert result["message"] == "No prompt provided"
    
    def test_execute_cell_generates_png_success(self):
        """Test cell execution that triggers PNG generation successfully."""
        cell_data = {
            "prompt": "A red dragon",
            "generatedPng": None
        }
        
        # Mock the StableDiffusionService
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.return_value = {
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANSbase64data...",
            "metadata": {
                "prompt": "A red dragon",
                "width": 512,
                "height": 512
            }
        }
        mock_sd_class.return_value = mock_service
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': MagicMock(StableDiffusionService=mock_sd_class)}):
            result = main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "PNG generated successfully"
        assert result["has_png"] is True
        assert "generatedPng" in result
        assert result["generatedPng"].startswith("data:image/png;base64,")
        assert "fallback" not in result
    
    def test_execute_cell_generates_png_fallback(self):
        """Test cell execution falls back to placeholder when service fails."""
        cell_data = {
            "prompt": "A mountain",
            "generatedPng": None
        }
        
        # Mock service to return failure
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.return_value = {
            "success": False,
            "error": "Service timeout"
        }
        mock_sd_class.return_value = mock_service
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': MagicMock(StableDiffusionService=mock_sd_class)}):
            result = main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["has_png"] is True
        assert "generatedPng" in result
        assert result["generatedPng"].startswith("data:image/png;base64,")
        assert result.get("fallback") is True
        assert "error" in result


@pytest.mark.asyncio
class TestGeneratePngFromPrompt:
    """Tests for generate_png_from_prompt function."""
    
    async def test_generate_png_success(self):
        """Test successful PNG generation."""
        # Mock the StableDiffusionService class
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.return_value = {
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANS...",
            "metadata": {
                "prompt": "A blue crystal",
                "width": 512,
                "height": 512,
                "steps": 20,
                "cfg_scale": 7.0,
                "seed": 12345
            }
        }
        mock_sd_class.return_value = mock_service
        
        # Patch the import inside the function
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': MagicMock(StableDiffusionService=mock_sd_class)}):
            result = await main.generate_png_from_prompt(
                prompt="A blue crystal",
                width=512,
                height=512,
                steps=20,
                cfg_scale=7.0,
                seed=-1
            )
        
        assert result["success"] is True
        assert "image_base64" in result
        assert result["prompt"] == "A blue crystal"
        assert "metadata" in result
    
    async def test_generate_png_service_failure(self):
        """Test PNG generation when service returns failure."""
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.return_value = {
            "success": False,
            "error": "Stable Diffusion API timeout"
        }
        mock_sd_class.return_value = mock_service
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': MagicMock(StableDiffusionService=mock_sd_class)}):
            result = await main.generate_png_from_prompt(
                prompt="A mountain"
            )
        
        assert result["success"] is False
        assert "error" in result
        assert "timeout" in result["error"].lower()
    
    async def test_generate_png_exception_handling(self):
        """Test PNG generation exception handling."""
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.side_effect = Exception("Connection error")
        mock_sd_class.return_value = mock_service
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': MagicMock(StableDiffusionService=mock_sd_class)}):
            result = await main.generate_png_from_prompt(
                prompt="A forest"
            )
        
        assert result["success"] is False
        assert "error" in result
        assert "Connection error" in result["error"]
