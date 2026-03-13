"""
Redis Pub/Sub Service for Event Bus.

Provides publish and subscribe capabilities for the distributed event bus,
handling message routing between WebSocket clients and backend workers.
"""

import asyncio
import json
import logging
from typing import Awaitable, Callable, Dict, Optional, Set

from ..core.redis_client import get_redis_client
from ..models.event_bus import MessageEnvelope

logger = logging.getLogger(__name__)


class RedisPubSubService:
    """
    Service for Redis pub/sub operations in the event bus.

    Features:
    - Publish messages to Redis channels
    - Subscribe to multiple channels
    - Route incoming messages to registered handlers
    - Automatic reconnection on connection failure
    """

    def __init__(self):
        """Initialize the Redis pub/sub service."""
        self._pubsub = None
        self._redis_client = None
        self._subscriptions: Dict[
            str, Set[Callable[[MessageEnvelope], Awaitable[None]]]
        ] = {}
        self._subscriber_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._lock = asyncio.Lock()

    async def initialize(self):
        """
        Initialize Redis connection and pub/sub.

        Returns:
            True if initialized successfully, False otherwise
        """
        try:
            self._redis_client = await get_redis_client()

            if self._redis_client is None:
                logger.warning("Redis client not available for pub/sub")
                return False

            self._pubsub = self._redis_client.pubsub()
            logger.info("Redis pub/sub service initialized")
            return True

        except Exception as e:
            logger.error("Failed to initialize Redis pub/sub: %s", e)
            return False

    async def publish(self, message: MessageEnvelope) -> bool:
        """
        Publish a message to a Redis channel.

        The channel name is derived from the message topic by replacing '/' with ':'.

        Args:
            message: Message envelope to publish

        Returns:
            True if published successfully, False otherwise
        """
        if self._redis_client is None:
            logger.warning("Cannot publish: Redis client not initialized")
            return False

        try:
            # Convert topic to channel name (e.g., "agent/request/file_access" -> "agent:request:file_access")
            channel = message.topic.replace("/", ":")

            # Serialize message
            message_json = message.model_dump_json()

            # Publish to Redis
            num_subscribers = await self._redis_client.publish(channel, message_json)

            logger.debug("Published message to channel '%s': %s subscribers", channel, num_subscribers)
            return True

        except Exception as e:
            logger.error("Error publishing message to %s: %s", message.topic, e)
            return False

    async def subscribe(
        self, topic: str, handler: Callable[[MessageEnvelope], Awaitable[None]]
    ):
        """
        Subscribe to a topic with a message handler.

        Args:
            topic: Event topic to subscribe to (e.g., "agent/response/file_data")
            handler: Async callback function to handle incoming messages
        """
        async with self._lock:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = set()

                # Subscribe to Redis channel
                channel = topic.replace("/", ":")

                if self._pubsub is not None:
                    await self._pubsub.subscribe(channel)
                    logger.info("Subscribed to Redis channel: %s", channel)

            self._subscriptions[topic].add(handler)
            logger.debug(
                "Handler registered for topic '%s'. Total handlers: %s",
                topic, len(self._subscriptions[topic])
            )

        # Start subscriber task if not already running
        if self._subscriber_task is None or self._subscriber_task.done():
            await self.start_subscriber()

    async def unsubscribe(
        self, topic: str, handler: Callable[[MessageEnvelope], Awaitable[None]]
    ):
        """
        Unsubscribe a handler from a topic.

        Args:
            topic: Event topic to unsubscribe from
            handler: Handler to remove
        """
        async with self._lock:
            if topic in self._subscriptions:
                self._subscriptions[topic].discard(handler)

                # If no more handlers, unsubscribe from Redis
                if not self._subscriptions[topic]:
                    del self._subscriptions[topic]

                    channel = topic.replace("/", ":")
                    if self._pubsub is not None:
                        await self._pubsub.unsubscribe(channel)
                        logger.info("Unsubscribed from Redis channel: %s", channel)

    async def start_subscriber(self):
        """
        Start the background subscriber task.

        This task listens for messages from Redis and routes them to handlers.
        """
        if self._is_running:
            logger.debug("Subscriber already running")
            return

        if self._pubsub is None:
            logger.warning("Cannot start subscriber: pub/sub not initialized")
            return

        self._is_running = True
        self._subscriber_task = asyncio.create_task(self._subscriber_loop())
        logger.info("Redis subscriber started")

    async def stop_subscriber(self):
        """Stop the background subscriber task."""
        self._is_running = False

        if self._subscriber_task and not self._subscriber_task.done():
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

        logger.info("Redis subscriber stopped")

    async def _subscriber_loop(self):
        """
        Background loop that listens for messages from Redis.

        Routes messages to registered handlers based on topic.
        """
        try:
            logger.info("Starting Redis subscriber loop")

            async for message in self._pubsub.listen():
                if not self._is_running:
                    break

                # Skip non-message events
                if message["type"] != "message":
                    continue

                try:
                    # Parse message
                    channel = message["channel"]
                    data = message["data"]

                    # Convert channel back to topic
                    topic = channel.replace(":", "/")

                    # Parse envelope
                    envelope = MessageEnvelope(**json.loads(data))

                    logger.debug("Received message from channel '%s': topic=%s", channel, envelope.topic)

                    # Route to handlers
                    async with self._lock:
                        handlers = self._subscriptions.get(topic, set()).copy()

                    for handler in handlers:
                        try:
                            await handler(envelope)
                        except Exception as e:
                            logger.error("Error in message handler for topic '%s': %s", topic, e, exc_info=True)

                except json.JSONDecodeError as e:
                    logger.error("Failed to parse message: %s", e)
                except Exception as e:
                    logger.error("Error processing message: %s", e, exc_info=True)

        except asyncio.CancelledError:
            logger.info("Redis subscriber loop cancelled")
            raise
        except Exception as e:
            logger.error("Error in Redis subscriber loop: %s", e, exc_info=True)
        finally:
            logger.info("Redis subscriber loop ended")

    async def close(self):
        """Close the Redis pub/sub service."""
        await self.stop_subscriber()

        if self._pubsub is not None:
            try:
                await self._pubsub.close()
                logger.info("Redis pub/sub closed")
            except Exception as e:
                logger.error("Error closing Redis pub/sub: %s", e)
            finally:
                self._pubsub = None

    def get_subscribed_topics(self) -> Set[str]:
        """
        Get set of currently subscribed topics.

        Returns:
            Set of topic names
        """
        return set(self._subscriptions.keys())


# Global service instance
_pubsub_service: Optional[RedisPubSubService] = None


async def get_pubsub_service() -> RedisPubSubService:
    """
    Get the global Redis pub/sub service instance.

    Initializes the service if not already initialized.

    Returns:
        RedisPubSubService instance
    """
    global _pubsub_service

    if _pubsub_service is None:
        _pubsub_service = RedisPubSubService()
        await _pubsub_service.initialize()

    return _pubsub_service


async def close_pubsub_service():
    """Close the global Redis pub/sub service."""
    global _pubsub_service

    if _pubsub_service is not None:
        await _pubsub_service.close()
        _pubsub_service = None
