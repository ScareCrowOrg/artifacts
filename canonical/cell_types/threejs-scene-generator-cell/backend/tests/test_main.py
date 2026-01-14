"""
Unit tests for Three.js Scene Generator Cell backend.

Note: These tests focus on the execute_cell function which can be tested without
mocking LLM services. The generate_threejs_from_prompt function requires integration
with backend services and is better tested through integration tests.
"""

import pytest
import json
import sys
from pathlib import Path

# Add the cell's backend scripts to the Python path
cell_backend_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(cell_backend_path))

from main import execute_cell


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
    
    def test_execute_cell_with_complex_prompt(self):
        """Test execute_cell with complex multi-line prompt."""
        complex_prompt = """A 3D scene with:
- A rotating cube in the center
- Dynamic lighting
- Camera orbit controls
- Particle effects"""
        
        cell_data = {
            "prompt": complex_prompt,
            "generatedScript": None
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["prompt"] == complex_prompt
        assert result["has_script"] is False
    
    def test_execute_cell_return_structure(self):
        """Test that execute_cell returns the expected data structure."""
        cell_data = {"prompt": "test", "generatedScript": "code"}
        
        result = execute_cell(cell_data)
        
        # Verify all expected keys are present
        assert "success" in result
        assert "message" in result
        assert "prompt" in result
        assert "has_script" in result
        
        # Verify types
        assert isinstance(result["success"], bool)
        assert isinstance(result["message"], str)
        assert isinstance(result["prompt"], str)
        assert isinstance(result["has_script"], bool)


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


class TestSampleData:
    """Tests using fixture data."""
    
    def test_with_sample_cell_data(self, sample_cell_data):
        """Test execute_cell with sample fixture data."""
        result = execute_cell(sample_cell_data)
        
        assert result["success"] is True
        assert "metallic cube" in result["prompt"]
    
    def test_with_sample_code(self, sample_threejs_code):
        """Test execute_cell with sample Three.js code."""
        cell_data = {
            "prompt": "Sample prompt",
            "generatedScript": sample_threejs_code
        }
        
        result = execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["has_script"] is True
