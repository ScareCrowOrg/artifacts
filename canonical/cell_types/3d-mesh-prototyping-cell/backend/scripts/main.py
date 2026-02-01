"""
3D Mesh Prototyping Cell - Backend Execution Logic

Implements Single Image-to-3D reconstruction pipeline with hybrid job queueing architecture.

Phase 6 Update: Adds hybrid generation mode routing (cloud-api, local-gpu, manual-upload).
- Supports multiple generation modes for flexible deployment scenarios
- cloud-api: External API-based generation (placeholder for future integration)
- local-gpu: Redis-based job queueing for Windows Worker integration
- manual-upload: Direct file upload without processing

Architecture:
- Manager Cell (Kind/Linux): API, job queueing, result retrieval
- Windows Worker: GPU processing (SF3D + Blender)
- Redis: Job queue and status tracking
- Shared Volume: File transfer between Manager and Worker
"""

from typing import Dict, Any
import logging

from job_queue import queue_3d_generation_job, get_job_status

logger = logging.getLogger(__name__)


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the 3D mesh prototyping cell with hybrid generation mode routing.
    
    Phase 6 Architecture:
    1. Extract generationMode from cell_data (default: 'local-gpu')
    2. Route to appropriate generation handler
    3. Return job_id for polling (local-gpu) or immediate result (other modes)
    
    Generation Modes:
    - 'local-gpu': Redis job queueing for Windows Worker (default)
    - 'cloud-api': External API-based generation (placeholder)
    - 'manual-upload': Direct file upload without processing
    
    Args:
        cell_data: Cell instance data containing:
            - inputImage: Base64-encoded PNG image for reconstruction
            - reconstructionParams: Parameters for 3D generation
            - generationMode: Generation mode (optional, defaults to 'local-gpu')
    
    Returns:
        Dict with execution results:
            - success: Boolean indicating if operation succeeded
            - job_id: Unique job identifier (for local-gpu mode)
            - message: Status message
            - error: Error message if execution failed
    """
    try:
        input_image = cell_data.get('inputImage')
        reconstruction_params = cell_data.get('reconstructionParams', {})
        generation_mode = cell_data.get('generationMode', 'local-gpu')
        
        if not input_image:
            return {
                "success": False,
                "error": "No input image provided. Please upload a PNG image for 3D reconstruction.",
                "job_id": None
            }
        
        logger.info(f"Executing 3D mesh reconstruction with mode: {generation_mode}")
        logger.debug(f"Reconstruction params: {reconstruction_params}")
        
        # Route to appropriate generation handler
        result = await route_generation_request(cell_data, generation_mode)
        
        return result
    
    except Exception as e:
        logger.error(f"Error in 3D mesh prototyping cell execution: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
            "job_id": None
        }



async def route_generation_request(cell_data: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """
    Route 3D generation request to appropriate handler based on mode.
    
    Generation Modes:
    - 'cloud-api': External API-based generation (placeholder for future integration)
    - 'local-gpu': Redis-based job queueing for Windows Worker
    - 'manual-upload': Direct file upload without processing
    
    Args:
        cell_data: Cell instance data with input image and parameters
        mode: Generation mode string
    
    Returns:
        Dict with execution results based on mode
    """
    try:
        if mode == 'cloud-api':
            return await handle_cloud_api_generation(cell_data)
        elif mode == 'local-gpu':
            return await handle_local_gpu_generation(cell_data)
        elif mode == 'manual-upload':
            return await handle_manual_upload(cell_data)
        else:
            logger.error(f"Unknown generation mode: {mode}")
            return {
                "success": False,
                "error": f"Unknown generation mode: {mode}. Supported modes: cloud-api, local-gpu, manual-upload",
                "job_id": None
            }
    except Exception as e:
        logger.error(f"Error routing generation request: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Routing error: {str(e)}",
            "job_id": None
        }


async def handle_cloud_api_generation(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle 3D generation via external cloud API (Stable Fast 3D).
    
    Integrates with Stability AI's Stable Fast 3D API to generate 3D meshes
    from single images. Requires API key configuration.
    
    Args:
        cell_data: Cell instance data with input image and parameters
    
    Returns:
        Dict with API generation result (success/error, mesh data, metadata)
    """
    logger.info("Cloud API generation requested (Stable Fast 3D)")
    
    # Import the Stable Fast 3D client
    # Note: Import is inside function because stable_fast_3d_client is a local module
    # in the same directory. This allows graceful handling if the module is unavailable.
    try:
        from stable_fast_3d_client import create_client
    except ImportError:
        logger.error("Failed to import Stable Fast 3D client")
        return {
            "success": False,
            "error": "Stable Fast 3D client module not available",
            "mesh_data": None,
            "metadata": None
        }
    
    # Create client (will load config from environment)
    client = create_client()
    
    if client is None:
        logger.error("Stable Fast 3D API key not configured")
        return {
            "success": False,
            "error": "Stable Fast 3D API key not configured. Please set STABLE_FAST_3D_API_KEY in your environment.",
            "mesh_data": None,
            "metadata": None
        }
    
    # Extract input image
    input_image = cell_data.get('inputImage')
    if not input_image:
        logger.error("No input image provided")
        return {
            "success": False,
            "error": "No input image provided for 3D generation",
            "mesh_data": None,
            "metadata": None
        }
    
    # Extract reconstruction parameters
    reconstruction_params = cell_data.get('reconstructionParams', {})
    texture_resolution = reconstruction_params.get('textureResolution', 1024)
    foreground_ratio = reconstruction_params.get('foregroundRatio', 0.85)
    
    logger.info(f"Generating 3D mesh with params: texture_resolution={texture_resolution}, foreground_ratio={foreground_ratio}")
    
    # Call Stable Fast 3D API
    result = client.generate_mesh(
        image_data=input_image,
        texture_resolution=texture_resolution,
        foreground_ratio=foreground_ratio
    )
    
    # Add mode to result
    if result.get("success"):
        result["mode"] = "cloud-api"
        result["message"] = "3D mesh generated successfully via Stable Fast 3D API"
        logger.info("Cloud API generation completed successfully")
    else:
        logger.error(f"Cloud API generation failed: {result.get('error')}")
    
    return result


