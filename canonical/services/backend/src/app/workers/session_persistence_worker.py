"""
Session Persistence Worker for Event Bus.

Listens to session state update events and persists them to CentralHub.
Handles conflict resolution and acknowledgment publishing.

Architecture:
- Uses CentralHubClient HTTP proxy (no direct MongoDB connection)
- Supports offline operation when CentralHub is unavailable
- Maintains batch processing for performance
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..config.database import CENTRALHUB_URL, MONGODB_ENABLED
from ..database.centralhub_client import CentralHubClient
from ..database.schemas.session_schema import (
    SESSIONS_COLLECTION,
    BookSchema,
)
from ..models.event_bus import EventTopic, MessageEnvelope
from ..services.redis_pubsub_service import get_pubsub_service

logger = logging.getLogger(__name__)


class SessionPersistenceWorker:
    """
    Worker that processes session state updates from the event bus.

    Features:
    - Listen to session:state:update channel
    - Validate state payload
    - Persist to CentralHub via HTTP proxy (no direct MongoDB)
    - Batch processing for performance (buffer updates for 500ms)
    - Conflict detection via version numbers
    - Publish acknowledgment to session:state:synced
    - Publish errors to session:state:error
    """

    def __init__(
        self, centralhub_url: Optional[str] = None, batch_interval: float = 0.5
    ):
        """
        Initialize the session persistence worker.

        Args:
            centralhub_url: CentralHub URL (defaults to config)
            batch_interval: Batch processing interval in seconds
        """
        self.centralhub_url = centralhub_url or CENTRALHUB_URL
        self.batch_interval = batch_interval
        self._is_running = False
        self._pubsub_service = None
        self._hub_client: Optional[CentralHubClient] = None
        self._batch_queue: Dict[str, Dict[str, Any]] = {}
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None

        logger.info("Session persistence worker initialized with batch interval: %ss", batch_interval)

    async def start(self):
        """
        Start the worker and subscribe to session state updates.
        """
        if self._is_running:
            logger.warning("Worker already running")
            return

        if not MONGODB_ENABLED:
            logger.warning(
                "MongoDB is disabled - session persistence worker will not start"
            )
            return

        # Initialize CentralHub client
        try:
            self._hub_client = CentralHubClient(
                base_url=self.centralhub_url,
                enabled=True,
            )
            logger.info("CentralHub client initialized: %s", self.centralhub_url)

            # Note: Index creation is handled by CentralHub, not by workers
            logger.info(
                "Session indexes managed by CentralHub (no local index creation)"
            )
        except Exception as e:
            logger.error("Failed to initialize CentralHub client: %s", e)
            raise

        # Initialize pub/sub service
        self._pubsub_service = await get_pubsub_service()

        # Subscribe to session state updates
        await self._pubsub_service.subscribe(
            EventTopic.SESSION_STATE_UPDATE.value, self._handle_state_update
        )

        # Start batch processing task
        self._batch_task = asyncio.create_task(self._batch_processor())

        self._is_running = True
        logger.info("Session persistence worker started")

    async def stop(self):
        """
        Stop the worker and clean up resources.
        """
        if not self._is_running:
            return

        # Unsubscribe from channels
        if self._pubsub_service:
            await self._pubsub_service.unsubscribe(
                EventTopic.SESSION_STATE_UPDATE.value, self._handle_state_update
            )

        # Stop batch processor
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        # Flush any remaining batched updates
        await self._flush_batch()

        # Close CentralHub client
        if self._hub_client:
            await self._hub_client.close()

        self._is_running = False
        logger.info("Session persistence worker stopped")

    async def _handle_state_update(self, message: MessageEnvelope):
        """
        Handle a session state update message.

        Args:
            message: Message envelope containing BookSchema payload
        """
        try:
            # Validate and parse book data
            book_data = message.payload

            if not isinstance(book_data, dict):
                await self._send_error_response(
                    message, "INVALID_PAYLOAD", "Payload must be a dictionary"
                )
                return

            if "book_id" not in book_data:
                await self._send_error_response(
                    message, "MISSING_BOOK_ID", "Payload must contain book_id"
                )
                return

            book_id = book_data["book_id"]
            logger.info("Received state update for book: %s", book_id)

            # Add to batch queue (thread-safe)
            async with self._batch_lock:
                self._batch_queue[book_id] = {
                    "data": book_data,
                    "trace_id": message.trace_id,
                    "timestamp": datetime.utcnow(),
                }

        except Exception as e:
            logger.error("Error handling state update: %s", e, exc_info=True)
            await self._send_error_response(
                message,
                "INTERNAL_ERROR",
                f"Internal error processing state update: {str(e)}",
            )

    async def _batch_processor(self):
        """
        Background task that periodically flushes the batch queue to MongoDB.
        """
        while True:
            try:
                await asyncio.sleep(self.batch_interval)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in batch processor: %s", e, exc_info=True)

    async def _flush_batch(self):
        """
        Flush all batched updates to MongoDB.
        """
        if not self._batch_queue:
            return

        async with self._batch_lock:
            # Take snapshot of queue
            queue_snapshot = dict(self._batch_queue)
            self._batch_queue.clear()

        if not queue_snapshot:
            return

        logger.info("Flushing batch of %s updates to MongoDB", len(queue_snapshot))

        # Process each update
        for book_id, update_info in queue_snapshot.items():
            try:
                await self._persist_book(update_info["data"], update_info["trace_id"])
            except Exception as e:
                logger.error("Failed to persist book %s: %s", book_id, e, exc_info=True)
                await self._send_error_response_by_trace(
                    update_info["trace_id"],
                    "PERSISTENCE_ERROR",
                    f"Failed to persist book: {str(e)}",
                )

    async def _persist_book(self, book_data: Dict[str, Any], trace_id: str):
        """
        Persist a book to CentralHub via HTTP proxy with conflict detection.

        Args:
            book_data: Book data dictionary
            trace_id: Trace ID for correlation
        """
        book_id = book_data["book_id"]

        # Validate schema
        try:
            _book_schema = BookSchema(**book_data)
        except Exception as e:
            logger.error("Schema validation failed for book %s: %s", book_id, e)
            await self._send_error_response_by_trace(
                trace_id, "SCHEMA_ERROR", f"Schema validation failed: {str(e)}"
            )
            return

        # Check for existing book (conflict detection)
        try:
            existing = await self._hub_client.find_one(
                collection=SESSIONS_COLLECTION,
                query={"book_id": book_id},
                user_id=book_data.get("user_id"),
            )
        except Exception as e:
            logger.error("Failed to check existing book %s: %s", book_id, e)
            await self._send_error_response_by_trace(
                trace_id, "DB_ERROR", f"Database query failed: {str(e)}"
            )
            return

        if existing:
            existing_version = existing.get("version", 0)
            new_version = book_data.get("version", 1)

            # Simple last-write-wins with version check
            if new_version < existing_version:
                logger.warning(
                    "Version conflict for book %s: existing=%s, new=%s",
                    book_id, existing_version, new_version
                )
                await self._send_error_response_by_trace(
                    trace_id,
                    "VERSION_CONFLICT",
                    f"Version conflict: server has version {existing_version}, client sent {new_version}",
                )
                return

        # Ensure updated_at is current
        book_data["updated_at"] = datetime.utcnow()

        # Update via CentralHub
        try:
            _modified_count = await self._hub_client.update_one(
                collection=SESSIONS_COLLECTION,
                query={"book_id": book_id},
                update={"$set": book_data},
                user_id=book_data.get("user_id"),
            )

            # Note: CentralHub update_one doesn't distinguish between insert and update
            # We assume success if no error was raised
            logger.info("Persisted book %s successfully (version %s)", book_id, book_data.get('version'))

            # Send acknowledgment
            await self._send_sync_acknowledgment(
                book_id, trace_id, book_data.get("version", 1)
            )

        except Exception as e:
            logger.error("CentralHub write failed for book %s: %s", book_id, e)
            await self._send_error_response_by_trace(
                trace_id, "DB_ERROR", f"Database write failed: {str(e)}"
            )

    async def _send_sync_acknowledgment(
        self, book_id: str, correlation_id: str, version: int
    ):
        """
        Send a sync acknowledgment message.

        Args:
            book_id: Book identifier
            correlation_id: Correlation ID for the original request
            version: Persisted version number
        """
        ack_message = MessageEnvelope(
            source="backend-session-persistence-worker",
            topic=EventTopic.SESSION_STATE_SYNCED.value,
            payload={
                "book_id": book_id,
                "version": version,
                "synced_at": datetime.utcnow().isoformat(),
            },
            correlation_id=correlation_id,
        )

        if self._pubsub_service:
            await self._pubsub_service.publish(ack_message)

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
            source="backend-session-persistence-worker",
            topic=EventTopic.SESSION_STATE_ERROR.value,
            payload={"error_code": error_code, "message": error_message},
            correlation_id=original_message.trace_id,
        )

        if self._pubsub_service:
            await self._pubsub_service.publish(error_envelope)

    async def _send_error_response_by_trace(
        self, trace_id: str, error_code: str, error_message: str
    ):
        """
        Send an error response using just a trace ID.

        Args:
            trace_id: Trace ID for correlation
            error_code: Error code identifier
            error_message: Human-readable error message
        """
        error_envelope = MessageEnvelope(
            source="backend-session-persistence-worker",
            topic=EventTopic.SESSION_STATE_ERROR.value,
            payload={"error_code": error_code, "message": error_message},
            correlation_id=trace_id,
        )

        if self._pubsub_service:
            await self._pubsub_service.publish(error_envelope)


# Global worker instance
_worker: Optional[SessionPersistenceWorker] = None


async def start_session_persistence_worker():
    """
    Start the global session persistence worker.

    Returns:
        The worker instance
    """
    global _worker

    if _worker is None:
        _worker = SessionPersistenceWorker()

    await _worker.start()
    return _worker


async def stop_session_persistence_worker():
    """Stop the global session persistence worker."""
    global _worker

    if _worker is not None:
        await _worker.stop()
        _worker = None
