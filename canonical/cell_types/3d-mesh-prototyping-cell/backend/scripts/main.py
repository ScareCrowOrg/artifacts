"""
3D Mesh Prototyping Cell - Backend Execution Logic

Implements Single Image-to-3D reconstruction pipeline with hybrid job queueing architecture.

Phase 5 Update: Implements Redis-based job queueing for hybrid Windows Worker integration.
- Jobs are queued to Redis with input image written to shared volume
- Windows Worker polls queue and processes jobs using SF3D + Blender pipeline
- Results are accessed via shared volume and returned to client

Architecture:
- Manager Cell (Kind/Linux): API, job queueing, result retrieval
- Windows Worker: GPU processing (SF3D + Blender)
- Redis: Job queue and status tracking
- Shared Volume: File transfer between Manager and Worker
"""

from typing import Dict, Any, Optional
import logging
import base64
import json
import uuid
import time
import asyncio
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


async def execute_cell(cell_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the 3D mesh prototyping cell with hybrid job queueing.
    
    Phase 5 Architecture:
    1. Generate unique job_id
    2. Write input image to shared volume
    3. Queue job to Redis with parameters
    4. Return job_id immediately (client polls for status)
    
    The Windows Worker will:
    - Poll Redis queue for jobs
    - Process using SF3D + Blender pipeline
    - Write results to shared volume
    - Update job status in Redis
    
    Args:
        cell_data: Cell instance data containing:
            - inputImage: Base64-encoded PNG image for reconstruction
            - reconstructionParams: Parameters for 3D generation
    
    Returns:
        Dict with job queueing results:
            - success: Boolean indicating if job was queued
            - job_id: Unique job identifier for status polling
            - message: Status message
            - error: Error message if queueing failed
    """
    try:
        input_image = cell_data.get('inputImage')
        reconstruction_params = cell_data.get('reconstructionParams', {})
        
        if not input_image:
            return {
                "success": False,
                "error": "No input image provided. Please upload a PNG image for 3D reconstruction.",
                "job_id": None
            }
        
        logger.info("Queueing 3D mesh reconstruction job...")
        logger.debug(f"Reconstruction params: {reconstruction_params}")
        
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
                "message": "3D mesh generation job queued successfully"
            }
        else:
            logger.error(f"Job queueing failed: {job_result.get('error')}")
            return {
                "success": False,
                "error": job_result.get("error", "Unknown error during job queueing"),
                "job_id": None
            }
    
    except Exception as e:
        logger.error(f"Error in 3D mesh prototyping cell execution: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
            "job_id": None
        }

async def queue_3d_generation_job(
    input_image: str,
    target_faces: int = 50000,
    enable_draco: bool = True,
    compression_level: int = 7,
    target_size_mb: float = 5.0
) -> Dict[str, Any]:
    """
    Queue a 3D generation job to Redis for processing by Windows Worker.
    
    Phase 5 Hybrid Architecture:
    1. Generate unique job_id
    2. Write input image to shared volume
    3. Queue job metadata to Redis
    4. Return job_id for client polling
    
    Args:
        input_image: Base64-encoded PNG image
        target_faces: Target face count for decimation
        enable_draco: Enable Draco mesh compression
        compression_level: Draco compression level (0-10)
        target_size_mb: Target file size in MB
    
    Returns:
        Dict containing:
            - success: Boolean
            - job_id: Unique job identifier
            - error: Error message if failed
    """
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        logger.info(f"Queueing 3D generation job: {job_id}")
        
        # Get Redis client and shared volume path
        redis_client = await get_redis_client()
        shared_volume = get_shared_volume_path()
        
        # Create job directory in shared volume
        job_dir = shared_volume / "jobs" / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Job persistence path: {job_dir}")
        logger.info(f"Resolved job directory (absolute): {job_dir.resolve()}")
        
        # Write input image to shared volume
        input_path = job_dir / "input.png"
        try:
            # Decode base64 image
            if ',' in input_image:
                # Remove data:image/png;base64, prefix
                image_data = input_image.split(',', 1)[1]
            else:
                image_data = input_image
            
            image_bytes = base64.b64decode(image_data)
            
            bytes_written = 0
            with open(input_path, 'wb') as f:
                bytes_written = f.write(image_bytes)
                f.flush()  # Ensure data is written to disk
            
            # Verify file was written successfully
            try:
                file_size = input_path.stat().st_size
            except FileNotFoundError:
                raise IOError(f"Failed to write file to {input_path}")
            
            logger.info(f"✅ Wrote input image to: {input_path}")
            logger.info(f"   Absolute path: {input_path.resolve()}")
            logger.info(f"   File size: {file_size} bytes (expected: {len(image_bytes)} bytes)")
            
            # Validate file size matches
            if file_size != len(image_bytes):
                raise IOError(f"File size mismatch: wrote {len(image_bytes)} bytes but file is {file_size} bytes")
            
        except Exception as e:
            logger.error(f"Failed to write input image: {e}")
            return {
                "success": False,
                "error": f"Failed to write input image: {str(e)}",
                "job_id": None
            }
        
        # Prepare job metadata
        # Worker expects paths relative to its SHARED_VOLUME mount point (/data)
        # Backend writes to shared_volume (/mnt/wsl/scareverse by default)
        # These must align: Backend writes to /mnt/wsl/scareverse/jobs/{id}/input.png
        # Worker reads from /data/jobs/{id}/input.png (where /data is mounted from /mnt/wsl/scareverse)
        worker_input_path = f"/data/jobs/{job_id}/input.png"
        worker_output_dir = f"/data/jobs/{job_id}"
        
        logger.info(f"Path mapping for worker:")
        logger.info(f"  Backend writes to: {input_path}")
        logger.info(f"  Worker will read from: {worker_input_path}")
        logger.info(f"  Worker output dir: {worker_output_dir}")
        
        job_data = {
            "job_id": job_id,
            "status": "queued",
            "created_at": timestamp,
            "input_image_path": worker_input_path,
            "output_dir": worker_output_dir,
            "parameters": json.dumps({
                "target_faces": target_faces,
                "enable_draco": enable_draco,
                "compression_level": compression_level,
                "target_size_mb": target_size_mb
            })
        }
        
        # Store job status in Redis
        status_key = f"scareverse:3d-status:{job_id}"
        await redis_client.hmset(status_key, job_data)
        await redis_client.expire(status_key, 3600)  # Expire after 1 hour
        
        logger.debug(f"Stored job status in Redis: {status_key}")
        
        # Queue job for worker
        queue_key = "scareverse:3d-jobs:queue"
        await redis_client.lpush(queue_key, json.dumps(job_data))
        
        logger.info(f"Job {job_id} queued successfully")
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "Job queued successfully"
        }
        
    except Exception as e:
        logger.error(f"Error queueing 3D generation job: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Job queueing failed: {str(e)}",
            "job_id": None
        }


async def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Get the status of a 3D generation job from Redis.
    
    Args:
        job_id: Unique job identifier
    
    Returns:
        Dict containing:
            - status: Job status (queued/processing/completed/failed)
            - mesh_data: Base64 GLB data (if completed)
            - metadata: Processing metadata (if completed)
            - error: Error message (if failed)
    """
    try:
        redis_client = await get_redis_client()
        status_key = f"scareverse:3d-status:{job_id}"
        
        # Get job status from Redis
        job_data = await redis_client.hgetall(status_key)
        
        if not job_data:
            return {
                "status": "not_found",
                "error": "Job not found"
            }
        
        status = job_data.get("status", "unknown")
        
        if status == "completed":
            # Job completed - read GLB from shared volume
            shared_volume = get_shared_volume_path()
            output_path = shared_volume / "jobs" / job_id / "output.glb"
            
            if output_path.exists():
                with open(output_path, 'rb') as f:
                    glb_bytes = f.read()
                
                glb_base64 = base64.b64encode(glb_bytes).decode('utf-8')
                mesh_data = f"data:model/gltf-binary;base64,{glb_base64}"
                
                # Parse metadata from job_data
                metadata_json = job_data.get("metadata", "{}")
                metadata = json.loads(metadata_json) if metadata_json else {}
                
                return {
                    "status": "completed",
                    "mesh_data": mesh_data,
                    "metadata": metadata
                }
            else:
                return {
                    "status": "failed",
                    "error": "Output file not found"
                }
        
        elif status == "failed":
            error = job_data.get("error", "Unknown error")
            return {
                "status": "failed",
                "error": error
            }
        
        else:
            # Job still in progress (queued or processing)
            return {
                "status": status
            }
        
    except Exception as e:
        logger.error(f"Error getting job status: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"Status retrieval failed: {str(e)}"
        }


async def get_redis_client():
    """
    Get Redis client for job queueing.
    
    Returns:
        Redis client instance
    """
    try:
        # Try to import from core (when running as part of backend app)
        try:
            from app.core.redis_client import get_redis_client as get_core_redis
            return await get_core_redis()
        except (ImportError, ModuleNotFoundError):
            # Fallback: create Redis client directly (standalone execution)
            import redis.asyncio as redis
            import os
            
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to get Redis client: {e}")
        raise


def get_shared_volume_path() -> Path:
    """
    Get the shared volume path for file transfer with Windows Worker.
    
    Path Mapping Architecture (Updated MVP 4.1):
    - Backend (Kind/Linux): Uses /app volume mount (project root in Kind)
    - Worker (Windows Docker): Mounts project's .local-dev-data/scareverse-data as /data
    - Files written by Backend to /app/.local-dev-data/scareverse-data/jobs/{id}/input.png
    - Are visible in Windows at [PROJECT_ROOT]\.local-dev-data\scareverse-data\jobs\{id}\input.png
    - Are read by Worker from /data/jobs/{id}/input.png
    
    The SHARED_VOLUME_PATH for Backend should be /app/.local-dev-data/scareverse-data (default)
    The SHARED_VOLUME for Worker should be /data (default, mounting .local-dev-data/scareverse-data)
    
    Returns:
        Path object pointing to shared volume (Backend perspective)
    """
    import os
    
    # Use environment variable or default to /app bridge path
    shared_volume_env = os.getenv('SHARED_VOLUME_PATH')
    if not shared_volume_env:
        # Fallback: Use /app volume mount (Kind hostPath -> project root)
        shared_volume_env = '/app/.local-dev-data/scareverse-data'
    
    shared_volume_path = Path(shared_volume_env)
    
    # Log the configuration for debugging
    logger.info(f"✅ Shared volume path configured: {shared_volume_path}")
    logger.debug(f"Shared volume exists: {shared_volume_path.exists()}")
    
    return shared_volume_path


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
        if len(sys.argv) > 1:
            cell_data = json.loads(sys.argv[1])
        else:
            # Test data
            cell_data = {
                "inputImage": "data:image/png;base64,iVBORw0KGgo...",
                "reconstructionParams": {
                    "targetFaces": 50000,
                    "enableDracoCompression": True,
                    "compressionLevel": 7,
                    "targetFileSizeMB": 5
                }
            }
        
        result = await execute_cell(cell_data)
        print(json.dumps(result, indent=2))
    
    asyncio.run(main())