async def handle_local_gpu_generation(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle 3D generation via local GPU worker (Redis job queue).
    
    This is the default mode for Windows Worker integration.
    Jobs are queued to Redis and processed asynchronously.
    
    Args:
        cell_data: Cell instance data with input image and parameters
    
    Returns:
        Dict with job queueing result
    """
    logger.info("Local GPU generation requested (Redis job queue)")
    
    input_image = cell_data.get('inputImage')
    reconstruction_params = cell_data.get('reconstructionParams', {})
    
    # Queue job to Redis (non-blocking)
    job_result = await queue_3d_generation_job(
        input_image=input_image,
        target_faces=reconstruction_params.get('targetFaces', 50000),
        enable_draco=reconstruction_params.get('enableDracoCompression', True),
        compression_level=reconstruction_params.get('compressionLevel', 7),
        target_size_mb=reconstruction_params.get('targetFileSizeMB', 5)
    )
    
    if job_result.get("success"):
        logger.info(f"Job queued successfully: {job_result.get('job_id')}")
        return {
            "success": True,
            "job_id": job_result.get("job_id"),
            "mode": "local-gpu",
            "message": "3D mesh generation job queued successfully"
        }
    else:
        logger.error(f"Job queueing failed: {job_result.get('error')}")
        return {
            "success": False,
            "error": job_result.get("error", "Unknown error during job queueing"),
            "job_id": None
        }


async def handle_manual_upload(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle manual file upload mode (no processing needed).
    
    In this mode, the user has already uploaded a 3D mesh file.
    No generation or processing is required.
    
    Args:
        cell_data: Cell instance data with uploaded file
    
    Returns:
        Dict with success confirmation
    """
    logger.info("Manual upload mode - no processing required")
    
    return {
        "success": True,
        "mode": "manual-upload",
        "message": "File upload confirmed. No processing required."
    }


# Legacy mock function kept for backward compatibility and testing
def generate_3d_mesh_from_image(
    input_image: str,
    target_faces: int = 50000,
    enable_draco: bool = True,
    compression_level: int = 7,
    target_size_mb: float = 5.0
) -> Dict[str, Any]:
    """
    Generate 3D mesh from single image using GPU-accelerated reconstruction.
    
    Pipeline stages:
        1. Image preprocessing (resize, normalize)
        2. AI model inference (Single Image-to-3D reconstruction)
        3. Mesh post-processing (decimation, UV mapping)
        4. GLB export with Draco compression
        5. Size optimization to meet target file size
    
    Args:
        input_image: Base64-encoded PNG image
        target_faces: Target face count for decimation
        enable_draco: Enable Draco mesh compression
        compression_level: Draco compression level (0-10)
        target_size_mb: Target file size in MB
    
    Returns:
        Dict containing:
            - success: Boolean
            - mesh_data: Base64-encoded GLB mesh
            - metadata: Mesh statistics
            - error: Error message if failed
    
    GPU Requirements:
        - CUDA-enabled GPU (RTX 4070 recommended)
        - CUDA 12.1+ with cuDNN 8+
        - Device mapping via /dev/nvidia* in Kind cluster
        - nvidia-container-runtime configured
    
    TODO:
        - Integrate Stable Fast 3D model (preferred for speed <1s on RTX 4070)
        - Implement mesh decimation with Blender/Trimesh
        - Add Draco compression via gltf-pipeline
        - Add GPU device detection and validation
        - Implement model weight caching to host volume
    """
    try:
        logger.info("GPU-based 3D reconstruction not yet implemented")
        logger.info("Returning mock GLB mesh for MVP testing")
        
        # MVP: Return a mock result
        # This will be replaced with actual model inference
        mock_result = _generate_mock_glb_mesh(
            target_faces=target_faces,
            enable_draco=enable_draco
        )
        
        return mock_result
    
    except Exception as e:
        logger.error(f"Error in 3D mesh generation: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"3D mesh generation failed: {str(e)}",
            "mesh_data": None,
            "metadata": None
        }


def _generate_mock_glb_mesh(
    target_faces: int = 50000,
    enable_draco: bool = True
) -> Dict[str, Any]:
    """
    Generate a mock GLB mesh for testing purposes.
    
    This is a placeholder that returns a simple cube GLB file.
    Will be replaced with actual 3D reconstruction when GPU is available.
    
    Args:
        target_faces: Target face count (for metadata simulation)
        enable_draco: Whether Draco compression is enabled (for metadata)
    
    Returns:
        Dict with mock mesh data and metadata
    """
    # Simple GLB cube (minimal valid GLB file)
    # This is a base64-encoded minimal GLB with a cube geometry
    mock_glb_base64 = (
        "Z2xURgIAAABABAAAAQAAAP////8AAAAAAQAAAP////8CAAAAjAAAAFYAAAABAAAA"
        "AAAAAAEAAAD/////AAAAADwAAAABAAAAAAAAAAAAAAAAAAAAPwAAAAEAAACamZk/"
        "zczMPpmZGT+amRk/AAAAAP//fz8AAAAAzczMPZmZGT8AAAAAmpmZPgAAAACamZk+"
        "AAAAAAAAAD8AAAAAzczMPQAAAACamZk+AAAAAJqZmT4AAAAAZmZmPgAAAABmZmY+"
    )
    
    # Calculate mock metadata
    estimated_vertices = int(target_faces * 0.5)  # Rough estimate
    estimated_size = len(mock_glb_base64) * 0.75  # Base64 to bytes
    compression_ratio = 0.3 if enable_draco else 1.0
    
    metadata = {
        "vertices": estimated_vertices,
        "faces": target_faces,
        "fileSizeBytes": int(estimated_size * compression_ratio),
        "compressionRatio": compression_ratio,
        "compressionEnabled": enable_draco,
        "generationTimeSeconds": 0.1,  # Mock time
        "modelType": "mock_cube",
        "note": "This is a mock mesh for testing. Real 3D reconstruction requires GPU setup."
    }
    
    logger.info(f"Generated mock GLB mesh: {metadata}")
    
    return {
        "success": True,
        "mesh_data": f"data:model/gltf-binary;base64,{mock_glb_base64}",
        "metadata": metadata
    }


if __name__ == "__main__":
    # Allow standalone execution for testing
    import json
    import sys
    import asyncio
    
    async def main():
        """Standalone execution entry point for testing."""
        if len(sys.argv) > 1:
            cell_data = json.loads(sys.argv[1])
        else:
            # Test data with default local-gpu mode
            cell_data = {
                "inputImage": "data:image/png;base64,iVBORw0KGgo...",
                "reconstructionParams": {
                    "targetFaces": 50000,
                    "enableDracoCompression": True,
                    "compressionLevel": 7,
                    "targetFileSizeMB": 5
                },
                "generationMode": "local-gpu"
            }
        
        result = await execute_cell(cell_data)
        print(json.dumps(result, indent=2))
    
    asyncio.run(main())

