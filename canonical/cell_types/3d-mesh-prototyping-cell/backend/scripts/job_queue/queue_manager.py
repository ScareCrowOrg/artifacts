"""
Job Queue Manager for 3D Mesh Generation

Implements Redis-based job queueing, status tracking, and result retrieval
for hybrid Windows Worker architecture.
"""

import logging
import base64
import json
import uuid
import time
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

from .file_manager import get_shared_volume_path

# Redis L1 client from canonical shared (single source of truth)
# Supports fallback: tries backend app context first, then direct connection
try:
    from canonical.shared.redis_client import get_redis_client
except ImportError:
    # Local dev fallback: add shared to path
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / 'shared'))
    from redis_client import get_redis_client

logger = logging.getLogger(__name__)


async def queue_3d_generation_job(
    input_image: str,
    target_faces: int = 50000,
    enable_draco: bool = True,
    compression_level: int = 7,
    target_size_mb: float = 5.0,
    model_type: str = "hunyuan3d"
) -> Dict[str, Any]:
    """
    Queue a 3D generation job to Redis for processing by Windows Worker.

    Phase 6 Hybrid Architecture with Model Routing:
    1. Generate unique job_id
    2. Write input image to shared volume
    3. Queue job metadata to Redis (includes model_type for routing)
    4. Return job_id for client polling

    Args:
        input_image: Base64-encoded PNG image
        target_faces: Target face count for decimation
        enable_draco: Enable Draco mesh compression
        compression_level: Draco compression level (0-10)
        target_size_mb: Target file size in MB
        model_type: 3D generation model to use ('hunyuan3d', default: 'hunyuan3d')

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
            
            # Log payload size for echo detection
            logger.info(f"Processing image of {len(image_bytes)} bytes")
            
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
        
        # Prepare job metadata - CRITICAL: Path Unification
        # All paths MUST use get_shared_volume_path() to ensure consistency
        # MVP 4.1 Path Mapping Architecture:
        # - Backend writes to: /app/.local-dev-data/scareverse-data/jobs/{id}/input.png
        # - Files visible in Windows at: <PROJECT_ROOT>\.local-dev-data\scareverse-data\jobs\{id}\input.png
        # - Worker mounts .local-dev-data/scareverse-data as /app/.local-dev-data/scareverse-data
        # - Worker reads from: /app/.local-dev-data/scareverse-data/jobs/{id}/input.png
        
        # Phase A: Use shared_volume_root for ALL path constructions
        shared_volume_root = get_shared_volume_path()
        worker_input_path = str(shared_volume_root / "jobs" / job_id / "input.png")
        worker_output_dir = str(shared_volume_root / "jobs" / job_id)
        
        # DEBUG LOG - Path Configuration (Critical for troubleshooting)
        logger.info(f"✅ Path unification verified:")
        logger.info(f"  Shared volume root: {shared_volume_root}")
        logger.info(f"  Backend writes to: {input_path}")
        logger.info(f"  Worker input path: {worker_input_path}")
        logger.info(f"  Worker output dir: {worker_output_dir}")
        
        job_data = {
            "job_id": job_id,
            "job_type": "3d_generation",  # Worker needs to know this is a 3D job
            "status": "queued",
            "created_at": timestamp,
            "model_type": model_type,  # Route to appropriate 3D service (sf3d or instantmesh)
            "input_image_path": worker_input_path,
            "output_dir": worker_output_dir,
            "parameters": json.dumps({
                "target_faces": target_faces,
                "enable_draco": enable_draco,
                "compression_level": compression_level,
                "target_size_mb": target_size_mb
            })
        }
        
        # Store job status in Redis as a Hash
        status_key = f"scareverse:3d-status:{job_id}"
        
        # Preventive cleanup: Delete any existing key to avoid WRONGTYPE errors
        # This ensures we always start with a fresh Hash, not a leftover String
        await redis_client.delete(status_key)
        
        # Store job data as a Hash using hmset
        await redis_client.hmset(status_key, job_data)
        await redis_client.expire(status_key, 3600)  # Expire after 1 hour
        
        logger.debug(f"Stored job status in Redis: {status_key}")

        # Queue job for worker (route to appropriate service based on model_type)
        # model_type can be: hunyuan3d (only supported local model)
        if model_type == "hunyuan3d":
            queue_key = "scareverse:hunyuan3d-jobs:queue"
        else:
            # Default to hunyuan3d for unknown types
            queue_key = "scareverse:hunyuan3d-jobs:queue"

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
    
    Retrieves job status and, if completed, reads the generated mesh
    from the shared volume.
    
    Args:
        job_id: Unique job identifier
    
    Returns:
        Dict containing:
            - status: Job status (queued/processing/completed/failed/not_found/error)
            - mesh_data: Base64 GLB data (if completed)
            - metadata: Processing metadata (if completed)
            - error: Error message (if failed or error)
    """
    try:
        redis_client = await get_redis_client()
        status_key = f"scareverse:3d-status:{job_id}"
        
        # Get job status from Redis (expecting a Hash)
        try:
            job_data = await redis_client.hgetall(status_key)
        except Exception as redis_error:
            # Handle WRONGTYPE error when key is not a Hash
            error_msg = str(redis_error)
            if "WRONGTYPE" in error_msg:
                logger.error(
                    f"Redis WRONGTYPE error for key {status_key}. "
                    f"Key exists but is not a Hash. This can happen if the key "
                    f"was created with 'set' instead of 'hset'. Consider deleting "
                    f"the key: redis-cli DEL {status_key}"
                )
                return {
                    "status": "error",
                    "error": "Job status key has wrong type. Please retry the job or contact support."
                }
            else:
                # Re-raise other Redis errors
                raise
        
        if not job_data:
            return {
                "status": "not_found",
                "error": "Job not found"
            }
        
        # Safely decode bytes if Redis client doesn't have decode_responses=True
        if job_data and isinstance(next(iter(job_data.values()), None), bytes):
            job_data = {k.decode('utf-8') if isinstance(k, bytes) else k: 
                       v.decode('utf-8') if isinstance(v, bytes) else v 
                       for k, v in job_data.items()}
        
        status = job_data.get("status", "unknown")
        
        if status == "completed":
            # Job completed - read GLB from shared volume
            # Phase B: Trust Redis - Extract optimized_mesh_path from Worker payload
            
            # CRITICAL: Read dynamic path from Worker instead of hardcoded "output.glb"
            optimized_mesh_path_str = job_data.get("optimized_mesh_path")
            
            if not optimized_mesh_path_str:
                logger.error(f"❌ Worker did not report 'optimized_mesh_path' in Redis payload")
                logger.error(f"   Job ID: {job_id}")
                logger.error(f"   Available keys in job_data: {list(job_data.keys())}")
                return {
                    "status": "failed",
                    "error": "Worker did not report output file path. This indicates a Worker-side failure."
                }
            
            # Sanitization: Normalize and resolve to absolute path
            output_path = Path(optimized_mesh_path_str.strip()).resolve()
            
            # DEBUG LOG (Crucial for troubleshooting "Output file not found" errors)
            logger.info(f"🔍 Attempting to read output file from Worker-reported path:")
            logger.info(f"  Job ID: {job_id}")
            logger.info(f"  Worker-reported path: {optimized_mesh_path_str}")
            logger.info(f"  Resolved absolute path: {output_path}")
            
            # Phase C: Active File Validation with Filesystem Cache Invalidation
            # Strategy: Retry with cache invalidation to handle volume sync delays
            file_found = False
            max_retries = 5
            retry_delay = 1.0
            
            for attempt in range(max_retries):
                # Force kernel to update file table by listing parent directory
                parent_dir = output_path.parent
                if parent_dir.exists():
                    try:
                        # This operation forces filesystem cache refresh
                        list(parent_dir.iterdir())
                    except (PermissionError, OSError) as e:
                        logger.warning(f"Failed to list directory for cache invalidation: {e}")
                
                # Check if file exists and has non-zero size
                if output_path.exists() and output_path.stat().st_size > 0:
                    file_found = True
                    if attempt > 0:
                        logger.info(f"✅ File detected after {attempt} retry attempt(s): {output_path}")
                    else:
                        logger.info(f"✅ File detected on first attempt: {output_path}")
                    break
                
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ Attempt {attempt + 1}/{max_retries}: File not visible. Retrying after {retry_delay}s...")
                    time.sleep(retry_delay)
            
            if file_found:
                # File successfully validated - read content
                with open(output_path, 'rb') as f:
                    glb_bytes = f.read()
                
                glb_base64 = base64.b64encode(glb_bytes).decode('utf-8')
                mesh_data = f"data:model/gltf-binary;base64,{glb_base64}"
                
                # Parse metadata from job_data
                # Metadata might be stored as JSON string in the hash
                metadata_json = job_data.get("metadata", "{}")
                try:
                    metadata = json.loads(metadata_json) if metadata_json and metadata_json != "{}" else {}
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse metadata JSON: {metadata_json}")
                    metadata = {}
                
                # Extract optimization status fields from job_data
                # These are set by the worker_bridge.py resilience fallback
                blender_optimized = job_data.get("blender_optimized")
                blender_error = job_data.get("blender_error")
                sf3d_completed = job_data.get("sf3d_completed")
                message = job_data.get("message")
                
                # Convert string booleans to actual booleans
                if blender_optimized is not None:
                    blender_optimized = blender_optimized in ['True', 'true', '1', True]
                if sf3d_completed is not None:
                    sf3d_completed = sf3d_completed in ['True', 'true', '1', True]
                
                # Add optimization status to metadata if not already present
                if blender_optimized is not None:
                    metadata['blenderOptimized'] = blender_optimized
                if blender_error:
                    metadata['blenderError'] = blender_error
                if sf3d_completed is not None:
                    metadata['sf3dCompleted'] = sf3d_completed
                if message:
                    metadata['message'] = message
                
                return {
                    "status": "completed",
                    "mesh_data": mesh_data,
                    "metadata": metadata,
                    "blender_optimized": blender_optimized,
                    "blender_error": blender_error,
                    "sf3d_completed": sf3d_completed,
                    "message": message
                }
            else:
                # Phase C Fallback: File not found after all retry attempts
                logger.error(f"❌ Failed to locate file after {max_retries} retry attempts")
                logger.error(f"   Expected path: {output_path}")
                
                # Diagnostic Step 1: Check if parent directory exists
                parent_dir = output_path.parent
                if parent_dir.exists():
                    try:
                        dir_contents = list(parent_dir.iterdir())
                        logger.error(f"📁 Parent directory exists: {parent_dir}")
                        logger.error(f"   Directory contains {len(dir_contents)} items:")
                        for item in dir_contents:
                            item_info = f"   - {item.name}"
                            if item.is_file():
                                try:
                                    size = item.stat().st_size
                                    item_info += f" (file, {size} bytes)"
                                except OSError:
                                    item_info += " (file, size unknown)"
                            else:
                                item_info += " (directory)"
                            logger.error(item_info)
                    except (PermissionError, OSError) as e:
                        logger.error(f"   Could not list directory contents: {e}")
                else:
                    logger.error(f"❌ Parent directory does not exist: {parent_dir}")
                    logger.error(f"   This suggests the Worker never started processing or job directory creation failed.")
                
                # Diagnostic Step 2: Check Worker-reported path structure
                logger.error(f"   Worker reported path: {optimized_mesh_path_str}")
                logger.error(f"   This suggests the Worker completed but the file is not visible to the Backend.")
                logger.error(f"   Possible causes:")
                logger.error(f"     1. Volume mount mismatch between Worker and Backend")
                logger.error(f"     2. Worker wrote to different location than reported")
                logger.error(f"     3. Filesystem synchronization delay (cache issue)")
                
                return {
                    "status": "failed",
                    "error": "Output file not found at Worker-reported path. Worker may have encountered an error during file write or volume mounting issue exists. Check Worker logs for details."
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
