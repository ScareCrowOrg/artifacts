"""
WebSocket Router for Distributed Event Bus.

Provides WebSocket endpoint for browser extension to establish
persistent bidirectional communication channel with the backend.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from ..auth import verify_token
from ..models.event_bus import EventTopic, MessageEnvelope
from ..services.redis_pubsub_service import get_pubsub_service
from ..services.websocket_connection_manager import get_connection_manager

logger = logging.getLogger(__name__)

# Create router
websocket_router = APIRouter(tags=["websocket", "event-bus"])


@websocket_router.get(
    "/ws/event-bus/health",
    summary="WebSocket health check",
    response_description="Health status of WebSocket service",
)
async def websocket_health():
    """
    Health check endpoint for the WebSocket event bus service.

    Returns:
        Status information about active connections
    """
    manager = get_connection_manager()
    connected_clients = manager.get_connected_clients()

    return {
        "status": "healthy",
        "service": "websocket-event-bus",
        "active_connections": len(connected_clients),
        "client_ids": list(connected_clients),
    }


@websocket_router.websocket("/ws/event-bus")
async def websocket_event_bus(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT authentication token"),
):
    """
    WebSocket endpoint for distributed event bus communication.

    Protocol:
    1. Client connects with JWT token in query parameter
    2. Server validates token and accepts connection
    3. Client sends MessageEnvelope JSON objects
    4. Server routes messages to Redis pub/sub
    5. Server forwards Redis messages to client
    6. Heartbeats exchanged to maintain connection

    Args:
        websocket: WebSocket connection
        token: JWT authentication token
    """
    client_id: Optional[str] = None
    manager = get_connection_manager()
    pubsub = await get_pubsub_service()

    # Handler for messages from Redis to this client
    async def redis_to_websocket_handler(message: MessageEnvelope):
        """Forward messages from Redis to this WebSocket client."""
        if client_id:
            await manager.send_message(client_id, message)

    try:
        # Validate token
        if not token:
            logger.warning("WebSocket connection attempted without token")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Token required"
            )
            return

        payload = verify_token(token)
        if not payload:
            logger.warning("WebSocket connection attempted with invalid token")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            )
            return

        # Extract user info from token
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("WebSocket token missing user_id")
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload"
            )
            return

        # Use user_id as client_id (could be enhanced with session_id)
        client_id = user_id

        # Accept connection and register with manager
        await manager.connect(
            client_id=client_id,
            websocket=websocket,
            metadata={"user_id": user_id, "token_exp": payload.get("exp")},
        )

        logger.info("WebSocket connection established for client %s", client_id)

        # Subscribe to agent response topics (backend → client messages)
        await pubsub.subscribe(
            EventTopic.AGENT_RESPONSE_FILE_DATA.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.AGENT_RESPONSE_FILE_WRITTEN.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.AGENT_RESPONSE_EXEC_RESULT.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.AGENT_RESPONSE_ERROR.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.SESSION_STATE_SYNCED.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.SESSION_STATE_ERROR.value, redis_to_websocket_handler
        )

        # Subscribe to monitoring topics (Sprint 3: Pipeline Monitoring)
        await pubsub.subscribe(
            EventTopic.MONITORING_HEALTH_UPDATE.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.MONITORING_METRICS_UPDATE.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.MONITORING_PREREQUISITE_UPDATE.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.MONITORING_ALERT_TRIGGERED.value, redis_to_websocket_handler
        )
        await pubsub.subscribe(
            EventTopic.MONITORING_ALERT_RESOLVED.value, redis_to_websocket_handler
        )

        # Send connection acknowledgment
        ack_message = MessageEnvelope(
            source="backend-websocket-server",
            topic=EventTopic.SYSTEM_EVENT_LOG.value,
            payload={"message": "Connection established", "client_id": client_id},
        )
        await manager.send_message(client_id, ack_message)

        # Main message loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()

                # Parse message envelope
                try:
                    message_dict = json.loads(data)
                    message = MessageEnvelope(**message_dict)

                    logger.debug("Received message from %s: topic=%s", client_id, message.topic)

                    # Handle heartbeat
                    if message.topic == EventTopic.SYSTEM_EVENT_HEARTBEAT.value:
                        await manager.update_heartbeat(client_id)

                        # Send heartbeat response
                        heartbeat_response = MessageEnvelope(
                            source="backend-websocket-server",
                            topic=EventTopic.SYSTEM_EVENT_HEARTBEAT.value,
                            payload={"status": "healthy", "client_id": client_id},
                            correlation_id=message.trace_id,
                        )
                        await manager.send_message(client_id, heartbeat_response)
                        continue

                    # Route message to Redis pub/sub
                    success = await pubsub.publish(message)

                    if not success:
                        # Send error if publish failed
                        error_msg = MessageEnvelope(
                            source="backend-websocket-server",
                            topic=EventTopic.AGENT_RESPONSE_ERROR.value,
                            payload={
                                "error_code": "PUBLISH_FAILED",
                                "message": "Failed to publish message to event bus",
                                "details": {"original_topic": message.topic},
                            },
                            correlation_id=message.trace_id,
                        )
                        await manager.send_message(client_id, error_msg)
                    else:
                        logger.info("Message routed to Redis from %s: %s", client_id, message.topic)

                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON from %s: %s", client_id, e)
                    error_message = MessageEnvelope(
                        source="backend-websocket-server",
                        topic=EventTopic.AGENT_RESPONSE_ERROR.value,
                        payload={
                            "error_code": "INVALID_JSON",
                            "message": "Invalid JSON format",
                            "details": {"error": str(e)},
                        },
                    )
                    await manager.send_message(client_id, error_message)

                except Exception as e:
                    logger.error("Error parsing message from %s: %s", client_id, e)
                    error_message = MessageEnvelope(
                        source="backend-websocket-server",
                        topic=EventTopic.AGENT_RESPONSE_ERROR.value,
                        payload={
                            "error_code": "INVALID_MESSAGE",
                            "message": "Invalid message format",
                            "details": {"error": str(e)},
                        },
                    )
                    await manager.send_message(client_id, error_message)

            except WebSocketDisconnect:
                logger.info("Client %s disconnected normally", client_id)
                break

    except WebSocketDisconnect:
        logger.info("Client %s disconnected during handshake", client_id or 'unknown')

    except Exception as e:
        logger.error("Unexpected error in WebSocket connection for %s: %s", client_id or 'unknown', e, exc_info=True)

    finally:
        # Unsubscribe from Redis topics
        if client_id:
            try:
                await pubsub.unsubscribe(
                    EventTopic.AGENT_RESPONSE_FILE_DATA.value,
                    redis_to_websocket_handler,
                )
                await pubsub.unsubscribe(
                    EventTopic.AGENT_RESPONSE_FILE_WRITTEN.value,
                    redis_to_websocket_handler,
                )
                await pubsub.unsubscribe(
                    EventTopic.AGENT_RESPONSE_EXEC_RESULT.value,
                    redis_to_websocket_handler,
                )
                await pubsub.unsubscribe(
                    EventTopic.AGENT_RESPONSE_ERROR.value, redis_to_websocket_handler
                )
                await pubsub.unsubscribe(
                    EventTopic.SESSION_STATE_SYNCED.value, redis_to_websocket_handler
                )
                await pubsub.unsubscribe(
                    EventTopic.SESSION_STATE_ERROR.value, redis_to_websocket_handler
                )
            except Exception as e:
                logger.error("Error unsubscribing from Redis topics: %s", e)

        # Clean up connection
        if client_id:
            await manager.disconnect(client_id)
            logger.info("WebSocket connection closed for client %s", client_id)
