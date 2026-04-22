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
def mock_queue_image_generation_job():
    """Fixture to mock queue_image_generation_job for tests."""
    async def _mock_generator(generate_return_value):
        """Create a mock for queue_image_generation_job async function."""
        async def mock_job(*args, **kwargs):
            return generate_return_value
        return mock_job
    return _mock_generator


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
    
    async def test_execute_cell_generates_png_success(self, mock_queue_image_generation_job):
        """Test cell execution that triggers PNG generation successfully."""
        cell_data = {
            "prompt": "A red dragon",
            "generatedPng": None
        }

        # Create mock using fixture
        mock_job = await mock_queue_image_generation_job({
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANSbase64data...",
            "metadata": {
                "prompt": "A red dragon",
                "width": 512,
                "height": 512
            }
        })

        with patch('main.queue_image_generation_job', mock_job):
            result = await main.execute_cell(cell_data)

        assert result["success"] is True
        assert result["message"] == "PNG generated successfully"
        assert result["has_png"] is True
        assert "generatedPng" in result
        assert result["generatedPng"].startswith("data:image/png;base64,")
        assert "fallback" not in result
    
    async def test_execute_cell_generates_png_failure(self, mock_queue_image_generation_job):
        """Test cell execution when image generation fails."""
        cell_data = {
            "prompt": "A mountain",
            "generatedPng": None
        }

        # Create mock using fixture
        mock_job = await mock_queue_image_generation_job({
            "success": False,
            "error": "Service timeout"
        })

        with patch('main.queue_image_generation_job', mock_job):
            result = await main.execute_cell(cell_data)

        assert result["success"] is False
        assert "error" in result
        assert result["error"] == "Service timeout"


