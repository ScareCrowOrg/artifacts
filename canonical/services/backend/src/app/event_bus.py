"""
Lightweight in-memory event bus for real-time updates.

This module provides a simple publish-subscribe event bus for broadcasting
cell state changes and fragment additions to connected SSE clients.

For production, consider replacing with Redis Pub/Sub for scalability.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Set

from .utils.json_serialization import serialize_for_json

logger = logging.getLogger(__name__)


class EventBus:
    """
    Simple in-memory event bus for pub-sub messaging.

    Supports multiple subscribers per topic.
    Thread-safe using asyncio primitives.
    """

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: Dict[
            str, Set[Callable[[Dict[str, Any]], Awaitable[None]]]
        ] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self, topic: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Subscribe to a topic with a callback.

        Args:
            topic: Topic name to subscribe to (e.g., "issues-queue")
            callback: Async callback function that receives event data
        """
        async with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = set()
            self._subscribers[topic].add(callback)
            logger.info("Subscriber added to topic '%s'. Total: %s", topic, len(self._subscribers[topic]))

    async def unsubscribe(
        self, topic: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """
        Unsubscribe from a topic.

        Args:
            topic: Topic name to unsubscribe from
            callback: The callback function to remove
        """
        async with self._lock:
            if topic in self._subscribers:
                self._subscribers[topic].discard(callback)
                logger.info("Subscriber removed from topic '%s'. Remaining: %s", topic, len(self._subscribers[topic]))

                # Clean up empty topic
                if not self._subscribers[topic]:
                    del self._subscribers[topic]

    async def publish(self, topic: str, event_data: Dict[str, Any]) -> None:
        """
        Publish an event to all subscribers of a topic.

        Args:
            topic: Topic name to publish to
            event_data: Event data dictionary
        """
        async with self._lock:
            subscribers = self._subscribers.get(topic, set()).copy()

        if not subscribers:
            logger.debug("No subscribers for topic '%s'", topic)
            return

        # Add timestamp if not present
        if "timestamp" not in event_data:
            event_data["timestamp"] = datetime.utcnow().isoformat()

        # Serialize event data to ensure JSON compatibility (handles datetime objects recursively)
        # Create a copy to avoid modifying the caller's data
        serialized_data = serialize_for_json(event_data.copy())

        logger.info("Publishing event to topic '%s' with %s subscribers", topic, len(subscribers))

        # Notify all subscribers (fire and forget)
        for callback in subscribers:
            try:
                asyncio.create_task(callback(serialized_data))
            except Exception as e:
                logger.error("Error notifying subscriber: %s", e)

    def publish_sync(self, topic: str, event_data: Dict[str, Any]) -> None:
        """
        Synchronous wrapper for publish() - schedules event in event loop.

        Safe to call from synchronous code when event loop is running.

        Args:
            topic: Topic name to publish to
            event_data: Event data dictionary
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.publish(topic, event_data))
            else:
                # If loop is not running, run it temporarily
                loop.run_until_complete(self.publish(topic, event_data))
        except RuntimeError:
            # No event loop available - events will be lost
            logger.warning("No event loop available to publish event to '%s'", topic)


# Global event bus instance
event_bus = EventBus()


# Helper functions for common event types


async def publish_cell_state_changed(
    cell_id: str, new_state: str, cell_data: Dict[str, Any] = None
) -> None:
    """
    Publish a cell state change event.

    Args:
        cell_id: ID of the cell
        new_state: New state value
        cell_data: Optional full cell data
    """
    event_data = {
        "event_type": "cell_state_changed",
        "cell_id": cell_id,
        "new_state": new_state,
        "cell_data": cell_data,
    }
    await event_bus.publish("issues-queue", event_data)


def publish_cell_state_changed_sync(
    cell_id: str, new_state: str, cell_data: Dict[str, Any] = None
) -> None:
    """
    Synchronous wrapper for publish_cell_state_changed.

    Args:
        cell_id: ID of the cell
        new_state: New state value
        cell_data: Optional full cell data
    """
    event_data = {
        "event_type": "cell_state_changed",
        "cell_id": cell_id,
        "new_state": new_state,
        "cell_data": cell_data,
    }
    event_bus.publish_sync("issues-queue", event_data)


async def publish_fragment_added(cell_id: str, fragment: Dict[str, Any]) -> None:
    """
    Publish a fragment addition event.

    Args:
        cell_id: ID of the cell
        fragment: Fragment data (tipo, conteudo, resultado)
    """
    event_data = {
        "event_type": "fragment_added",
        "cell_id": cell_id,
        "fragment": fragment,
    }
    await event_bus.publish("issues-queue", event_data)


def publish_fragment_added_sync(cell_id: str, fragment: Dict[str, Any]) -> None:
    """
    Synchronous wrapper for publish_fragment_added.

    Args:
        cell_id: ID of the cell
        fragment: Fragment data (tipo, conteudo, resultado)
    """
    event_data = {
        "event_type": "fragment_added",
        "cell_id": cell_id,
        "fragment": fragment,
    }
    event_bus.publish_sync("issues-queue", event_data)


async def publish_cell_created(cell_id: str, cell_data: Dict[str, Any]) -> None:
    """
    Publish a cell creation event.

    Args:
        cell_id: ID of the cell
        cell_data: Full cell data
    """
    event_data = {
        "event_type": "cell_created",
        "cell_id": cell_id,
        "cell_data": cell_data,
    }
    await event_bus.publish("issues-queue", event_data)


def publish_cell_created_sync(cell_id: str, cell_data: Dict[str, Any]) -> None:
    """
    Synchronous wrapper for publish_cell_created.

    Args:
        cell_id: ID of the cell
        cell_data: Full cell data
    """
    event_data = {
        "event_type": "cell_created",
        "cell_id": cell_id,
        "cell_data": cell_data,
    }
    event_bus.publish_sync("issues-queue", event_data)
