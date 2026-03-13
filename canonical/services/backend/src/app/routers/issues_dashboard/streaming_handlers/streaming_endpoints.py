"""
SSE Streaming Endpoint Handlers for Issues Dashboard

Provides main SSE endpoints for real-time event streaming.
"""

import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse

from ....event_bus import event_bus
from .streaming_fallback import (
    stream_cell_fragments_fallback,
    stream_pipeline_fragments_fallback,
)

logger = logging.getLogger(__name__)


async def stream_events(request: Request):
    """
    Server-Sent Events (SSE) endpoint for real-time updates.

    Streams events from the event bus to connected clients.
    Events include:
    - cell_state_changed
    - fragment_added
    - cell_created

    Args:
        request: FastAPI request object for disconnect detection

    Returns:
        StreamingResponse with text/event-stream content type
    """

    async def event_generator():
        """Generate SSE events from event bus."""

        # Create a queue for this client
        client_queue: asyncio.Queue = asyncio.Queue()

        # Define callback to receive events
        async def on_event(event_data: Dict[str, Any]):
            """Callback to put events into client queue."""
            # Event data is already serialized by event_bus.publish()
            await client_queue.put(event_data)

        # Subscribe to issues-queue topic
        await event_bus.subscribe("issues-queue", on_event)

        try:
            logger.info("SSE client connected")

            # Send initial connection message
            yield f"data: {json.dumps({'event_type': 'connected', 'message': 'SSE connection established'})}\n\n"

            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected")
                    break

                try:
                    # Wait for event with timeout (for keepalive)
                    event_data = await asyncio.wait_for(
                        client_queue.get(),
                        timeout=30.0,  # 30 second timeout
                    )

                    # Send event to client
                    yield f"data: {json.dumps(event_data)}\n\n"

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield ": keepalive\n\n"

        except asyncio.CancelledError:
            logger.info("SSE connection cancelled")
        except Exception as e:
            logger.error("Error in SSE stream: %s", e)
        finally:
            # Unsubscribe when client disconnects
            await event_bus.unsubscribe("issues-queue", on_event)
            logger.info("SSE client unsubscribed")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def stream_cell_fragments(cell_id: str, request: Request):
    """
    Server-Sent Events (SSE) endpoint for streaming cell fragments from Redis.

    Streams fragments in real-time as they are published by the orchestrator
    during workflow execution.

    Falls back to event bus when Redis is disabled.

    Args:
        cell_id: ID of the cell to stream fragments for
        request: FastAPI request object for disconnect detection

    Returns:
        StreamingResponse with text/event-stream content type
    """
    from app.config.database import (
        REDIS_L1_ENABLED,
        REDIS_L1_PASSWORD,
    )

    if not REDIS_L1_ENABLED:
        # Fallback to event bus when Redis is disabled
        logger.warning("Redis L1 disabled, using event bus fallback for cell %s fragments", cell_id)
        return await stream_cell_fragments_fallback(cell_id, request)

    try:
        import redis.asyncio as aioredis
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis async client not available. Install 'redis' package.",
        )

    async def fragment_generator():
        """Generate SSE events from Redis pubsub."""
        redis_client = None
        pubsub = None

        try:
            # Initialize async Redis client
            redis_client = aioredis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_L1_PASSWORD,
                decode_responses=True,
            )

            # Create pubsub and subscribe to cell's fragment channel
            pubsub = redis_client.pubsub()
            channel = f"celula:{cell_id}:fragmentos"
            await pubsub.subscribe(channel)

            logger.info("SSE client subscribed to Redis channel: %s", channel)

            # Send initial connection message
            yield f"data: {json.dumps({'event_type': 'connected', 'message': f'Subscribed to fragments for cell {cell_id}'})}\n\n"

            # Listen for messages
            async for message in pubsub.listen():
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected from channel: %s", channel)
                    break

                # Skip subscription confirmation messages
                if message["type"] == "subscribe":
                    continue

                # Process actual messages
                if message["type"] == "message":
                    try:
                        # Parse fragment data
                        fragment_data = json.loads(message["data"])

                        # Send fragment to client
                        event_data = {
                            "event_type": "fragment",
                            "cell_id": cell_id,
                            "fragment": fragment_data,
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"

                    except json.JSONDecodeError as e:
                        logger.error("Failed to decode fragment data: %s", e)
                        continue

        except asyncio.CancelledError:
            logger.info("SSE connection cancelled for cell: %s", cell_id)
        except Exception as e:
            logger.error("Error in Redis SSE stream: %s", e)
            # Don't expose internal error details to external users
            error_data = {
                "event_type": "error",
                "message": "An error occurred while streaming fragments",
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            # Cleanup
            if pubsub:
                await pubsub.unsubscribe()
                await pubsub.close()
            if redis_client:
                await redis_client.close()
            logger.info("SSE client cleaned up for cell: %s", cell_id)

    return StreamingResponse(
        fragment_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def stream_all_active_fragments(request: Request):
    """
    Server-Sent Events (SSE) endpoint for streaming fragments from all active cells.

    Subscribes to all cell fragment channels using Redis pattern subscription (celula:*:fragmentos)
    to provide a holistic real-time view of pipeline activity.

    Falls back to event bus when Redis is disabled.

    Args:
        request: FastAPI request object for disconnect detection

    Returns:
        StreamingResponse with text/event-stream content type
    """
    from app.config.database import (
        REDIS_L1_DB,
    )

    if not REDIS_ENABLED:
        # Fallback to event bus when Redis is disabled
        logger.warning(
            "Redis L1 disabled, using event bus fallback for pipeline fragments"
        )
        return await stream_pipeline_fragments_fallback(request)

    try:
        import redis.asyncio as aioredis
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis async client not available. Install 'redis' package.",
        )

    async def all_fragments_generator():
        """Generate SSE events from all cell fragment channels via Redis pattern subscription."""
        redis_client = None
        pubsub = None

        try:
            # Initialize async Redis client
            redis_client = aioredis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_L1_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
            )

            # Create pubsub and subscribe to all cell fragment channels using pattern
            pubsub = redis_client.pubsub()
            pattern = "celula:*:fragmentos"
            await pubsub.psubscribe(pattern)

            logger.info("SSE client subscribed to Redis pattern: %s", pattern)

            # Send initial connection message
            yield f"data: {json.dumps({'event_type': 'connected', 'message': 'Subscribed to all active cell fragments'})}\n\n"

            # Listen for messages
            async for message in pubsub.listen():
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected from pattern: %s", pattern)
                    break

                # Skip subscription confirmation messages
                if message["type"] == "psubscribe":
                    continue

                # Process pattern messages
                if message["type"] == "pmessage":
                    try:
                        # Extract cell_id from channel name (format: celula:{cell_id}:fragmentos)
                        channel = message["channel"]
                        cell_id = channel.split(":")[1] if ":" in channel else "unknown"

                        # Parse fragment data
                        fragment_data = json.loads(message["data"])

                        # Send fragment to client with cell_id included
                        event_data = {
                            "event_type": "pipeline_fragment",
                            "cell_id": cell_id,
                            "fragment": fragment_data,
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"

                    except json.JSONDecodeError as e:
                        logger.error("Failed to decode fragment data: %s", e)
                        continue
                    except (IndexError, KeyError) as e:
                        logger.error("Failed to extract cell_id from channel: %s", e)
                        continue

        except asyncio.CancelledError:
            logger.info("SSE connection cancelled for all fragments stream")
        except Exception as e:
            logger.error("Error in Redis pattern SSE stream: %s", e)
            # Don't expose internal error details to external users
            error_data = {
                "event_type": "error",
                "message": "An error occurred while streaming pipeline fragments",
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            # Cleanup
            if pubsub:
                await pubsub.punsubscribe()
                await pubsub.close()
            if redis_client:
                await redis_client.close()
            logger.info("SSE client cleaned up for all fragments stream")

    return StreamingResponse(
        all_fragments_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