@pytest.mark.asyncio
class TestGeneratePngFromPrompt:
    """Tests for generate_png_from_prompt function."""
    
    async def test_generate_png_success(self, mock_queue_image_generation_job):
        """Test successful PNG generation."""
        mock_module = mock_queue_image_generation_job({
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
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
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
    
    async def test_generate_png_with_negative_prompt(self, mock_queue_image_generation_job):
        """Test PNG generation with negative prompt."""
        mock_module = mock_queue_image_generation_job({
            "success": True,
            "image_base64": "iVBORw0KGgoAAAANS...",
            "metadata": {
                "prompt": "A dragon",
                "negative_prompt": "blurry, low quality",
                "width": 512,
                "height": 512
            }
        })
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A dragon",
                negative_prompt="blurry, low quality"
            )
        
        assert result["success"] is True
        assert "image_base64" in result
    
    async def test_generate_png_with_3d_asset_mode_enabled(self, mock_queue_image_generation_job):
        """Test PNG generation with 3D Asset Mode enabled."""
        captured_calls = []
        
        def capture_generate_call(*args, **kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.side_effect = capture_generate_call
        mock_sd_class.return_value = mock_service
        mock_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A crystal warrior",
                asset_3d_mode=True
            )
        
        assert result["success"] is True
        assert len(captured_calls) == 1
        
        # Verify that 3D asset suffixes were added
        enhanced_prompt = captured_calls[0]["prompt"]
        assert "A crystal warrior" in enhanced_prompt
        assert "full body" in enhanced_prompt
        assert "flat lighting" in enhanced_prompt
        assert "orthographic view" in enhanced_prompt
        
        enhanced_negative = captured_calls[0]["negative_prompt"]
        assert "shadows" in enhanced_negative
        assert "dramatic lighting" in enhanced_negative
    
    async def test_generate_png_with_3d_asset_mode_and_custom_negative_prompt(self, mock_queue_image_generation_job):
        """Test PNG generation with 3D Asset Mode and custom negative prompt."""
        captured_calls = []
        
        def capture_generate_call(*args, **kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.side_effect = capture_generate_call
        mock_sd_class.return_value = mock_service
        mock_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A robot",
                negative_prompt="blurry, low quality",
                asset_3d_mode=True
            )
        
        assert result["success"] is True
        assert len(captured_calls) == 1
        
        # Verify that custom negative prompt is preserved and 3D suffix is appended
        enhanced_negative = captured_calls[0]["negative_prompt"]
        assert "blurry" in enhanced_negative
        assert "low quality" in enhanced_negative
        assert "shadows" in enhanced_negative
        assert "dramatic lighting" in enhanced_negative
        
        # Verify no keyword duplication
        keywords = [k.strip() for k in enhanced_negative.split(',')]
        assert len(keywords) == len(set(keywords)), "Should not have duplicate keywords"
    
    async def test_generate_png_3d_mode_deduplicates_keywords(self, mock_queue_image_generation_job):
        """Test that 3D Asset Mode properly deduplicates keywords in negative prompt."""
        captured_calls = []
        
        def capture_generate_call(*args, **kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.side_effect = capture_generate_call
        mock_sd_class.return_value = mock_service
        mock_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        # User provides negative prompt with some keywords that overlap with 3D mode defaults
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A spaceship",
                negative_prompt="shadows, cluttered background, extra detail",
                asset_3d_mode=True
            )
        
        assert result["success"] is True
        assert len(captured_calls) == 1
        
        # Verify keywords appear only once
        enhanced_negative = captured_calls[0]["negative_prompt"]
        keywords = [k.strip() for k in enhanced_negative.split(',')]
        
        # Check no duplicates
        assert len(keywords) == len(set(keywords)), f"Found duplicate keywords: {keywords}"
        
        # Verify both user keywords and suffix keywords are present
        assert "shadows" in keywords
        assert "cluttered background" in keywords
        assert "extra detail" in keywords
        assert "dramatic lighting" in keywords
        assert "depth of field" in keywords
    
    async def test_generate_png_with_3d_asset_mode_disabled(self, mock_queue_image_generation_job):
        """Test PNG generation with 3D Asset Mode disabled (default)."""
        captured_calls = []
        
        def capture_generate_call(*args, **kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.side_effect = capture_generate_call
        mock_sd_class.return_value = mock_service
        mock_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A crystal warrior",
                asset_3d_mode=False
            )
        
        assert result["success"] is True
        assert len(captured_calls) == 1
        
        # Verify that prompts are NOT enhanced when 3D mode is disabled
        enhanced_prompt = captured_calls[0]["prompt"]
        assert enhanced_prompt == "A crystal warrior"
        assert "full body" not in enhanced_prompt
        assert "flat lighting" not in enhanced_prompt
    
    async def test_generate_png_service_failure(self, mock_queue_image_generation_job):
        """Test PNG generation when service returns failure."""
        mock_module = mock_queue_image_generation_job({
            "success": False,
            "error": "Stable Diffusion API timeout"
        })
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A mountain"
            )
        
        assert result["success"] is False
        assert "error" in result
        assert "timeout" in result["error"].lower()
    
    async def test_generate_png_exception_handling(self, mock_queue_image_generation_job):
        """Test PNG generation exception handling."""
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.side_effect = Exception("Connection error")
        mock_sd_class.return_value = mock_service
        mock_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
            result = await main.generate_png_from_prompt(
                prompt="A forest"
            )
        
        assert result["success"] is False
        assert "error" in result
        assert "Connection error" in result["error"]


@pytest.mark.asyncio
class TestExecuteCellWith3DAssetMode:
    """Tests for execute_cell with 3D Asset Mode."""
    
    async def test_execute_cell_with_3d_asset_mode(self, mock_queue_image_generation_job):
        """Test cell execution with 3D Asset Mode enabled."""
        cell_data = {
            "prompt": "A space robot",
            "generatedPng": None,
            "asset3dMode": True,
            "negativePrompt": "cartoon style"
        }
        
        captured_calls = []
        
        def capture_generate_call(*args, **kwargs):
            captured_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_service = AsyncMock()
        mock_service.generate_image.side_effect = capture_generate_call
        mock_sd_class.return_value = mock_service
        mock_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {'app.services.stable_diffusion_queue_client': mock_module}):
            result = await main.execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["has_png"] is True
        assert len(captured_calls) == 1
        
        # Verify 3D asset mode was applied
        enhanced_prompt = captured_calls[0]["prompt"]
        assert "A space robot" in enhanced_prompt
        assert "flat lighting" in enhanced_prompt
        
        enhanced_negative = captured_calls[0]["negative_prompt"]
        assert "cartoon style" in enhanced_negative
        assert "shadows" in enhanced_negative


