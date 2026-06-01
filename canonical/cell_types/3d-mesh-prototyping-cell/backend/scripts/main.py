"""
3D Mesh Prototyping Cell - Backend Execution Logic

Implements Single Image-to-3D reconstruction pipeline with hybrid job queueing architecture.

BaseCell v1.0 Implementation:
- MeshPrototypingCell class inherits from BaseCell (defined at end of file)
- Implements execute(), describe(), validate(), health_check()
- Backward compatible through execute_cell() wrapper
- Legacy handlers remain for stability

Phase 6 Update: Adds hybrid generation mode routing (cloud-api, local-gpu, manual-upload).
- Supports multiple generation modes for flexible deployment scenarios
- cloud-api: External API-based generation (placeholder for future integration)
- local-gpu: Redis-based job queueing for Windows Worker integration
- manual-upload: Direct file upload without processing

Architecture:
- Manager Cell (Kind/Linux): API, job queueing, result retrieval
- Windows Worker: GPU processing (InstantMesh + Blender)
- Redis: Job queue and status tracking
- Shared Volume: File transfer between Manager and Worker
"""

from typing import Dict, Any, List, Optional
import logging
import os
import sys

# Add backend to path for importing config module
backend_path = os.path.join(os.path.dirname(__file__), '../../../backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Add backend for BaseCell import
basecell_backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../../backend'))
if basecell_backend_path not in sys.path:
    sys.path.insert(0, basecell_backend_path)

from job_queue import queue_3d_generation_job, get_job_status

# Import configuration from backend (follows project standards)
try:
    from app.config import STABLE_FAST_3D_API_KEY
except ImportError:
    # Fallback if config is not available
    STABLE_FAST_3D_API_KEY = os.getenv("STABLE_FAST_3D_API_KEY")

try:
    from app.core.base_cell import BaseCell, CellResult, CellMetadata, ValidationError, EnvironmentConfig, HealthCheckResult, HealthStatus
    BASECELL_AVAILABLE = True
except ImportError:
    # Graceful degradation if BaseCell not available
    BASECELL_AVAILABLE = False
    BaseCell = object  # Fallback

logger = logging.getLogger(__name__)


async def execute_cell(cell_data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
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
            - modelType: 3D model to use (optional, defaults to 'hunyuan3d')
        user_id: Optional user identifier for audit/logging

    Returns:
        Dict with execution results:
            - success: Boolean indicating if operation succeeded
            - job_id: Unique job identifier (for local-gpu mode)
            - message: Status message
            - error: Error message if execution failed
    """
    try:
        # DEBUG: Log all cell_data keys to see what's being received
        logger.info(f"🔍 DEBUG cell_data keys: {list(cell_data.keys())}")

        # BaseCell wraps input in 'input_data', so modelType is nested
        input_data = cell_data.get('input_data', {})
        logger.info(f"🔍 DEBUG input_data keys: {list(input_data.keys())}")
        logger.info(f"🔍 DEBUG modelType value: {input_data.get('modelType')}")

        input_image = cell_data.get('inputImage')
        reconstruction_params = cell_data.get('reconstructionParams', {})
        generation_mode = cell_data.get('generationMode', 'local-gpu')
        model_type = input_data.get('modelType', 'hunyuan3d')  # Default: Hunyuan3D v2 FP8 via ComfyUI

        if not input_image:
            return {
                "success": False,
                "error": "No input image provided. Please upload a PNG image for 3D reconstruction.",
                "job_id": None
            }
        
        logger.info(f"Executing 3D mesh reconstruction with mode: {generation_mode}")
        logger.info(f"Using 3D model: {model_type}")
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
    import sys
    import os

    logger.info("Cloud API generation requested (Stable Fast 3D)")

    # Import the Stable Fast 3D client
    # Note: Import is inside function because stable_fast_3d_client is a local module
    # in the same directory. This allows graceful handling if the module is unavailable.
    # For ephemeral cell execution, we need to ensure the scripts directory is in sys.path
    try:
        # Ensure the scripts directory is in sys.path for ephemeral execution
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)

        from stable_fast_3d_client import create_client
    except ImportError as e:
        error_msg = "Failed to import Stable Fast 3D client"
        logger.error(f"{error_msg}: {str(e)}")
        return {
            "success": False,
            "error": error_msg,
            "mesh_data": None,
            "metadata": None,
            "mode": "cloud-api"
        }

    # Create client (will load config from environment)
    client = create_client()

    if client is None:
        error_msg = "Stable Fast 3D API key not configured. Please set STABLE_FAST_3D_API_KEY in your environment."
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "mesh_data": None,
            "metadata": None,
            "mode": "cloud-api"
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
    Supports multiple 3D generation models via model_type parameter.

    Args:
        cell_data: Cell instance data with input image and parameters

    Returns:
        Dict with job queueing result
    """
    logger.info("Local GPU generation requested (Redis job queue)")

    input_image = cell_data.get('inputImage')
    reconstruction_params = cell_data.get('reconstructionParams', {})

    # Extract modelType from nested input_data (BaseCell wrapper structure)
    input_data = cell_data.get('input_data', {})
    model_type = input_data.get('modelType', 'hunyuan3d')  # Default: Hunyuan3D v2 FP8 via ComfyUI

    logger.info(f"Using 3D generation model: {model_type}")

    # Extract assignee_id for Auto-Swap storage routing (Redis Magro)
    # Must match content-manager's convention: cell_data.get("assignee_id") or cell_data.get("user_id")
    assignee_id = cell_data.get("assignee_id") or cell_data.get("user_id")
    logger.info("[Redis Magro] assignee_id: %s", assignee_id)

    # Queue job to Redis (non-blocking)
    job_result = await queue_3d_generation_job(
        input_image=input_image,
        target_faces=reconstruction_params.get('targetFaces', 50000),
        enable_draco=reconstruction_params.get('enableDracoCompression', True),
        compression_level=reconstruction_params.get('compressionLevel', 7),
        target_size_mb=reconstruction_params.get('targetFileSizeMB', 5),
        model_type=model_type,
        assignee_id=assignee_id,
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


# ============ BASECELL v1.0 IMPLEMENTATION ============


class MeshPrototypingCell(BaseCell):
    """
    3D Mesh Prototyping Cell implementing BaseCell v1.0 framework.
    
    This cell provides Single Image-to-3D reconstruction using Stable Fast 3D
    through Redis job queueing to Windows Worker.
    
    Architecture:
    - Manager Cell (Kind/Linux): API, job queueing, result polling
    - Windows Worker: GPU processing (SF3D + Blender)
    - Redis: Job queue and status tracking
    - Shared Volume: File transfer between Manager and Worker
    
    Key Features:
    - Hybrid generation modes (cloud-api, local-gpu, manual-upload)
    - Redis-based job queueing for GPU operations
    - Job status polling and result retrieval
    - Graceful fallbacks and error handling
    """
    
    def __init__(self):
        """Initialize 3D Mesh Prototyping Cell"""
        self.redis_client = None
        self.sf3d_service = None
        
    async def setup(self, config: EnvironmentConfig) -> None:
        """
        Initialize lightweight resources.
        
        Sets up Redis connection for job queueing and optional
        Stable Fast 3D service connection.
        
        Note: Does NOT allocate GPU/VRAM - managed by Windows Worker.
        
        Args:
            config: Environment configuration
        """
        try:
            logger.info("Initializing 3D Mesh Prototyping Cell resources")
            # Note: Redis connection initialization would go here
            # For now, we use lazy initialization in execute()
            # to maintain compatibility with current architecture
            logger.info("3D Mesh Prototyping Cell setup complete")
        except Exception as e:
            logger.warning(f"Non-critical setup error: {e}")
    
    async def teardown(self) -> None:
        """
        Clean up lightweight resources.
        
        Closes Redis connections and cleans up any listeners.
        Does NOT deallocate GPU/VRAM (not cell's responsibility).
        """
        try:
            logger.info("Tearing down 3D Mesh Prototyping Cell resources")
            if self.redis_client:
                self.redis_client = None
            logger.info("3D Mesh Prototyping Cell teardown complete")
        except Exception as e:
            logger.error(f"Error during teardown: {e}", exc_info=True)
    
    async def execute(self, input: Dict[str, Any]) -> CellResult:
        """
        Execute 3D mesh reconstruction.
        
        Routes to appropriate handler based on generation mode:
        - 'cloud-api': External API-based generation
        - 'local-gpu': Redis job queueing for Windows Worker (default)
        - 'manual-upload': Direct file upload without processing
        
        Args:
            input: Input data containing:
                - inputImage: Base64-encoded PNG image (required)
                - reconstructionParams: Optional parameters
                - generationMode: Generation mode (optional, default: 'local-gpu')
        
        Returns:
            CellResult with success status, output data, and execution metadata
        """
        import time
        start_time = time.time()
        
        try:
            # Validate input
            validation_errors = self.validate(input)
            if validation_errors:
                return CellResult(
                    success=False,
                    output={},
                    error=f"Validation failed: {', '.join([e.message for e in validation_errors])}",
                    execution_time=(time.time() - start_time) * 1000
                )
            
            # Route to appropriate handler
            generation_mode = input.get('generationMode', 'local-gpu')
            result = await route_generation_request(input, generation_mode)
            
            # Convert legacy result format to CellResult
            execution_time = (time.time() - start_time) * 1000
            
            return CellResult(
                success=result.get('success', False),
                output=result,
                artifacts=[result.get('job_id')] if result.get('job_id') else [],
                execution_time=execution_time,
                execution_steps=[f"Generation mode: {generation_mode}"],
                metadata={'generation_mode': generation_mode}
            )
            
        except Exception as e:
            logger.error(f"Error in 3D Mesh Prototyping Cell execution: {e}", exc_info=True)
            return CellResult(
                success=False,
                output={},
                error=str(e),
                execution_time=(time.time() - start_time) * 1000
            )
    
    async def describe(self) -> CellMetadata:
        """
        Describe 3D Mesh Prototyping Cell capabilities.
        
        Returns metadata about inputs, outputs, and configuration.
        
        Returns:
            CellMetadata with cell description
        """
        return CellMetadata(
            id='3d-mesh-prototyping-cell',
            name='3D Mesh Prototyping',
            version='1.0.0',
            description='Single Image-to-3D reconstruction using Stable Fast 3D and GPU Worker',
            inputs={
                'inputImage': 'string (base64 PNG, required)',
                'reconstructionParams': 'object (optional)',
                'generationMode': 'string (cloud-api | local-gpu | manual-upload, default: local-gpu)'
            },
            outputs={
                'success': 'boolean',
                'job_id': 'string (for local-gpu mode)',
                'glb_url': 'string (3D model URL)',
                'message': 'string',
                'error': 'string (if failed)'
            },
            tags=['3d', 'reconstruction', 'mesh', 'stable-fast-3d', 'image-to-3d'],
            required_resources=['redis', 'windows-worker', 'stable-fast-3d'],
            estimated_duration_seconds=45.0
        )
    
    def validate(self, input: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate input data.
        
        Args:
            input: Input data to validate
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate inputImage
        if not input.get('inputImage'):
            errors.append(ValidationError(
                field='inputImage',
                message='inputImage is required (base64-encoded PNG)'
            ))
        
        # Validate generationMode if provided
        generation_mode = input.get('generationMode', 'local-gpu')
        valid_modes = ['cloud-api', 'local-gpu', 'manual-upload']
        if generation_mode not in valid_modes:
            errors.append(ValidationError(
                field='generationMode',
                message=f"Invalid generationMode '{generation_mode}'. Must be one of: {', '.join(valid_modes)}"
            ))
        
        return errors
    
    async def health_check(self) -> HealthCheckResult:
        """
        Check if 3D Mesh Prototyping Cell can execute.
        
        Validates connectivity to Redis and optionally Stable Fast 3D service.
        
        Returns:
            HealthCheckResult with status and diagnostic info
        """
        try:
            # Check if job queue module is available
            # This is a soft check - cell can still work with different modes
            try:
                from job_queue import queue_3d_generation_job
                job_queue_available = True
            except ImportError:
                job_queue_available = False
            
            if job_queue_available:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    reason="3D Mesh Prototyping Cell is fully operational"
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    reason="Job queue module not available (limited functionality)"
                )
        
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return HealthCheckResult(
                status=HealthStatus.UNAVAILABLE,
                reason=f"Health check error: {str(e)}"
            )


# Create global instance for backward compatibility
_mesh_prototyping_cell_instance = None


def get_mesh_prototyping_cell() -> MeshPrototypingCell:
    """Get or create the global 3D Mesh Prototyping Cell instance"""
    global _mesh_prototyping_cell_instance
    if not BASECELL_AVAILABLE:
        return None
    if _mesh_prototyping_cell_instance is None:
        _mesh_prototyping_cell_instance = MeshPrototypingCell()
    return _mesh_prototyping_cell_instance


# ============ MAIN EXECUTION ============


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

