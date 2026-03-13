"""
Unit tests for orchestrator helper functions.

Tests cover:
- Fragment publishing to Redis and event bus
- Fallback behavior when Redis is disabled
- Pipeline fragment publishing

Ensures 90% test coverage as per RULESET.md Rule 3.1.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

from app.orchestrator.helpers import (
    publish_fragment_to_redis,
    publish_pipeline_fragments,
    set_redis_client
)
from app.core.models import Fragment as CoreFragment, PipelineItem


# Test Fixtures

@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    client = Mock()
    client.publish = Mock()
    return client


@pytest.fixture
def sample_fragment():
    """Sample CoreFragment for testing."""
    return CoreFragment(
        id="frag-123",
        type="execucao",
        content="Test fragment",
        result="success",
        metadata={}
    )


@pytest.fixture
def sample_pipeline_item():
    """Sample PipelineItem with fragments."""
    item = Mock(spec=PipelineItem)
    item.cell_id = "cell-456"
    
    # Create mock fragments
    fragments = [
        CoreFragment(
            id=f"frag-{i}",
            type="info",
            content=f"Fragment {i}",
            result=None,
            metadata={}
        )
        for i in range(3)
    ]
    
    item.get_fragments_since = Mock(return_value=fragments)
    return item


# Tests for publish_fragment_to_redis

def test_publish_fragment_to_redis_with_redis_enabled(mock_redis_client, sample_fragment):
    """Test fragment publishing when Redis is enabled."""
    # Setup
    set_redis_client(mock_redis_client)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute
        publish_fragment_to_redis("cell-123", sample_fragment)
        
        # Verify Redis publish was called
        assert mock_redis_client.publish.called
        call_args = mock_redis_client.publish.call_args
        assert call_args[0][0] == "cell:cell-123:fragmentos"
        
        # Verify event bus was also called
        mock_event_bus.assert_called_once()
        event_bus_call = mock_event_bus.call_args
        assert event_bus_call[0][0] == "cell-123"


def test_publish_fragment_to_redis_without_redis(sample_fragment):
    """Test fragment publishing when Redis is disabled (None)."""
    # Setup - disable Redis
    set_redis_client(None)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute
        publish_fragment_to_redis("cell-123", sample_fragment)
        
        # Verify event bus was called even without Redis
        mock_event_bus.assert_called_once()
        event_bus_call = mock_event_bus.call_args
        assert event_bus_call[0][0] == "cell-123"
        
        # Extract fragment dict from call
        fragment_dict = event_bus_call[0][1]
        assert fragment_dict["type"] == "execucao"
        assert fragment_dict["content"] == "Test fragment"


def test_publish_fragment_to_redis_handles_redis_error(mock_redis_client, sample_fragment):
    """Test that Redis errors are handled gracefully."""
    # Setup Redis to raise error
    mock_redis_client.publish.side_effect = Exception("Redis connection error")
    set_redis_client(mock_redis_client)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute - should not raise
        publish_fragment_to_redis("cell-123", sample_fragment)
        
        # Verify event bus was still called despite Redis error
        mock_event_bus.assert_called_once()


def test_publish_fragment_to_redis_handles_event_bus_error(mock_redis_client, sample_fragment):
    """Test that event bus errors are handled gracefully."""
    # Setup event bus to raise error
    set_redis_client(mock_redis_client)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        mock_event_bus.side_effect = Exception("Event bus error")
        
        # Execute - should not raise
        publish_fragment_to_redis("cell-123", sample_fragment)
        
        # Redis should still be called despite event bus error
        assert mock_redis_client.publish.called


def test_publish_fragment_to_redis_formats_message_correctly(mock_redis_client, sample_fragment):
    """Test that fragment is properly serialized to JSON."""
    # Setup
    set_redis_client(mock_redis_client)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync'):
        # Execute
        publish_fragment_to_redis("cell-999", sample_fragment)
        
        # Verify Redis message format
        call_args = mock_redis_client.publish.call_args
        channel = call_args[0][0]
        message = call_args[0][1]
        
        assert channel == "cell:cell-999:fragmentos"
        # Message should be JSON string
        assert isinstance(message, str)
        assert "frag-123" in message  # Fragment ID should be in JSON


# Tests for publish_pipeline_fragments

def test_publish_pipeline_fragments_publishes_all_fragments(sample_pipeline_item):
    """Test that all pipeline fragments are published."""
    # Setup
    set_redis_client(None)  # Test without Redis
    
    with patch('app.orchestrator.helpers.publish_fragment_to_redis') as mock_publish:
        # Execute
        publish_pipeline_fragments(sample_pipeline_item)
        
        # Verify publish was called for each fragment
        assert mock_publish.call_count == 3
        
        # Verify cell_id was correct in each call
        for call_item in mock_publish.call_args_list:
            assert call_item[0][0] == "cell-456"


def test_publish_pipeline_fragments_with_since_fragment_id(sample_pipeline_item):
    """Test publishing only fragments after a specific ID."""
    # Setup
    set_redis_client(None)
    
    with patch('app.orchestrator.helpers.publish_fragment_to_redis') as mock_publish:
        # Execute with since_fragment_id
        publish_pipeline_fragments(sample_pipeline_item, since_fragment_id="frag-0")
        
        # Verify get_fragments_since was called with correct parameter
        sample_pipeline_item.get_fragments_since.assert_called_once_with("frag-0")
        
        # Verify fragments were published
        assert mock_publish.called


def test_publish_pipeline_fragments_handles_empty_fragments():
    """Test publishing when no new fragments exist."""
    # Setup pipeline item with no fragments
    item = Mock(spec=PipelineItem)
    item.cell_id = "cell-empty"
    item.get_fragments_since = Mock(return_value=[])
    
    with patch('app.orchestrator.helpers.publish_fragment_to_redis') as mock_publish:
        # Execute
        publish_pipeline_fragments(item)
        
        # Verify publish was not called
        mock_publish.assert_not_called()


def test_publish_pipeline_fragments_preserves_order():
    """Test that fragments are published in order."""
    # Setup
    item = Mock(spec=PipelineItem)
    item.cell_id = "cell-ordered"
    
    fragments = [
        CoreFragment(id=f"frag-{i}", type="info", content=f"Content {i}", result=None, metadata={})
        for i in range(5)
    ]
    item.get_fragments_since = Mock(return_value=fragments)
    
    published_fragments = []
    
    def capture_publish(cell_id, fragment):
        published_fragments.append(fragment.id)
    
    with patch('app.orchestrator.helpers.publish_fragment_to_redis', side_effect=capture_publish):
        # Execute
        publish_pipeline_fragments(item)
        
        # Verify order
        assert published_fragments == ["frag-0", "frag-1", "frag-2", "frag-3", "frag-4"]


# Tests for set_redis_client

def test_set_redis_client_updates_global(mock_redis_client):
    """Test that set_redis_client updates the global client."""
    # Execute
    set_redis_client(mock_redis_client)
    
    # Verify by publishing a fragment
    fragment = CoreFragment(
        id="test",
        type="test",
        content="test",
        result=None,
        metadata={}
    )
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync'):
        publish_fragment_to_redis("cell-test", fragment)
        
        # Should have called Redis
        assert mock_redis_client.publish.called


def test_set_redis_client_can_disable():
    """Test that Redis can be disabled by setting to None."""
    # Setup with Redis first
    mock_client = Mock()
    set_redis_client(mock_client)
    
    # Disable Redis
    set_redis_client(None)
    
    # Verify publishing works without Redis
    fragment = CoreFragment(
        id="test2",
        type="test",
        content="test",
        result=None,
        metadata={}
    )
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync'):
        publish_fragment_to_redis("cell-test2", fragment)
        
        # Should not have called the previous client
        mock_client.publish.assert_not_called()


# Integration tests

def test_full_publishing_flow_with_redis(mock_redis_client):
    """Integration test for complete publishing flow with Redis."""
    # Setup
    set_redis_client(mock_redis_client)
    
    # Create pipeline item
    item = Mock(spec=PipelineItem)
    item.cell_id = "cell-integration"
    
    fragments = [
        CoreFragment(
            id=f"frag-{i}",
            type="execucao",
            content=f"Step {i}",
            result="success" if i > 0 else None,
            metadata={"step": i}
        )
        for i in range(3)
    ]
    item.get_fragments_since = Mock(return_value=fragments)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute
        publish_pipeline_fragments(item)
        
        # Verify all Redis publishes
        assert mock_redis_client.publish.call_count == 3
        
        # Verify all event bus publishes
        assert mock_event_bus.call_count == 3
        
        # Verify all publishes used correct cell_id
        for call_item in mock_redis_client.publish.call_args_list:
            assert "cell-integration" in call_item[0][0]


def test_full_publishing_flow_without_redis():
    """Integration test for complete publishing flow without Redis."""
    # Setup - no Redis
    set_redis_client(None)
    
    # Create pipeline item
    item = Mock(spec=PipelineItem)
    item.cell_id = "cell-no-redis"
    
    fragments = [
        CoreFragment(
            id=f"frag-{i}",
            type="info",
            content=f"Info {i}",
            result=None,
            metadata={}
        )
        for i in range(2)
    ]
    item.get_fragments_since = Mock(return_value=fragments)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute
        publish_pipeline_fragments(item)
        
        # Verify event bus received all fragments
        assert mock_event_bus.call_count == 2
        
        # Verify fragments were properly formatted
        for call_item in mock_event_bus.call_args_list:
            cell_id, fragment_dict = call_item[0]
            assert cell_id == "cell-no-redis"
            assert "type" in fragment_dict
            assert "content" in fragment_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
