"""
Unit tests for Redis pub/sub service.

Tests message publishing, subscription, and routing functionality.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.models.event_bus import MessageEnvelope, EventTopic
from app.services.redis_pubsub_service import RedisPubSubService, get_pubsub_service


class TestRedisPubSubService:
    """Test suite for Redis pub/sub service."""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        client = AsyncMock()
        client.publish = AsyncMock(return_value=1)  # 1 subscriber
        client.pubsub = Mock(return_value=AsyncMock())
        return client
    
    @pytest.fixture
    async def service(self, mock_redis_client):
        """Create a Redis pub/sub service with mocked Redis."""
        service = RedisPubSubService()
        service._redis_client = mock_redis_client
        service._pubsub = mock_redis_client.pubsub()
        service._pubsub.subscribe = AsyncMock()
        service._pubsub.unsubscribe = AsyncMock()
        service._pubsub.close = AsyncMock()
        return service
    
    @pytest.mark.asyncio
    async def test_publish_message_success(self, service, mock_redis_client):
        """Test successfully publishing a message."""
        message = MessageEnvelope(
            source="test",
            topic=EventTopic.AGENT_REQUEST_FILE_ACCESS.value,
            payload={"path": "/test/file.txt"}
        )
        
        success = await service.publish(message)
        
        assert success is True
        assert mock_redis_client.publish.called
        
        # Verify channel conversion (/ -> :)
        call_args = mock_redis_client.publish.call_args
        channel = call_args[0][0]
        assert channel == "agent:request:file_access"
    
    @pytest.mark.asyncio
    async def test_publish_without_redis(self):
        """Test publishing when Redis is not available."""
        service = RedisPubSubService()
        # Don't initialize Redis client
        
        message = MessageEnvelope(
            source="test",
            topic=EventTopic.AGENT_REQUEST_FILE_ACCESS.value,
            payload={"test": "data"}
        )
        
        success = await service.publish(message)
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_subscribe_to_topic(self, service):
        """Test subscribing to a topic."""
        handler = AsyncMock()
        topic = EventTopic.AGENT_RESPONSE_FILE_DATA.value
        
        await service.subscribe(topic, handler)
        
        assert topic in service.get_subscribed_topics()
        assert handler in service._subscriptions[topic]
        
        # Verify Redis subscription
        assert service._pubsub.subscribe.called
        call_args = service._pubsub.subscribe.call_args
        channel = call_args[0][0]
        assert channel == "agent:response:file_data"
    
    @pytest.mark.asyncio
    async def test_subscribe_multiple_handlers_same_topic(self, service):
        """Test subscribing multiple handlers to the same topic."""
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        topic = EventTopic.AGENT_RESPONSE_FILE_DATA.value
        
        await service.subscribe(topic, handler1)
        await service.subscribe(topic, handler2)
        
        assert len(service._subscriptions[topic]) == 2
        assert handler1 in service._subscriptions[topic]
        assert handler2 in service._subscriptions[topic]
    
    @pytest.mark.asyncio
    async def test_unsubscribe_from_topic(self, service):
        """Test unsubscribing a handler from a topic."""
        handler = AsyncMock()
        topic = EventTopic.AGENT_RESPONSE_FILE_DATA.value
        
        await service.subscribe(topic, handler)
        assert topic in service.get_subscribed_topics()
        
        await service.unsubscribe(topic, handler)
        
        # Topic should be removed since no handlers remain
        assert topic not in service.get_subscribed_topics()
        assert service._pubsub.unsubscribe.called
    
    @pytest.mark.asyncio
    async def test_unsubscribe_one_of_multiple_handlers(self, service):
        """Test unsubscribing one handler when multiple exist."""
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        topic = EventTopic.AGENT_RESPONSE_FILE_DATA.value
        
        await service.subscribe(topic, handler1)
        await service.subscribe(topic, handler2)
        
        await service.unsubscribe(topic, handler1)
        
        # Topic should still exist with handler2
        assert topic in service.get_subscribed_topics()
        assert handler1 not in service._subscriptions[topic]
        assert handler2 in service._subscriptions[topic]
    
    @pytest.mark.asyncio
    async def test_topic_to_channel_conversion(self, service, mock_redis_client):
        """Test that topics are correctly converted to Redis channels."""
        message = MessageEnvelope(
            source="test",
            topic="agent/request/file_access",
            payload={}
        )
        
        await service.publish(message)
        
        call_args = mock_redis_client.publish.call_args
        channel = call_args[0][0]
        
        # Verify / -> : conversion
        assert channel == "agent:request:file_access"
    
    @pytest.mark.asyncio
    async def test_message_serialization_on_publish(self, service, mock_redis_client):
        """Test that messages are properly serialized when published."""
        message = MessageEnvelope(
            source="test-source",
            topic=EventTopic.SYSTEM_EVENT_LOG.value,
            payload={"key": "value"}
        )
        
        await service.publish(message)
        
        call_args = mock_redis_client.publish.call_args
        published_data = call_args[0][1]
        
        # Verify it's valid JSON
        parsed = json.loads(published_data)
        assert parsed["source"] == "test-source"
        assert parsed["payload"]["key"] == "value"
    
    @pytest.mark.asyncio
    async def test_start_and_stop_subscriber(self, service):
        """Test starting and stopping the subscriber task."""
        # Mock the listen method to prevent actual subscription
        service._pubsub.listen = AsyncMock()
        service._pubsub.listen.return_value = AsyncMock()
        service._pubsub.listen.return_value.__aiter__ = AsyncMock(return_value=iter([]))
        
        await service.start_subscriber()
        assert service._is_running is True
        assert service._subscriber_task is not None
        
        await service.stop_subscriber()
        assert service._is_running is False
    
    @pytest.mark.asyncio
    async def test_close_service(self, service):
        """Test closing the service."""
        pubsub_mock = service._pubsub
        
        await service.close()
        
        assert pubsub_mock.close.called
        # After close, _pubsub is set to None
        assert service._pubsub is None


class TestGetPubSubService:
    """Test suite for get_pubsub_service singleton."""
    
    @pytest.mark.asyncio
    @patch('app.services.redis_pubsub_service.get_redis_client')
    async def test_get_service_initializes_once(self, mock_get_redis):
        """Test that get_pubsub_service returns the same instance."""
        mock_redis = AsyncMock()
        mock_redis.pubsub = Mock(return_value=AsyncMock())
        mock_get_redis.return_value = mock_redis
        
        # Import here to avoid global state issues
        from app.services.redis_pubsub_service import get_pubsub_service, _pubsub_service
        
        # Reset global state
        import app.services.redis_pubsub_service as module
        module._pubsub_service = None
        
        service1 = await get_pubsub_service()
        service2 = await get_pubsub_service()
        
        assert service1 is service2