@pytest.mark.asyncio
class TestOllamaOrchestration:
    """Tests for Ollama orchestration in 3D Asset Mode."""
    
    async def test_ollama_orchestration_success(self, mock_queue_image_generation_job):
        """Test successful Ollama orchestration for prompt optimization."""
        # Mock Ollama service
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=True)
        mock_ollama_module.chamar_ollama = AsyncMock(return_value={
            "response": "A detailed space robot, metallic surface, centered composition, front view orthographic, flat studio lighting, neutral gray background, high resolution, clear geometric shapes, technical precision"
        })
        
        # Mock Stable Diffusion service
        captured_sd_calls = []
        
        def capture_sd_call(*args, **kwargs):
            captured_sd_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_sd_service = AsyncMock()
        mock_sd_service.generate_image.side_effect = capture_sd_call
        mock_sd_class.return_value = mock_sd_service
        mock_sd_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
            'app.services.stable_diffusion_queue_client': mock_sd_module
        }):
            result = await main.generate_png_from_prompt(
                prompt="A space robot",
                asset_3d_mode=True
            )
        
        assert result["success"] is True
        
        # Verify Ollama was called
        mock_ollama_module.verificar_ollama_disponivel.assert_called_once()
        mock_ollama_module.chamar_ollama.assert_called_once()
        
        # Verify Ollama prompt contains system instructions
        ollama_call_args = mock_ollama_module.chamar_ollama.call_args[0][0]
        assert "ScareVerse Prompt Architect" in ollama_call_args
        assert "A space robot" in ollama_call_args
        assert "CRITICAL PROHIBITION" in ollama_call_args
        
        # Verify SD was called with optimized prompt
        assert len(captured_sd_calls) == 1
        sd_prompt = captured_sd_calls[0]["prompt"]
        assert "metallic surface" in sd_prompt
        assert "flat studio lighting" in sd_prompt
        
        # Verify negative prompt includes anti-biological keywords
        sd_negative = captured_sd_calls[0]["negative_prompt"]
        assert "humans" in sd_negative
        assert "hands" in sd_negative
        assert "faces" in sd_negative
    
    async def test_ollama_orchestration_ollama_unavailable(self, mock_queue_image_generation_job):
        """Test fallback to static enhancement when Ollama is unavailable."""
        # Mock Ollama service as unavailable
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=False)
        
        # Mock Stable Diffusion service
        captured_sd_calls = []
        
        def capture_sd_call(*args, **kwargs):
            captured_sd_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_sd_service = AsyncMock()
        mock_sd_service.generate_image.side_effect = capture_sd_call
        mock_sd_class.return_value = mock_sd_service
        mock_sd_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
            'app.services.stable_diffusion_queue_client': mock_sd_module
        }):
            result = await main.generate_png_from_prompt(
                prompt="A magic sword",
                asset_3d_mode=True
            )
        
        assert result["success"] is True
        
        # Verify Ollama availability was checked
        mock_ollama_module.verificar_ollama_disponivel.assert_called_once()
        
        # Verify chamar_ollama was NOT called (Ollama unavailable)
        mock_ollama_module.chamar_ollama.assert_not_called()
        
        # Verify SD was called with static enhancement
        assert len(captured_sd_calls) == 1
        sd_prompt = captured_sd_calls[0]["prompt"]
        assert "A magic sword" in sd_prompt
        assert "full body" in sd_prompt
        assert "flat lighting" in sd_prompt
        assert "orthographic view" in sd_prompt
    
    async def test_ollama_orchestration_ollama_returns_empty(self, mock_queue_image_generation_job):
        """Test fallback to static enhancement when Ollama returns empty response."""
        # Mock Ollama service returning empty
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=True)
        mock_ollama_module.chamar_ollama = AsyncMock(return_value={"response": ""})
        
        # Mock Stable Diffusion service
        captured_sd_calls = []
        
        def capture_sd_call(*args, **kwargs):
            captured_sd_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_sd_service = AsyncMock()
        mock_sd_service.generate_image.side_effect = capture_sd_call
        mock_sd_class.return_value = mock_sd_service
        mock_sd_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
            'app.services.stable_diffusion_queue_client': mock_sd_module
        }):
            result = await main.generate_png_from_prompt(
                prompt="A treasure chest",
                asset_3d_mode=True
            )
        
        assert result["success"] is True
        
        # Verify Ollama was called but returned empty
        mock_ollama_module.chamar_ollama.assert_called_once()
        
        # Verify SD was called with static enhancement (fallback)
        assert len(captured_sd_calls) == 1
        sd_prompt = captured_sd_calls[0]["prompt"]
        assert "A treasure chest" in sd_prompt
        assert "full body" in sd_prompt
    
    async def test_ollama_orchestration_with_custom_negative_prompt(self, mock_queue_image_generation_job):
        """Test Ollama orchestration preserves user's negative prompt."""
        # Mock Ollama service
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=True)
        mock_ollama_module.chamar_ollama = AsyncMock(return_value={
            "response": "A medieval shield with ornate details, centered view, flat lighting, gray background"
        })
        
        # Mock Stable Diffusion service
        captured_sd_calls = []
        
        def capture_sd_call(*args, **kwargs):
            captured_sd_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_sd_service = AsyncMock()
        mock_sd_service.generate_image.side_effect = capture_sd_call
        mock_sd_class.return_value = mock_sd_service
        mock_sd_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
            'app.services.stable_diffusion_queue_client': mock_sd_module
        }):
            result = await main.generate_png_from_prompt(
                prompt="A medieval shield",
                negative_prompt="rust, damage, scratches",
                asset_3d_mode=True
            )
        
        assert result["success"] is True
        
        # Verify SD negative prompt includes both user keywords and base negative
        assert len(captured_sd_calls) == 1
        sd_negative = captured_sd_calls[0]["negative_prompt"]
        
        # User keywords preserved
        assert "rust" in sd_negative
        assert "damage" in sd_negative
        assert "scratches" in sd_negative
        
        # Base negative keywords added
        assert "humans" in sd_negative
        assert "people" in sd_negative
        assert "hands" in sd_negative
    
    async def test_ollama_orchestration_exception_handling(self, mock_queue_image_generation_job):
        """Test fallback when Ollama raises exception."""
        # Mock Ollama service raising exception
        mock_ollama_module = MagicMock()
        mock_ollama_module.verificar_ollama_disponivel = AsyncMock(return_value=True)
        mock_ollama_module.chamar_ollama = AsyncMock(side_effect=Exception("Connection timeout"))
        
        # Mock Stable Diffusion service
        captured_sd_calls = []
        
        def capture_sd_call(*args, **kwargs):
            captured_sd_calls.append(kwargs)
            return {
                "success": True,
                "image_base64": "iVBORw0KGgoAAAANS...",
                "metadata": {"prompt": kwargs.get("prompt", "")}
            }
        
        mock_sd_class = MagicMock()
        mock_sd_service = AsyncMock()
        mock_sd_service.generate_image.side_effect = capture_sd_call
        mock_sd_class.return_value = mock_sd_service
        mock_sd_module = MagicMock(StableDiffusionQueueClient=mock_sd_class)
        
        with patch.dict('sys.modules', {
            'app.ollama_service': mock_ollama_module,
            'app.services.stable_diffusion_queue_client': mock_sd_module
        }):
            result = await main.generate_png_from_prompt(
                prompt="A magic staff",
                asset_3d_mode=True
            )
        
        assert result["success"] is True
        
        # Verify SD was called with static enhancement (fallback after exception)
        assert len(captured_sd_calls) == 1
        sd_prompt = captured_sd_calls[0]["prompt"]
        assert "A magic staff" in sd_prompt
        assert "flat lighting" in sd_prompt


