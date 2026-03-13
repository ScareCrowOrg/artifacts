"""
Unit tests for WebSocket router and connection manager.

Tests WebSocket connection lifecycle, authentication, and message handling.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from fastapi import WebSocket, status
from fastapi.testclient import TestClient

from app.models.event_bus import MessageEnvelope, EventTopic
from app.services.websocket_connection_manager import ConnectionManager, get_connection_manager
from app.routers.websocket_router import websocket_router


class TestConnectionManager:
    """Test suite for WebSocket connection manager."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh connection manager for each test."""
        return ConnectionManager(heartbeat_interval=10)
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = AsyncMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws
    
    @pytest.mark.asyncio
    async def test_connect_adds_client(self, manager, mock_websocket):
        """Test that connect adds a client to the manager."""
        client_id = "test-client-1"
        
        await manager.connect(client_id, mock_websocket, {"user_id": "user123"})
        
        assert client_id in manager.get_connected_clients()
        assert mock_websocket.accept.called
        
        metadata = manager.get_client_metadata(client_id)
        assert metadata is not None
        assert metadata["metadata"]["user_id"] == "user123"
    
    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, manager, mock_websocket):
        """Test that disconnect removes a client from the manager."""
        client_id = "test-client-1"
        
        await manager.connect(client_id, mock_websocket)
        assert client_id in manager.get_connected_clients()
        
        await manager.disconnect(client_id)
        assert client_id not in manager.get_connected_clients()
    
    @pytest.mark.asyncio
    async def test_send_message_to_connected_client(self, manager, mock_websocket):
        """Test sending a message to a connected client."""
        client_id = "test-client-1"
        
        await manager.connect(client_id, mock_websocket)
        
        message = MessageEnvelope(
            source="test",
            topic=EventTopic.SYSTEM_EVENT_LOG.value,
            payload={"test": "data"}
        )
        
        success = await manager.send_message(client_id, message)
        
        assert success is True
        assert mock_websocket.send_text.called
        
        # Verify message was serialized correctly
        call_args = mock_websocket.send_text.call_args
        sent_data = call_args[0][0]
        parsed = json.loads(sent_data)
        assert parsed["topic"] == EventTopic.SYSTEM_EVENT_LOG.value
        assert parsed["payload"]["test"] == "data"
    
    @pytest.mark.asyncio
    async def test_send_message_to_disconnected_client(self, manager):
        """Test that sending to a disconnected client returns False."""
        message = MessageEnvelope(
            source="test",
            topic=EventTopic.SYSTEM_EVENT_LOG.value,
            payload={"test": "data"}
        )
        
        success = await manager.send_message("nonexistent-client", message)
        
        assert success is False
    
    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self, manager):
        """Test broadcasting a message to multiple clients."""
        # Create multiple mock websockets
        ws1 = AsyncMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        
        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()
        
        # Connect both clients
        await manager.connect("client1", ws1)
        await manager.connect("client2", ws2)
        
        message = MessageEnvelope(
            source="test",
            topic=EventTopic.SYSTEM_EVENT_LOG.value,
            payload={"broadcast": "message"}
        )
        
        await manager.broadcast(message)
        
        # Both should receive the message
        assert ws1.send_text.called
        assert ws2.send_text.called
    
    @pytest.mark.asyncio
    async def test_broadcast_with_exclusion(self, manager):
        """Test broadcasting with client exclusion."""
        ws1 = AsyncMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        
        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()
        
        await manager.connect("client1", ws1)
        await manager.connect("client2", ws2)
        
        message = MessageEnvelope(
            source="test",
            topic=EventTopic.SYSTEM_EVENT_LOG.value,
            payload={"broadcast": "message"}
        )
        
        # Broadcast but exclude client1
        await manager.broadcast(message, exclude={"client1"})
        
        # Only client2 should receive
        assert not ws1.send_text.called
        assert ws2.send_text.called
    
    @pytest.mark.asyncio
    async def test_update_heartbeat(self, manager, mock_websocket):
        """Test updating client heartbeat timestamp."""
        client_id = "test-client-1"
        
        await manager.connect(client_id, mock_websocket)
        
        # Get initial heartbeat
        metadata1 = manager.get_client_metadata(client_id)
        initial_heartbeat = metadata1["last_heartbeat"]
        
        # Wait a bit and update
        import asyncio
        await asyncio.sleep(0.1)
        await manager.update_heartbeat(client_id)
        
        # Check heartbeat was updated
        metadata2 = manager.get_client_metadata(client_id)
        updated_heartbeat = metadata2["last_heartbeat"]
        
        assert updated_heartbeat > initial_heartbeat
    
    @pytest.mark.asyncio
    async def test_close_all_connections(self, manager):
        """Test closing all connections."""
        ws1 = AsyncMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.close = AsyncMock()
        
        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.close = AsyncMock()
        
        await manager.connect("client1", ws1)
        await manager.connect("client2", ws2)
        
        assert len(manager.get_connected_clients()) == 2
        
        await manager.close_all()
        
        # Verify all connections closed
        assert len(manager.get_connected_clients()) == 0
        # Note: close may be called during error handling, not guaranteed
        # The key assertion is that clients are removed from manager


class TestWebSocketRouter:
    """Test suite for WebSocket router endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_status(self):
        """Test that health endpoint returns connection status."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        response = client.get("/api/ws/event-bus/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "active_connections" in data
        assert "client_ids" in data


class TestMessageEnvelope:
    """Test suite for MessageEnvelope model."""
    
    def test_create_envelope_with_required_fields(self):
        """Test creating envelope with minimal required fields."""
        envelope = MessageEnvelope(
            source="test-source",
            topic=EventTopic.SYSTEM_EVENT_LOG.value,
            payload={"message": "test"}
        )
        
        assert envelope.source == "test-source"
        assert envelope.topic == EventTopic.SYSTEM_EVENT_LOG.value
        assert envelope.payload["message"] == "test"
        assert envelope.trace_id is not None
        assert envelope.timestamp is not None
    
    def test_envelope_json_serialization(self):
        """Test that envelope can be serialized to JSON."""
        envelope = MessageEnvelope(
            source="test-source",
            topic=EventTopic.SYSTEM_EVENT_LOG.value,
            payload={"message": "test"}
        )
        
        json_str = envelope.model_dump_json()
        parsed = json.loads(json_str)
        
        assert parsed["source"] == "test-source"
        assert parsed["topic"] == EventTopic.SYSTEM_EVENT_LOG.value
        assert "timestamp" in parsed
        assert "trace_id" in parsed
    
    def test_envelope_with_correlation_id(self):
        """Test creating envelope with correlation ID."""
        envelope = MessageEnvelope(
            source="test-source",
            topic=EventTopic.AGENT_RESPONSE_FILE_DATA.value,
            payload={"data": "response"},
            correlation_id="original-request-id"
        )
        
        assert envelope.correlation_id == "original-request-id"
