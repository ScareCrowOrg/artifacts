"""
Tests for 3D Mesh Prototyping Cell backend execution logic.

Tests cover:
- Cell execution interface
- Mock mesh generation
- Error handling
- Metadata validation
"""

import pytest
import json
from typing import Dict, Any
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add the backend scripts directory to path for imports
scripts_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_path))

from main import execute_cell, generate_3d_mesh_from_image, _generate_mock_glb_mesh


class TestExecuteCell:
    """Tests for the main execute_cell function."""
    
    @pytest.mark.asyncio
    async def test_execute_cell_success(self):
        """Test successful execution with valid input image."""
        cell_data = {
            "inputImage": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "reconstructionParams": {
                "targetFaces": 50000,
                "enableDracoCompression": True,
                "compressionLevel": 7,
                "targetFileSizeMB": 5
            }
        }
        
        result = await execute_cell(cell_data)
        
        assert result["success"] is True
        assert result["generatedMesh"] is not None
        assert result["meshMetadata"] is not None
        assert "vertices" in result["meshMetadata"]
        assert "faces" in result["meshMetadata"]
        assert "fileSizeBytes" in result["meshMetadata"]
        assert result["generatedMesh"].startswith("data:model/gltf-binary;base64,")
    
    @pytest.mark.asyncio
    async def test_execute_cell_no_input_image(self):
        """Test execution fails gracefully when no input image provided."""
        cell_data = {
            "reconstructionParams": {
                "targetFaces": 50000
            }
        }
        
        result = await execute_cell(cell_data)
        
        assert result["success"] is False
        assert result["error"] is not None
        assert "No input image" in result["error"]
        assert result["generatedMesh"] is None
        assert result["meshMetadata"] is None
    
    @pytest.mark.asyncio
    async def test_execute_cell_with_custom_params(self):
        """Test execution with custom reconstruction parameters."""
        cell_data = {
            "inputImage": "data:image/png;base64,iVBORw0KGgo...",
            "reconstructionParams": {
                "targetFaces": 100000,
                "enableDracoCompression": False,
                "compressionLevel": 5,
                "targetFileSizeMB": 10
            }
        }
        
        result = await execute_cell(cell_data)
        
        assert result["success"] is True
        # Metadata should reflect custom target faces
        assert result["meshMetadata"]["faces"] == 100000


class TestGenerate3DMesh:
    """Tests for the 3D mesh generation function."""
    
    @pytest.mark.asyncio
    async def test_generate_3d_mesh_mock_implementation(self):
        """Test that mock implementation returns valid GLB data."""
        result = await generate_3d_mesh_from_image(
            input_image="data:image/png;base64,iVBORw0KGgo...",
            target_faces=50000,
            enable_draco=True,
            compression_level=7,
            target_size_mb=5.0
        )
        
        assert result["success"] is True
        assert result["mesh_data"] is not None
        assert result["metadata"] is not None
        assert result["mesh_data"].startswith("data:model/gltf-binary;base64,")
    
    @pytest.mark.asyncio
    async def test_generate_3d_mesh_different_params(self):
        """Test mesh generation with different parameters."""
        result = await generate_3d_mesh_from_image(
            input_image="data:image/png;base64,test",
            target_faces=25000,
            enable_draco=False,
            compression_level=3,
            target_size_mb=2.0
        )
        
        assert result["success"] is True
        metadata = result["metadata"]
        assert metadata["faces"] == 25000
        assert metadata["compressionEnabled"] is False


class TestMockGLBGeneration:
    """Tests for mock GLB mesh generation."""
    
    def test_generate_mock_glb_basic(self):
        """Test basic mock GLB generation."""
        result = _generate_mock_glb_mesh(
            target_faces=50000,
            enable_draco=True
        )
        
        assert result["success"] is True
        assert result["mesh_data"] is not None
        assert result["metadata"] is not None
        
        metadata = result["metadata"]
        assert metadata["faces"] == 50000
        assert metadata["compressionEnabled"] is True
        assert metadata["vertices"] > 0
        assert metadata["fileSizeBytes"] > 0
    
    def test_generate_mock_glb_without_compression(self):
        """Test mock GLB without Draco compression."""
        result = _generate_mock_glb_mesh(
            target_faces=10000,
            enable_draco=False
        )
        
        metadata = result["metadata"]
        assert metadata["compressionEnabled"] is False
        assert metadata["compressionRatio"] == 1.0
    
    def test_generate_mock_glb_various_face_counts(self):
        """Test mock GLB with different face counts."""
        for face_count in [1000, 10000, 50000, 100000]:
            result = _generate_mock_glb_mesh(
                target_faces=face_count,
                enable_draco=True
            )
            
            assert result["success"] is True
            assert result["metadata"]["faces"] == face_count
            # Vertices should be roughly half of faces
            assert result["metadata"]["vertices"] == int(face_count * 0.5)


