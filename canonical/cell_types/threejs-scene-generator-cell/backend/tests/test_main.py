"""
Unit tests for Three.js Scene Generator Cell backend.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from artifacts.canonical.cell_types.threejs_scene_generator_cell.backend.scripts.main import (
    execute_cell,
    generate_threejs_from_prompt
)


class TestExecuteCell:
    """Tests for execute_cell function."""
    
    def test_execute_cell_with_prompt(self):
        """Test execute_cell with a valid prompt."""
        cell_data = {
            "prompt": "A rotating cube",
            "generatedScript": None
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["message"] == "Three.js scene generator cell ready"
        assert result["prompt"] == "A rotating cube"
        assert result["has_script"] is False
    
    def test_execute_cell_with_generated_script(self):
        """Test execute_cell with generated script present."""
        cell_data = {
            "prompt": "A blue sphere",
            "generatedScript": "const scene = new THREE.Scene();"
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["has_script"] is True
        assert result["prompt"] == "A blue sphere"
    
    def test_execute_cell_empty_prompt(self):
        """Test execute_cell with empty prompt."""
        cell_data = {
            "prompt": "",
            "generatedScript": None
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_script"] is False
    
    def test_execute_cell_missing_fields(self):
        """Test execute_cell with missing fields uses defaults."""
        cell_data = {}
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == ""
        assert result["has_script"] is False


class TestGenerateThreeJSFromPrompt:
    """Tests for generate_threejs_from_prompt function."""
    
    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful Three.js code generation."""
        mock_llm_service = MagicMock()
        mock_llm_service.generate_code_streaming = AsyncMock()
        
        # Mock the streaming response
        async def mock_stream(*args, **kwargs):
            yield {"type": "code", "content": "const scene = new THREE.Scene();"}
            yield {"type": "code", "content": "\nconst camera = new THREE.PerspectiveCamera();"}
            yield {"type": "code", "content": "\nconst renderer = new THREE.WebGLRenderer();"}
        
        mock_llm_service.generate_code_streaming = mock_stream
        
        with patch('artifacts.canonical.cell_types.threejs_scene_generator_cell.backend.scripts.main.LLMService', return_value=mock_llm_service):
            result = await generate_threejs_from_prompt("A rotating cube", "mistral")
        
        assert result["success"] is True
        assert "THREE." in result["script"]
        assert "scene" in result["script"]
        assert "camera" in result["script"]
        assert "renderer" in result["script"]
        assert result["prompt"] == "A rotating cube"
    
    @pytest.mark.asyncio
    async def test_generate_missing_required_elements(self):
        """Test generation fails when required Three.js elements are missing."""
        mock_llm_service = MagicMock()
        
        # Mock streaming response with invalid code
        async def mock_stream(*args, **kwargs):
            yield {"type": "code", "content": "console.log('hello');"}
        
        mock_llm_service.generate_code_streaming = mock_stream
        
        with patch('artifacts.canonical.cell_types.threejs_scene_generator_cell.backend.scripts.main.LLMService', return_value=mock_llm_service):
            result = await generate_threejs_from_prompt("Invalid prompt", "mistral")
        
        assert result["success"] is False
        assert "error" in result
        assert "Failed to generate valid Three.js code" in result["error"]
    
    @pytest.mark.asyncio
    async def test_generate_skips_narrative(self):
        """Test that narrative chunks are skipped."""
        mock_llm_service = MagicMock()
        
        # Mock streaming with mixed content
        async def mock_stream(*args, **kwargs):
            yield {"type": "narrative", "content": "Let me create a scene..."}
            yield {"type": "code", "content": "const scene = new THREE.Scene();"}
            yield {"type": "narrative", "content": "Adding camera..."}
            yield {"type": "code", "content": "\nconst camera = new THREE.PerspectiveCamera();"}
            yield {"type": "code", "content": "\nconst renderer = new THREE.WebGLRenderer();"}
        
        mock_llm_service.generate_code_streaming = mock_stream
        
        with patch('artifacts.canonical.cell_types.threejs_scene_generator_cell.backend.scripts.main.LLMService', return_value=mock_llm_service):
            result = await generate_threejs_from_prompt("A scene", "mistral")
        
        assert result["success"] is True
        # Ensure narrative is not in the script
        assert "Let me create" not in result["script"]
        assert "Adding camera" not in result["script"]
        # Ensure code is present
        assert "THREE.Scene" in result["script"]
    
    @pytest.mark.asyncio
    async def test_generate_handles_exception(self):
        """Test error handling when LLM service raises exception."""
        with patch('artifacts.canonical.cell_types.threejs_scene_generator_cell.backend.scripts.main.LLMService', side_effect=Exception("LLM service error")):
            result = await generate_threejs_from_prompt("A cube", "mistral")
        
        assert result["success"] is False
        assert "error" in result
        assert "LLM service error" in result["error"]
        assert result["prompt"] == "A cube"
    
    @pytest.mark.asyncio
    async def test_generate_with_different_model(self):
        """Test generation with different AI model."""
        mock_llm_service = MagicMock()
        
        async def mock_stream(*args, **kwargs):
            # Verify the model parameter is passed
            assert kwargs.get('model') == 'gpt-4'
            yield {"type": "code", "content": "const scene = new THREE.Scene();"}
            yield {"type": "code", "content": "\nconst camera = new THREE.PerspectiveCamera();"}
            yield {"type": "code", "content": "\nconst renderer = new THREE.WebGLRenderer();"}
        
        mock_llm_service.generate_code_streaming = mock_stream
        
        with patch('artifacts.canonical.cell_types.threejs_scene_generator_cell.backend.scripts.main.LLMService', return_value=mock_llm_service):
            result = await generate_threejs_from_prompt("A scene", "gpt-4")
        
        assert result["success"] is True


class TestStandaloneExecution:
    """Tests for standalone script execution."""
    
    def test_standalone_with_args(self, monkeypatch):
        """Test standalone execution with command-line arguments."""
        test_data = {"prompt": "Test scene", "generatedScript": "test code"}
        
        import sys
        monkeypatch.setattr(sys, 'argv', ['main.py', json.dumps(test_data)])
        
        # This would normally execute the script, but we're just testing the logic
        result = execute_cell(test_data)
        assert result["success"] is True
        assert result["prompt"] == "Test scene"
    
    def test_standalone_without_args(self, monkeypatch):
        """Test standalone execution without arguments uses defaults."""
        import sys
        monkeypatch.setattr(sys, 'argv', ['main.py'])
        
        # Test with default data
        default_data = {"prompt": "A rotating cube", "generatedScript": None}
        result = execute_cell(default_data)
        assert result["success"] is True
        assert result["prompt"] == "A rotating cube"


# Test data fixtures
@pytest.fixture
def sample_cell_data():
    """Sample cell data for testing."""
    return {
        "prompt": "A rotating metallic cube with dynamic lighting",
        "generatedScript": None,
        "isGenerating": False,
        "error": None,
        "selectedModel": "mistral"
    }


@pytest.fixture
def sample_threejs_code():
    """Sample Three.js code for testing."""
    return """
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer();
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const geometry = new THREE.BoxGeometry();
const material = new THREE.MeshStandardMaterial({ color: 0x00ff00 });
const cube = new THREE.Mesh(geometry, material);
scene.add(cube);

camera.position.z = 5;

function animate() {
    requestAnimationFrame(animate);
    cube.rotation.x += 0.01;
    cube.rotation.y += 0.01;
    renderer.render(scene, camera);
}
animate();
"""
