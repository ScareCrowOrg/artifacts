"""
Log Collection Worker for Event Bus.

Listens to error and warning events and stores them in CentralHub
for centralized logging and analysis.

Architecture:
- Uses CentralHubClient HTTP proxy (no direct MongoDB connection)
- Supports offline operation when CentralHub is unavailable
- Batch processing for performance
"""

import asyncio
import logging
from typing import Optional

from ..config.database import CENTRALHUB_URL, MONGODB_ENABLED
from ..database.centralhub_client import CentralHubClient
from ..database.schemas.log_schema import LogEntrySchema
from ..database.schemas.session_schema import LOGS_COLLECTION
from ..models.event_bus import EventTopic, MessageEnvelope
from ..services.redis_pubsub_service import get_pubsub_service

logger = logging.getLogger(__name__)


class LogCollectionWorker:
    """
    Worker that collects logs and errors from the event bus.

    Features:
    - Listen to system:event:error and system:event:warning channels
    - Extract error/log details from message payload
    - Store in CentralHub via HTTP proxy (no direct MongoDB)
    - TTL index for automatic 30-day retention (managed by CentralHub)
    - Batch processing for performance
    """

    def __init__(
        self, centralhub_url: Optional[str] = None, batch_interval: float = 1.0
    ):
        """
        Initialize the log collection worker.

        Args:
            centralhub_url: CentralHub URL (defaults to config)
            batch_interval: Batch processing interval in seconds
        """
        self.centralhub_url = centralhub_url or CENTRALHUB_URL
        self.batch_interval = batch_interval
        self._is_running = False
        self._pubsub_service = None
        self._hub_client: Optional[CentralHubClient] = None
        self._batch_queue: list = []
        self._batch_lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None

        logger.info("Log collection worker initialized with batch interval: %ss", batch_interval)

    async def start(self):
        """
        Start the worker and subscribe to log events.
        """
        if self._is_running:
            logger.warning("Worker already running")
            return

        if not MONGODB_ENABLED:
            logger.warning("MongoDB is disabled - log collection worker will not start")
            return

        # Initialize CentralHub client
        try:
            self._hub_client = CentralHubClient(
                base_url=self.centralhub_url,
                enabled=True,
            )
            logger.info("CentralHub client initialized: %s", self.centralhub_url)

            # Note: Index creation (including TTL) is handled by CentralHub, not by workers
            logger.info(
                "Log indexes (including TTL) managed by CentralHub (no local index creation)"
            )
        except Exception as e:
            logger.error("Failed to initialize CentralHub client: %s", e)
            raise

        # Initialize pub/sub service
        self._pubsub_service = await get_pubsub_service()

        # Subscribe to error and log events
        await self._pubsub_service.subscribe(
            EventTopic.SYSTEM_EVENT_ERROR.value, self._handle_log_event
        )

        # Note: Add SYSTEM_EVENT_WARNING if/when it's defined in EventTopic
        # await self._pubsub_service.subscribe(
        #     EventTopic.SYSTEM_EVENT_WARNING.value,
        #     self._handle_log_event
        # )

        # Start batch processing task
        self._batch_task = asyncio.create_task(self._batch_processor())

        self._is_running = True
        logger.info("Log collection worker started")

    async def stop(self):
        """
        Stop the worker and clean up resources.
        """
        if not self._is_running:
            return

        # Unsubscribe from channels
        if self._pubsub_service:
            await self._pubsub_service.unsubscribe(
                EventTopic.SYSTEM_EVENT_ERROR.value, self._handle_log_event
            )

        # Stop batch processor
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        # Flush any remaining batched logs
        await self._flush_batch()

        # Close CentralHub client
        if self._hub_client:
            await self._hub_client.close()

        self._is_running = False
        logger.info("Log collection worker stopped")

    async def _handle_log_event(self, message: MessageEnvelope):
        """
        Handle a log/error event message.

        Args:
            message: Message envelope containing log/error payload
        """
        try:
            payload = message.payload

            # Determine log level from topic or payload
            level = "error"  # Default
            if message.topic == EventTopic.SYSTEM_EVENT_ERROR.value:
                level = "error"
            # Add more topic-to-level mappings as needed

            # Extract log details
            log_message = payload.get("message", "No message provided")
            error_code = payload.get("error_code")
            stack_trace = payload.get("stack_trace")
            details = payload.get("details", {})

            # Build log entry
            log_entry = {
                "log_id": message.trace_id,
                "timestamp": message.timestamp,
                "level": level,
                "source": message.source,
                "message": log_message,
                "stack_trace": stack_trace,
                "user_id": details.get("user_id"),
                "client_id": details.get("client_id"),
                "context": {
                    "error_code": error_code,
                    "correlation_id": message.correlation_id,
                    **details,
                },
            }

            # Add to batch queue
            async with self._batch_lock:
                self._batch_queue.append(log_entry)

        except Exception as e:
            logger.error("Error handling log event: %s", e, exc_info=True)

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
        Flush all batched log entries to CentralHub.
        """
        if not self._batch_queue:
            return

        async with self._batch_lock:
            # Take snapshot of queue
            queue_snapshot = list(self._batch_queue)
            self._batch_queue.clear()

        if not queue_snapshot:
            return

        logger.info("Flushing batch of %s log entries to CentralHub", len(queue_snapshot))

        try:
            # Validate and insert logs one by one (CentralHub doesn't have insert_many yet)
            successful_inserts = 0
            for log_data in queue_snapshot:
                try:
                    log_entry = LogEntrySchema(**log_data)
                    await self._hub_client.insert_one(
                        collection=LOGS_COLLECTION,
                        document=log_entry.model_dump(),
                        user_id=log_data.get("user_id"),
                    )
                    successful_inserts += 1
                except Exception as e:
                    logger.error("Failed to insert log entry: %s", e)

            if successful_inserts > 0:
                logger.info("Inserted %s log entries to CentralHub", successful_inserts)

        except Exception as e:
            logger.error("Failed to insert log batch: %s", e, exc_info=True)


# Global worker instance
_worker: Optional[LogCollectionWorker] = None


async def start_log_collection_worker():
    """
    Start the global log collection worker.

    Returns:
        The worker instance
    """
    global _worker

    if _worker is None:
        _worker = LogCollectionWorker()

    await _worker.start()
    return _worker


async def stop_log_collection_worker():
    """Stop the global log collection worker."""
    global _worker

    if _worker is not None:
        await _worker.stop()
        _worker = None
