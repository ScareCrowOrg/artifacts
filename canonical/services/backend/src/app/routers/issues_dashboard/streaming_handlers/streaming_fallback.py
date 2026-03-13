"""
SSE Streaming Fallback Handlers for Issues Dashboard

Provides fallback implementations using event bus when Redis is unavailable.
"""

import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import Request
from fastapi.responses import StreamingResponse

from ....event_bus import event_bus

logger = logging.getLogger(__name__)


async def stream_cell_fragments_fallback(cell_id: str, request: Request):
    """
    Internal fallback SSE endpoint for streaming cell fragments via event bus when Redis is disabled.

    This is not a public API endpoint - it's called internally by stream_cell_fragments()
    when Redis is unavailable. Subscribes to fragment_added events from the event bus
    and filters by cell_id.

    Args:
        cell_id: ID of the cell to stream fragments for
        request: FastAPI request object for disconnect detection

    Returns:
        StreamingResponse with text/event-stream content type
    """

    async def fragment_generator():
        """Generate SSE events from event bus filtered by cell_id."""
        # Create a queue for this client
        client_queue: asyncio.Queue = asyncio.Queue()

        # Define callback to receive events
        async def on_event(event_data: Dict[str, Any]):
            """Callback to put events into client queue if they match the cell_id."""
            # Filter events for this specific cell
            if (
                event_data.get("event_type") == "fragment_added"
                and event_data.get("cell_id") == cell_id
            ):
                # Event data is already serialized by event_bus.publish()
                await client_queue.put(event_data)

        # Subscribe to issues-queue topic
        await event_bus.subscribe("issues-queue", on_event)

        try:
            logger.info("SSE client connected to cell %s fragments (event bus fallback)", cell_id)

            # Send initial connection message
            yield f"data: {json.dumps({'event_type': 'connected', 'message': f'Subscribed to fragments for cell {cell_id} (event bus)'})}\n\n"

            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected from cell %s fragments", cell_id)
                    break

                try:
                    # Wait for event with timeout (for keepalive)
                    event_data = await asyncio.wait_for(
                        client_queue.get(),
                        timeout=30.0,  # 30 second timeout
                    )

                    # Transform event_data to match expected format
                    fragment_event = {
                        "event_type": "fragment",
                        "cell_id": cell_id,
                        "fragment": event_data.get("fragment", {}),
                    }

                    # Send event to client
                    yield f"data: {json.dumps(fragment_event)}\n\n"

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield ": keepalive\n\n"

        except asyncio.CancelledError:
            logger.info("SSE connection cancelled for cell: %s", cell_id)
        except Exception as e:
            logger.error("Error in event bus SSE stream: %s", e)
            error_data = {
                "event_type": "error",
                "message": "An error occurred while streaming fragments",
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            # Unsubscribe when client disconnects
            await event_bus.unsubscribe("issues-queue", on_event)
            logger.info("SSE client unsubscribed from cell %s fragments", cell_id)

    return StreamingResponse(
        fragment_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def stream_pipeline_fragments_fallback(request: Request):
    """
    Internal fallback SSE endpoint for streaming fragments from all active cells via event bus.

    This is not a public API endpoint - it's called internally by stream_all_active_fragments()
    when Redis is unavailable. Subscribes to fragment_added events from the event bus for all cells.

    Args:
        request: FastAPI request object for disconnect detection

    Returns:
        StreamingResponse with text/event-stream content type
    """

    async def all_fragments_generator():
        """Generate SSE events from event bus for all fragment_added events."""
        # Create a queue for this client
        client_queue: asyncio.Queue = asyncio.Queue()

        # Define callback to receive events
        async def on_event(event_data: Dict[str, Any]):
            """Callback to put fragment events into client queue."""
            # Only process fragment_added events
            if event_data.get("event_type") == "fragment_added":
                # Event data is already serialized by event_bus.publish()
                await client_queue.put(event_data)

        # Subscribe to issues-queue topic
        await event_bus.subscribe("issues-queue", on_event)

        try:
            logger.info(
                "SSE client connected to pipeline fragments (event bus fallback)"
            )

            # Send initial connection message
            yield f"data: {json.dumps({'event_type': 'connected', 'message': 'Subscribed to all active cell fragments (event bus)'})}\n\n"

            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("SSE client disconnected from pipeline fragments")
                    break

                try:
                    # Wait for event with timeout (for keepalive)
                    event_data = await asyncio.wait_for(
                        client_queue.get(),
                        timeout=30.0,  # 30 second timeout
                    )

                    # Transform event_data to match expected format
                    pipeline_event = {
                        "event_type": "pipeline_fragment",
                        "cell_id": event_data.get("cell_id", "unknown"),
                        "fragment": event_data.get("fragment", {}),
                    }

                    # Send event to client
                    yield f"data: {json.dumps(pipeline_event)}\n\n"

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield ": keepalive\n\n"

        except asyncio.CancelledError:
            logger.info("SSE connection cancelled for pipeline fragments")
        except Exception as e:
            logger.error("Error in event bus pipeline SSE stream: %s", e)
            error_data = {
                "event_type": "error",
                "message": "An error occurred while streaming pipeline fragments",
            }
            yield f"data: {json.dumps(error_data)}\n\n"
        finally:
            # Unsubscribe when client disconnects
            await event_bus.unsubscribe("issues-queue", on_event)
            logger.info("SSE client unsubscribed from pipeline fragments")

    return StreamingResponse(
        all_fragments_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