def test_static_3d_enhancement():
    """Test the static 3D enhancement helper function."""
    prompt = "A wooden barrel"
    negative_prompt = None
    
    enhanced_prompt, enhanced_negative = main._apply_static_3d_enhancement(prompt, negative_prompt)
    
    # Check positive enhancement
    assert "A wooden barrel" in enhanced_prompt
    assert "full body" in enhanced_prompt
    assert "flat lighting" in enhanced_prompt
    assert "orthographic view" in enhanced_prompt
    
    # Check negative enhancement
    assert "shadows" in enhanced_negative
    assert "dramatic lighting" in enhanced_negative
    assert "cluttered background" in enhanced_negative


def test_static_3d_enhancement_with_custom_negative():
    """Test static 3D enhancement with custom negative prompt."""
    prompt = "A steel helmet"
    negative_prompt = "rust, damage"
    
    enhanced_prompt, enhanced_negative = main._apply_static_3d_enhancement(prompt, negative_prompt)
    
    # Check positive enhancement
    assert "A steel helmet" in enhanced_prompt
    
    # Check negative enhancement preserves user keywords
    assert "rust" in enhanced_negative
    assert "damage" in enhanced_negative
    assert "shadows" in enhanced_negative
    
    # Check no duplicate keywords
    keywords = [k.strip() for k in enhanced_negative.split(',')]
    assert len(keywords) == len(set(keywords))
