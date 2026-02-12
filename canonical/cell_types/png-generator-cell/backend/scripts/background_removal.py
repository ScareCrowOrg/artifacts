"""
Background Removal Integration for PNG Generator Cell

Provides GPU-accelerated background removal by delegating to the
Windows Worker via Redis queue.
"""

import logging
import uuid
import time
import json
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def queue_background_removal_job(
    input_image_base64: str,
    alpha_matting: bool = True,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Queue a background removal job to Redis for GPU Worker processing.
    
    This function:
    1. Creates a unique job_id
    2. Queues the job to Redis with REMOTE_REMBG type
    3. Polls Redis for job completion
    4. Returns the transparent PNG result
    
    Args:
        input_image_base64: Base64-encoded input image (with or without data URI prefix)
        alpha_matting: Enable alpha matting for better edge quality (default: True)
        timeout: Maximum time to wait for job completion in seconds
        
    Returns:
        Dict containing:
            - success: Boolean indicating success/failure
            - output_image_base64: Base64-encoded transparent PNG (if success)
            - error: Error message (if failure)
            - job_id: Unique job identifier
            - processing_time: Time taken by GPU worker
            
    Raises:
        Exception: If Redis connection fails or job times out
    """
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        logger.info(f"Queueing background removal job: {job_id}")
        
        # Get Redis client
        redis_client = await get_redis_client()
        
        # Strip data URI prefix if present
        if ',' in input_image_base64:
            input_image_base64 = input_image_base64.split(',', 1)[1]
        
        # Prepare job data
        job_data = {
            "job_id": job_id,
            "job_type": "REMOTE_REMBG",
            "service": "rembg",
            "input_image_base64": input_image_base64,
            "alpha_matting": alpha_matting,
            "timestamp": time.time()
        }
        
        # Queue job to Redis
        queue_name = "scareverse:rembg-jobs:queue"
        await redis_client.lpush(queue_name, json.dumps(job_data))
        
        logger.info(f"✅ Job queued: {job_id}")
        logger.debug(f"   Queue: {queue_name}")
        logger.debug(f"   Alpha matting: {alpha_matting}")
        
        # Poll for job completion
        result = await poll_job_status(redis_client, job_id, timeout)
        
        if result["status"] == "completed":
            logger.info(f"✅ Background removal completed: {job_id}")
            return {
                "success": True,
                "output_image_base64": result.get("output_image_base64", ""),
                "job_id": job_id,
                "processing_time": result.get("processing_time", 0)
            }
        elif result["status"] == "failed":
            error_msg = result.get("error", "Unknown error")
            logger.error(f"❌ Background removal failed: {job_id} - {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "job_id": job_id
            }
        else:
            # Timeout or unknown status
            logger.error(f"❌ Background removal timeout: {job_id}")
            return {
                "success": False,
                "error": f"Job timeout or unknown status: {result['status']}",
                "job_id": job_id
            }
            
    except Exception as e:
        logger.error(f"Failed to queue background removal job: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to queue job: {str(e)}",
            "job_id": job_id if 'job_id' in locals() else None
        }


async def poll_job_status(
    redis_client,
    job_id: str,
    timeout: float = 60.0,
    poll_interval: float = 0.5
) -> Dict[str, Any]:
    """
    Poll Redis for job status until completion or timeout.
    
    Args:
        redis_client: Redis client instance
        job_id: Job identifier to poll
        timeout: Maximum time to wait in seconds
        poll_interval: Time between polls in seconds
        
    Returns:
        Dict containing job status and result data
    """
    # Use the same status prefix as worker_bridge.py
    status_key = f"scareverse:rembg-status:{job_id}"
    start_time = time.time()
    
    logger.debug(f"Polling job status: {job_id} (timeout: {timeout}s)")
    
    while time.time() - start_time < timeout:
        # Get job status from Redis (stored as Hash)
        status_data = await redis_client.hgetall(status_key)
        
        if status_data:
            status = status_data.get("status", "unknown")
            
            if status == "completed":
                # Job completed successfully
                logger.debug(f"Job completed: {job_id}")
                
                # Deserialize complex fields from JSON
                result = {
                    "status": "completed",
                    "job_id": job_id,
                    "output_image_base64": status_data.get("output_image_base64", ""),
                    "processing_time": float(status_data.get("processing_time", 0)),
                    "alpha_matting": status_data.get("alpha_matting", "true") == "true"
                }
                
                return result
                
            elif status == "failed":
                # Job failed
                logger.debug(f"Job failed: {job_id}")
                return {
                    "status": "failed",
                    "job_id": job_id,
                    "error": status_data.get("error", "Unknown error")
                }
            
            elif status == "processing":
                # Still processing, continue polling
                logger.debug(f"Job still processing: {job_id}")
        
        # Wait before next poll
        await asyncio.sleep(poll_interval)
    
    # Timeout reached
    logger.warning(f"Job polling timeout: {job_id}")
    return {
        "status": "timeout",
        "job_id": job_id,
        "error": f"Job did not complete within {timeout} seconds"
    }


async def get_redis_client():
    """
    Get Redis client for job queueing.
    
    Attempts to import from core backend app first, falls back to
    standalone Redis client for direct script execution.
    
    Returns:
        Redis client instance with async support
        
    Raises:
        Exception: If Redis connection fails
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
            logger.info(f"Creating standalone Redis client: {redis_url}")
            return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to get Redis client: {e}")
        raise


# Synchronous wrapper for backward compatibility
def queue_background_removal_job_sync(
    input_image_base64: str,
    alpha_matting: bool = True,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Synchronous wrapper for queue_background_removal_job.
    
    Uses asyncio.run to execute the async function.
    Useful for non-async contexts.
    
    Args:
        input_image_base64: Base64-encoded input image
        alpha_matting: Enable alpha matting
        timeout: Maximum wait time
        
    Returns:
        Dict with job result
    """
    return asyncio.run(queue_background_removal_job(
        input_image_base64=input_image_base64,
        alpha_matting=alpha_matting,
        timeout=timeout
    ))


if __name__ == "__main__":
    # Test script for standalone execution
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python background_removal.py <base64_image>")
        sys.exit(1)
    
    input_image = sys.argv[1]
    result = queue_background_removal_job_sync(input_image)
    
    print(json.dumps(result, indent=2))
