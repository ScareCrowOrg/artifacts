"""
Handshake Worker for Event Bus.

Listens to handshake requests from clients and responds with
updated sessions since the last sync timestamp.

Architecture:
- Uses CentralHubClient HTTP proxy (no direct MongoDB connection)
- Supports offline operation when CentralHub is unavailable
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config.database import CENTRALHUB_URL, MONGODB_ENABLED
from ..database.centralhub_client import CentralHubClient
from ..database.schemas.session_schema import SESSIONS_COLLECTION
from ..models.event_bus import EventTopic, MessageEnvelope
from ..services.redis_pubsub_service import get_pubsub_service

logger = logging.getLogger(__name__)


class HandshakeWorker:
    """
    Worker that processes handshake requests from clients.

    Features:
    - Listen to system:event:handshake_request channel
    - Query CentralHub for sessions updated since last_sync_timestamp
    - Query for deleted sessions
    - Build handshake response payload
    - Publish response to system:event:handshake_response
    """

    def __init__(self, centralhub_url: Optional[str] = None):
        """
        Initialize the handshake worker.

        Args:
            centralhub_url: CentralHub URL (defaults to config)
        """
        self.centralhub_url = centralhub_url or CENTRALHUB_URL
        self._is_running = False
        self._pubsub_service = None
        self._hub_client: Optional[CentralHubClient] = None

        logger.info("Handshake worker initialized")

    async def start(self):
        """
        Start the worker and subscribe to handshake requests.
        """
        if self._is_running:
            logger.warning("Worker already running")
            return

        if not MONGODB_ENABLED:
            logger.warning("MongoDB is disabled - handshake worker will not start")
            return

        # Initialize CentralHub client
        try:
            self._hub_client = CentralHubClient(
                base_url=self.centralhub_url,
                enabled=True,
            )
            logger.info("CentralHub client initialized: %s", self.centralhub_url)
        except Exception as e:
            logger.error("Failed to initialize CentralHub client: %s", e)
            raise

        # Initialize pub/sub service
        self._pubsub_service = await get_pubsub_service()

        # Subscribe to handshake requests
        await self._pubsub_service.subscribe(
            EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
            self._handle_handshake_request,
        )

        self._is_running = True
        logger.info("Handshake worker started")

    async def stop(self):
        """
        Stop the worker and clean up resources.
        """
        if not self._is_running:
            return

        # Unsubscribe from channels
        if self._pubsub_service:
            await self._pubsub_service.unsubscribe(
                EventTopic.SYSTEM_EVENT_HANDSHAKE_REQUEST.value,
                self._handle_handshake_request,
            )

        # Close CentralHub client
        if self._hub_client:
            await self._hub_client.close()

        self._is_running = False
        logger.info("Handshake worker stopped")

    async def _handle_handshake_request(self, message: MessageEnvelope):
        """
        Handle a handshake request message.

        Args:
            message: Message envelope containing handshake request payload
        """
        try:
            payload = message.payload

            # Extract request parameters
            client_id = payload.get("client_id")
            user_id = payload.get("user_id")
            last_sync_timestamp = payload.get("last_sync_timestamp")

            if not client_id:
                logger.warning("Handshake request missing client_id")
                await self._send_error_response(
                    message,
                    "MISSING_CLIENT_ID",
                    "Handshake request must include client_id",
                )
                return

            if not user_id:
                logger.warning("Handshake request missing user_id")
                await self._send_error_response(
                    message, "MISSING_USER_ID", "Handshake request must include user_id"
                )
                return

            logger.info("Processing handshake request for client %s, user %s", client_id, user_id)

            # Parse last sync timestamp
            last_sync_dt = None
            if last_sync_timestamp:
                try:
                    last_sync_dt = datetime.fromisoformat(
                        last_sync_timestamp.replace("Z", "+00:00")
                    )
                except ValueError as e:
                    logger.warning("Invalid last_sync_timestamp format: %s", e)

            # Query updated sessions
            updated_sessions = await self._get_updated_sessions(user_id, last_sync_dt)

            # Query deleted sessions
            # TODO: Implement deletion tracking in separate collection or field
            # Current implementation only returns sessions with state != "deleted"
            # For true deletion tracking, consider:
            # - Separate "deleted_sessions" collection with deletion timestamps
            # - Or add "deleted_at" timestamp field to sessions and query it
            # See: https://github.com/ScareCrowOrg/ScareVerseLab/issues/[TBD]
            deleted_sessions = []

            # Build response
            response_payload = {
                "client_id": client_id,
                "server_timestamp": datetime.utcnow().isoformat(),
                "updated_sessions": updated_sessions,
                "deleted_sessions": deleted_sessions,
                "sync_count": len(updated_sessions),
            }

            # Send handshake response
            await self._send_handshake_response(message, response_payload)

            logger.info("Handshake complete for client %s: %s updates", client_id, len(updated_sessions))

        except Exception as e:
            logger.error("Error handling handshake request: %s", e, exc_info=True)
            await self._send_error_response(
                message,
                "INTERNAL_ERROR",
                f"Internal error processing handshake: {str(e)}",
            )

    async def _get_updated_sessions(
        self, user_id: str, last_sync_timestamp: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """
        Get sessions that have been updated since the last sync timestamp.

        Args:
            user_id: User identifier
            last_sync_timestamp: Last sync timestamp (or None for all sessions)

        Returns:
            List of updated session dictionaries
        """
        # Build query
        query: Dict[str, Any] = {
            "user_id": user_id,
            "state": {"$ne": "deleted"},  # Don't return deleted sessions
        }

        if last_sync_timestamp:
            # CentralHub's HTTP proxy accepts ISO format and converts to MongoDB date comparison
            # MongoDB will handle the date comparison correctly even with ISO strings
            query["updated_at"] = {"$gt": last_sync_timestamp.isoformat()}

        try:
            # Query CentralHub (returns list)
            sessions = await self._hub_client.find_many(
                collection=SESSIONS_COLLECTION,
                query=query,
                user_id=user_id,
            )

            # Remove MongoDB's _id field if present
            for session in sessions:
                session.pop("_id", None)

            # Sort by updated_at (CentralHub may not guarantee order)
            # Convert to datetime for proper chronological sorting
            def get_sort_key(session: Dict[str, Any]) -> datetime:
                updated_at = session.get("updated_at")
                if isinstance(updated_at, datetime):
                    return updated_at
                elif isinstance(updated_at, str):
                    try:
                        return datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        return datetime.min
                return datetime.min

            sessions.sort(key=get_sort_key, reverse=False)

            return sessions

        except Exception as e:
            logger.error("Failed to query updated sessions: %s", e)
            raise

    async def _send_handshake_response(
        self, original_message: MessageEnvelope, payload: Dict[str, Any]
    ):
        """
        Send a handshake response message.

        Args:
            original_message: Original handshake request message
            payload: Response payload
        """
        response = MessageEnvelope(
            source="backend-handshake-worker",
            topic=EventTopic.SYSTEM_EVENT_HANDSHAKE_RESPONSE.value,
            payload=payload,
            correlation_id=original_message.trace_id,
        )

        if self._pubsub_service:
            await self._pubsub_service.publish(response)

    async def _send_error_response(
        self, original_message: MessageEnvelope, error_code: str, error_message: str
    ):
        """
        Send an error response.

        Args:
            original_message: Original request message
            error_code: Error code identifier
            error_message: Human-readable error message
        """
        error_envelope = MessageEnvelope(
            source="backend-handshake-worker",
            topic=EventTopic.AGENT_RESPONSE_ERROR.value,
            payload={"error_code": error_code, "message": error_message},
            correlation_id=original_message.trace_id,
        )

        if self._pubsub_service:
            await self._pubsub_service.publish(error_envelope)


# Global worker instance
_worker: Optional[HandshakeWorker] = None


async def start_handshake_worker():
    """
    Start the global handshake worker.

    Returns:
        The worker instance
    """
    global _worker

    if _worker is None:
        _worker = HandshakeWorker()

    await _worker.start()
    return _worker


async def stop_handshake_worker():
    """Stop the global handshake worker."""
    global _worker

    if _worker is not None:
        await _worker.stop()
        _worker = None
