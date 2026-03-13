"""
WebSocket Connection Manager for Event Bus.

Manages persistent WebSocket connections from browser extensions,
handling connection lifecycle, message routing, and heartbeats.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from ..models.event_bus import MessageEnvelope

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for the distributed event bus.

    Features:
    - Track active connections by client ID
    - Send messages to specific clients or broadcast
    - Handle connection lifecycle (connect, disconnect, cleanup)
    - Heartbeat mechanism to detect stale connections
    """

    def __init__(self, heartbeat_interval: int = 30):
        """
        Initialize the connection manager.

        Args:
            heartbeat_interval: Interval in seconds between heartbeat checks
        """
        self._connections: Dict[str, WebSocket] = {}
        self._client_metadata: Dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(
        self, client_id: str, websocket: WebSocket, metadata: Optional[dict] = None
    ):
        """
        Register a new WebSocket connection.

        Args:
            client_id: Unique identifier for the client
            websocket: WebSocket connection object
            metadata: Optional metadata about the client (user_id, extension_version, etc.)
        """
        await websocket.accept()

        async with self._lock:
            self._connections[client_id] = websocket
            self._client_metadata[client_id] = {
                "connected_at": datetime.utcnow(),
                "last_heartbeat": datetime.utcnow(),
                "metadata": metadata or {},
            }

        logger.info("Client %s connected. Total connections: %s", client_id, len(self._connections))

        # Start heartbeat task if not already running
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())

    async def disconnect(self, client_id: str):
        """
        Remove a WebSocket connection.

        Args:
            client_id: Client identifier to disconnect
        """
        async with self._lock:
            if client_id in self._connections:
                del self._connections[client_id]
                del self._client_metadata[client_id]
                logger.info("Client %s disconnected. Remaining connections: %s", client_id, len(self._connections))

    async def send_message(self, client_id: str, message: MessageEnvelope) -> bool:
        """
        Send a message to a specific client.

        Args:
            client_id: Target client identifier
            message: Message envelope to send

        Returns:
            True if message sent successfully, False otherwise
        """
        websocket = self._connections.get(client_id)

        if websocket is None:
            logger.warning("Cannot send message to %s: not connected", client_id)
            return False

        try:
            message_json = message.model_dump_json()
            await websocket.send_text(message_json)
            logger.debug("Sent message to %s: topic=%s", client_id, message.topic)
            return True

        except WebSocketDisconnect:
            logger.warning("Client %s disconnected during send", client_id)
            await self.disconnect(client_id)
            return False

        except Exception as e:
            logger.error("Error sending message to %s: %s", client_id, e)
            return False

    async def broadcast(
        self, message: MessageEnvelope, exclude: Optional[Set[str]] = None
    ):
        """
        Broadcast a message to all connected clients.

        Args:
            message: Message envelope to broadcast
            exclude: Optional set of client IDs to exclude from broadcast
        """
        exclude = exclude or set()

        async with self._lock:
            client_ids = list(self._connections.keys())

        for client_id in client_ids:
            if client_id not in exclude:
                await self.send_message(client_id, message)

    async def update_heartbeat(self, client_id: str):
        """
        Update the last heartbeat timestamp for a client.

        Args:
            client_id: Client identifier
        """
        if client_id in self._client_metadata:
            self._client_metadata[client_id]["last_heartbeat"] = datetime.utcnow()

    async def _heartbeat_monitor(self):
        """
        Background task to monitor client heartbeats and disconnect stale connections.

        Runs continuously while there are active connections.
        """
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval)

                if not self._connections:
                    # No connections, stop monitoring
                    logger.debug("No active connections, stopping heartbeat monitor")
                    break

                now = datetime.utcnow()
                stale_threshold = timedelta(seconds=self._heartbeat_interval * 3)

                async with self._lock:
                    stale_clients = []

                    for client_id, metadata in self._client_metadata.items():
                        last_heartbeat = metadata.get("last_heartbeat")
                        if last_heartbeat and (now - last_heartbeat) > stale_threshold:
                            stale_clients.append(client_id)

                # Disconnect stale clients
                for client_id in stale_clients:
                    logger.warning("Disconnecting stale client %s", client_id)
                    await self.disconnect(client_id)

        except Exception as e:
            logger.error("Error in heartbeat monitor: %s", e)

    def get_connected_clients(self) -> Set[str]:
        """
        Get set of currently connected client IDs.

        Returns:
            Set of client IDs
        """
        return set(self._connections.keys())

    def get_client_metadata(self, client_id: str) -> Optional[dict]:
        """
        Get metadata for a specific client.

        Args:
            client_id: Client identifier

        Returns:
            Client metadata or None if not found
        """
        return self._client_metadata.get(client_id)

    async def close_all(self):
        """
        Close all active connections.

        Used during application shutdown.
        """
        async with self._lock:
            client_ids = list(self._connections.keys())

        for client_id in client_ids:
            try:
                websocket = self._connections.get(client_id)
                if websocket:
                    await websocket.close()
            except Exception as e:
                logger.error("Error closing connection for %s: %s", client_id, e)

            await self.disconnect(client_id)

        logger.info("All WebSocket connections closed")


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """
    Get the global connection manager instance.

    Returns:
        ConnectionManager instance
    """
    global _connection_manager

    if _connection_manager is None:
        _connection_manager = ConnectionManager()

    return _connection_manager