class TestMetadataValidation:
    """Tests for mesh metadata validation."""
    
    @pytest.mark.asyncio
    async def test_metadata_contains_required_fields(self):
        """Test that metadata contains all required fields."""
        cell_data = {
            "inputImage": "data:image/png;base64,test",
            "reconstructionParams": {}
        }
        
        result = await execute_cell(cell_data)
        
        metadata = result["meshMetadata"]
        required_fields = [
            "vertices",
            "faces",
            "fileSizeBytes",
            "compressionRatio",
            "compressionEnabled",
            "generationTimeSeconds",
            "modelType"
        ]
        
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"
    
    @pytest.mark.asyncio
    async def test_metadata_types(self):
        """Test that metadata fields have correct types."""
        cell_data = {
            "inputImage": "data:image/png;base64,test",
            "reconstructionParams": {}
        }
        
        result = await execute_cell(cell_data)
        metadata = result["meshMetadata"]
        
        assert isinstance(metadata["vertices"], int)
        assert isinstance(metadata["faces"], int)
        assert isinstance(metadata["fileSizeBytes"], int)
        assert isinstance(metadata["compressionRatio"], (int, float))
        assert isinstance(metadata["compressionEnabled"], bool)
        assert isinstance(metadata["generationTimeSeconds"], (int, float))
        assert isinstance(metadata["modelType"], str)


class TestErrorHandling:
    """Tests for error handling in mesh generation."""
    
    @pytest.mark.asyncio
    async def test_handle_missing_input(self):
        """Test handling of missing input image."""
        result = await execute_cell({})
        
        assert result["success"] is False
        assert result["error"] is not None
        assert result["generatedMesh"] is None
    
    @pytest.mark.asyncio
    async def test_handle_invalid_params(self):
        """Test handling of invalid reconstruction parameters."""
        cell_data = {
            "inputImage": "data:image/png;base64,test",
            "reconstructionParams": {
                "targetFaces": -1000,  # Invalid: negative
                "compressionLevel": 999  # Invalid: out of range
            }
        }
        
        # Should still execute (validation happens in actual implementation)
        result = await execute_cell(cell_data)
        # Mock implementation doesn't validate, but real one should
        assert result is not None


class TestDataFormat:
    """Tests for data format validation."""
    
    def test_mock_glb_base64_format(self):
        """Test that mock GLB is valid base64."""
        result = _generate_mock_glb_mesh()
        
        mesh_data = result["mesh_data"]
        assert mesh_data.startswith("data:model/gltf-binary;base64,")
        
        # Extract base64 part
        base64_part = mesh_data.split(",")[1]
        
        # Should be valid base64 (no exception)
        import base64
        try:
            base64.b64decode(base64_part)
            assert True
        except Exception:
            pytest.fail("Invalid base64 encoding")
    
    @pytest.mark.asyncio
    async def test_output_format_consistency(self):
        """Test that output format is consistent."""
        cell_data = {
            "inputImage": "data:image/png;base64,test",
            "reconstructionParams": {}
        }
        
        result = await execute_cell(cell_data)
        
        # Check output structure
        assert "success" in result
        assert "generatedMesh" in result
        assert "meshMetadata" in result
        
        if result["success"]:
            assert result["generatedMesh"] is not None
            assert result["meshMetadata"] is not None


@pytest.mark.asyncio
async def test_integration_full_pipeline():
    """Integration test for full execution pipeline."""
    # Simulate full execution as would happen from API
    cell_data = {
        "inputImage": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "reconstructionParams": {
            "targetFaces": 50000,
            "enableDracoCompression": True,
            "compressionLevel": 7,
            "targetFileSizeMB": 5
        },
        "viewportSettings": {
            "autoRotate": True,
            "wireframeMode": False,
            "showGrid": True,
            "cameraPosition": [0, 1, 3]
        }
    }
    
    result = await execute_cell(cell_data)
    
    # Verify complete successful execution
    assert result["success"] is True
    assert result["generatedMesh"] is not None
    assert result["meshMetadata"] is not None
    
    # Verify metadata is comprehensive
    metadata = result["meshMetadata"]
    assert metadata["faces"] == 50000
    assert metadata["compressionEnabled"] is True
    assert metadata["fileSizeBytes"] > 0
    
    # Verify mesh data format
    assert result["generatedMesh"].startswith("data:model/gltf-binary;base64,")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
