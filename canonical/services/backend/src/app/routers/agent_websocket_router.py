"""
Agent Mode WebSocket Endpoint - Real-time Log Streaming.

Provides WebSocket endpoint for streaming Agent Mode logs
from Redis pub/sub to frontend terminal in real-time.

MVP 4 Implementation: Real-time telemetry via WebSocket + Redis.
"""

import logging
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from datetime import datetime

from app.auth_legacy import verify_token
from app.controllers.agent_mode import AgentModeController

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["agent-mode", "websocket"])

# Global controller instance
_agent_controller: Optional[AgentModeController] = None


def get_agent_controller() -> AgentModeController:
    """
    Get AgentModeController instance.

    Returns:
        AgentModeController instance
    """
    global _agent_controller
    if _agent_controller is None:
        _agent_controller = AgentModeController()
    return _agent_controller


@router.websocket("/ws/agent/{conversation_id}")
async def agent_logs_websocket(
    websocket: WebSocket,
    conversation_id: str,
    token: Optional[str] = Query(None, description="JWT authentication token"),
):
    """
    WebSocket endpoint for Agent Mode real-time log streaming.

    This endpoint connects to Redis pub/sub channel `agent:logs:{conversation_id}`
    and streams all Agent Mode logs to the connected WebSocket client.

    Protocol:
    1. Client connects with JWT token in query parameter
    2. Server validates token and accepts connection
    3. Server subscribes to Redis channel for this conversation
    4. Server streams log messages as JSON to client
    5. Heartbeats sent every 30s to keep connection alive

    Message Format (sent to client):
    ```json
    {
        "type": "log" | "status" | "error" | "heartbeat",
        "content": "log line content (for log type)",
        "status": "status message (for status type)",
        "message": "error message (for error type)",
        "timestamp": "ISO 8601 timestamp"
    }
    ```

    Args:
        websocket: WebSocket connection
        conversation_id: Agent Mode session/conversation ID
        token: JWT authentication token
    """
    client_id: Optional[str] = None
    controller = get_agent_controller()

    try:
        # Validate token
        if not token:
            logger.warning("Agent WebSocket connection attempted without token: %s", conversation_id)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token required")
            return

        payload = verify_token(token)
        if not payload:
            logger.warning("Agent WebSocket connection with invalid token: %s", conversation_id)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        # Extract user info
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Agent WebSocket token missing user_id: %s", conversation_id)
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload"
            )
            return

        client_id = f"{user_id}:{conversation_id}"

        # Validate session exists
        session = await controller.get_session_status(conversation_id)
        if not session:
            logger.warning("Agent WebSocket connection for non-existent session: %s", conversation_id)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session not found")
            return

        # Accept connection
        await websocket.accept()
        logger.info("Agent WebSocket connected: user=%s, session=%s", user_id, conversation_id)

        # Send connection confirmation
        await websocket.send_json(
            {
                "type": "status",
                "status": "connected",
                "conversation_id": conversation_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # MVP 4.1: Subscribe to Redis pub/sub for real-time logs
        try:
            pubsub_service = await controller._get_pubsub_service()
            if pubsub_service and pubsub_service._redis_client:
                # Subscribe to Redis channel
                channel = f"agent:logs:{conversation_id}"
                pubsub = pubsub_service._redis_client.pubsub()
                await pubsub.subscribe(channel)

                logger.info("Subscribed to Redis channel: %s for %s", channel, client_id)

                # Listen for messages from Redis
                while True:
                    try:
                        # Get message from Redis (with timeout)
                        message = await asyncio.wait_for(
                            pubsub.get_message(ignore_subscribe_messages=True), timeout=30.0
                        )

                        if message and message["type"] == "message":
                            # Parse and forward message to WebSocket
                            try:
                                log_data = json.loads(message["data"])
                                await websocket.send_json(log_data)
                            except json.JSONDecodeError as e:
                                logger.error("Invalid JSON in Redis message: %s", e)
                                # Inform client about malformed data
                                await websocket.send_json(
                                    {
                                        "type": "error",
                                        "message": "Malformed log data received",
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }
                                )

                        # Send heartbeat if no message (timeout)
                        if message is None:
                            await websocket.send_json(
                                {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}
                            )
                            logger.debug("Heartbeat sent to %s", client_id)

                    except asyncio.TimeoutError:
                        # Send heartbeat on timeout
                        await websocket.send_json(
                            {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}
                        )
                        logger.debug("Heartbeat sent to %s", client_id)

                    except WebSocketDisconnect:
                        logger.info("Agent WebSocket disconnected: %s", client_id)
                        await pubsub.unsubscribe(channel)
                        await pubsub.close()
                        break

                    except Exception as e:
                        logger.error("Error in Redis message loop for %s: %s", client_id, e)
                        break
            else:
                # Fallback: Redis not available, just send heartbeats
                logger.warning(
                    f"Redis pub/sub not available for {client_id}, " "using heartbeat-only mode"
                )
                while True:
                    await asyncio.sleep(30)
                    await websocket.send_json(
                        {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}
                    )
        except Exception as e:
            logger.error("Error in pub/sub setup for %s: %s", client_id, e)
            # Fallback heartbeat loop
            while True:
                try:
                    await asyncio.sleep(30)
                    await websocket.send_json(
                        {"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}
                    )
                except WebSocketDisconnect:
                    break
                except Exception as loop_error:
                    logger.error("Error in fallback loop: %s", loop_error)
                    break

    except WebSocketDisconnect:
        logger.info("Agent WebSocket disconnected during setup: %s", conversation_id)
    except Exception as e:
        logger.error("Error in Agent WebSocket for %s: %s", conversation_id, e, exc_info=True)
        try:
            await websocket.close(
                code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error"
            )
        except Exception:
            pass
    finally:
        logger.info("Agent WebSocket connection closed: %s", conversation_id)


@router.get(
    "/ws/agent/health",
    summary="Agent WebSocket health check",
    response_description="Health status of Agent WebSocket service",
)
async def agent_websocket_health():
    """
    Health check endpoint for Agent Mode WebSocket service.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "service": "agent-websocket",
        "version": "1.0.0",
        "features": ["real-time log streaming", "jwt authentication", "heartbeat mechanism"],
    }
