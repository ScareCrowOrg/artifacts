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


@pytest.fixture
def mock_stable_diffusion_service():
    """Fixture to mock StableDiffusionService for tests."""
    def _create_mock(generate_image_return_value):
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.return_value = generate_image_return_value
        mock_sd_class.return_value = mock_service
        return MagicMock(StableDiffusionService=mock_sd_class)
    return _create_mock


@pytest.mark.asyncio
class TestExecuteCell:
    """Tests for execute_cell function."""
    
    async def test_execute_cell_with_existing_png(self):
        """Test cell execution with already generated PNG."""
        cell_data = {
            "prompt": "A blue crystal",
            "generatedPng": "data:image/png;base64,iVBORw0KGgoAAAANS..."
        }
        
        result = await main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "PNG generator cell ready"
        assert result["has_png"] is True
        assert result["generatedPng"] == "data:image/png;base64,iVBORw0KGgoAAAANS..."
    
    async def test_execute_cell_empty_prompt(self):
        """Test cell execution with empty prompt."""
        cell_data = {
            "prompt": "",
            "generatedPng": None
        }
        
        result = await main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_png"] is False
        assert result["message"] == "No prompt provided"
    
    async def test_execute_cell_generates_png_success(self, mock_stable_diffusion_service):
        """Test cell execution that triggers PNG generation successfully."""
        cell_data = {
            "prompt": "A red dragon",
            "generatedPng": None
        }
        
        # Create mock using fixture
        mock_module = mock_stable_diffusion_service({
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANSbase64data...",
            "metadata": {
                "prompt": "A red dragon",
                "width": 512,
                "height": 512
            }
        })
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': mock_module}):
            result = await main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "PNG generated successfully"
        assert result["has_png"] is True
        assert "generatedPng" in result
        assert result["generatedPng"].startswith("data:image/png;base64,")
        assert "fallback" not in result
    
    async def test_execute_cell_generates_png_fallback(self, mock_stable_diffusion_service):
        """Test cell execution falls back to placeholder when service fails."""
        cell_data = {
            "prompt": "A mountain",
            "generatedPng": None
        }
        
        # Create mock using fixture
        mock_module = mock_stable_diffusion_service({
            "success": False,
            "error": "Service timeout"
        })
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': mock_module}):
            result = await main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["has_png"] is True
        assert "generatedPng" in result
        assert result["generatedPng"].startswith("data:image/png;base64,")
        assert result.get("fallback") is True
        assert "error" in result


@pytest.mark.asyncio
class TestGeneratePngFromPrompt:
    """Tests for generate_png_from_prompt function."""
    
    async def test_generate_png_success(self, mock_stable_diffusion_service):
        """Test successful PNG generation."""
        mock_module = mock_stable_diffusion_service({
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
        })
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': mock_module}):
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
    
    async def test_generate_png_service_failure(self, mock_stable_diffusion_service):
        """Test PNG generation when service returns failure."""
        mock_module = mock_stable_diffusion_service({
            "success": False,
            "error": "Stable Diffusion API timeout"
        })
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A mountain"
            )
        
        assert result["success"] is False
        assert "error" in result
        assert "timeout" in result["error"].lower()
    
    async def test_generate_png_exception_handling(self, mock_stable_diffusion_service):
        """Test PNG generation exception handling."""
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.side_effect = Exception("Connection error")
        mock_sd_class.return_value = mock_service
        mock_module = MagicMock(StableDiffusionService=mock_sd_class)
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_service': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A forest"
            )
        
        assert result["success"] is False
        assert "error" in result
        assert "Connection error" in result["error"]
