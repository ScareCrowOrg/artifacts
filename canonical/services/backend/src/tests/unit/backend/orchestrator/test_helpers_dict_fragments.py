"""
Unit tests for dict fragment handling in orchestrator helpers.

This test module specifically validates the fix for issue #1066 where
fragments stored as dicts in PipelineItem were causing AttributeError
when publish_fragment_to_redis tried to call model_dump() on them.

Tests ensure:
- Dict fragments are properly serialized
- String fragments are properly handled
- Mixed fragment types work correctly
- Redis and event bus publishing work with dict fragments

Ensures 90% test coverage as per RULESET.md Rule 3.1.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from app.orchestrator.helpers import (
    publish_fragment_to_redis,
    publish_pipeline_fragments,
    set_redis_client
)
from app.core.models import PipelineItem, NotebookItem


# Test Fixtures

@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    client = Mock()
    client.publish = Mock()
    return client


@pytest.fixture
def sample_dict_fragment():
    """Sample dict fragment as stored in PipelineItem."""
    return {
        "id": "frag-dict-123",
        "type": "execucao",
        "content": "Test dict fragment",
        "result": "success",
        "metadata": {"step": "test"},
        "timestamp": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_pipeline_item_with_dicts():
    """Sample PipelineItem with dict fragments (as actually stored)."""
    # Create a real NotebookItem for composition
    notebook_item = NotebookItem(
        assignee_id="user-123"
    )
    
    # Create PipelineItem with dict fragments
    item = PipelineItem(
        notebook_item_id="nb-456",
        notebook_item_data=notebook_item,
        cell_id="cell-dict-test",
        cell_type_id="test-type",
        assignee_id="user-123"
    )
    
    # Add fragments as dicts (this is how add_fragment() stores them)
    item.fragments = [
        {
            "id": f"frag-{i}",
            "type": "execucao",
            "content": f"Dict fragment {i}",
            "result": None,
            "metadata": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        for i in range(3)
    ]
    
    return item


# Tests for dict fragment handling

def test_publish_dict_fragment_to_redis(mock_redis_client, sample_dict_fragment):
    """Test that dict fragments are properly published to Redis."""
    # Setup
    set_redis_client(mock_redis_client)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute
        publish_fragment_to_redis("cell-123", sample_dict_fragment)
        
        # Verify Redis publish was called
        assert mock_redis_client.publish.called
        call_args = mock_redis_client.publish.call_args
        
        # Verify channel format
        assert call_args[0][0] == "cell:cell-123:fragmentos"
        
        # Verify message is JSON string
        message = call_args[0][1]
        assert isinstance(message, str)
        assert "frag-dict-123" in message
        assert "execucao" in message
        
        # Verify event bus was called with dict
        mock_event_bus.assert_called_once()
        event_bus_call = mock_event_bus.call_args
        assert event_bus_call[0][0] == "cell-123"
        assert event_bus_call[0][1] == sample_dict_fragment


def test_publish_string_fragment_to_redis(mock_redis_client):
    """Test that string fragments are properly handled."""
    # Setup
    set_redis_client(mock_redis_client)
    fragment_str = "Simple string fragment"
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute
        publish_fragment_to_redis("cell-456", fragment_str)
        
        # Verify event bus received converted dict
        event_bus_call = mock_event_bus.call_args
        fragment_dict = event_bus_call[0][1]
        
        assert fragment_dict["content"] == fragment_str
        assert fragment_dict["type"] == "info"
        
        # Verify Redis received JSON
        assert mock_redis_client.publish.called
        message = mock_redis_client.publish.call_args[0][1]
        assert fragment_str in message


def test_publish_dict_fragment_without_redis(sample_dict_fragment):
    """Test dict fragment publishing when Redis is disabled."""
    # Setup - disable Redis
    set_redis_client(None)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute
        publish_fragment_to_redis("cell-789", sample_dict_fragment)
        
        # Verify event bus was called
        mock_event_bus.assert_called_once()
        event_bus_call = mock_event_bus.call_args
        
        assert event_bus_call[0][0] == "cell-789"
        assert event_bus_call[0][1] == sample_dict_fragment


def test_publish_pipeline_fragments_with_dicts(sample_pipeline_item_with_dicts):
    """Test publishing PipelineItem fragments that are stored as dicts."""
    # Setup
    set_redis_client(None)
    
    with patch('app.orchestrator.helpers.publish_fragment_to_redis') as mock_publish:
        # Execute
        publish_pipeline_fragments(sample_pipeline_item_with_dicts)
        
        # Verify publish was called for each dict fragment
        assert mock_publish.call_count == 3
        
        # Verify each call received a dict
        for call_item in mock_publish.call_args_list:
            cell_id = call_item[0][0]
            fragment = call_item[0][1]
            
            assert cell_id == "cell-dict-test"
            assert isinstance(fragment, dict)
            assert "id" in fragment
            assert "type" in fragment
            assert "content" in fragment


def test_publish_pipeline_fragments_mixed_types():
    """Test publishing PipelineItem with mixed fragment types."""
    # Create a real NotebookItem
    notebook_item = NotebookItem(assignee_id="user-123")
    
    # Create PipelineItem
    item = PipelineItem(
        notebook_item_id="nb-mixed",
        notebook_item_data=notebook_item,
        cell_id="cell-mixed",
        cell_type_id="test-type",
        assignee_id="user-123"
    )
    
    # Add mixed fragment types
    item.fragments = [
        {"id": "f1", "type": "execucao", "content": "Dict fragment"},
        "Simple string fragment",
        {
            "id": "f2",
            "type": "memoria",
            "content": "Another dict",
            "timestamp": datetime.utcnow().isoformat()
        }
    ]
    
    set_redis_client(None)
    
    with patch('app.orchestrator.helpers.publish_fragment_to_redis') as mock_publish:
        # Execute
        publish_pipeline_fragments(item)
        
        # Verify all fragments were published
        assert mock_publish.call_count == 3
        
        # Verify types are preserved
        fragments_published = [call[0][1] for call in mock_publish.call_args_list]
        assert isinstance(fragments_published[0], dict)  # dict fragment
        assert isinstance(fragments_published[1], str)   # string fragment
        assert isinstance(fragments_published[2], dict)  # dict fragment


def test_dict_fragment_with_nested_data(mock_redis_client):
    """Test dict fragments with complex nested data structures."""
    # Setup
    set_redis_client(mock_redis_client)
    
    complex_fragment = {
        "id": "complex-123",
        "type": "execucao",
        "content": "Complex fragment",
        "result": {
            "chunks_created": 42,
            "nested": {
                "data": [1, 2, 3],
                "metadata": {"key": "value"}
            }
        },
        "metadata": {
            "workflow": "ingestion",
            "step": "preprocess"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute - should not raise
        publish_fragment_to_redis("cell-complex", complex_fragment)
        
        # Verify it was published
        assert mock_event_bus.called
        assert mock_redis_client.publish.called
        
        # Verify JSON serialization worked
        message = mock_redis_client.publish.call_args[0][1]
        assert isinstance(message, str)
        assert "complex-123" in message
        assert "chunks_created" in message


def test_get_fragments_since_returns_dicts():
    """Test that get_fragments_since returns dicts as expected."""
    # Create a real PipelineItem
    notebook_item = NotebookItem(assignee_id="user-123")
    item = PipelineItem(
        notebook_item_id="nb-test",
        notebook_item_data=notebook_item,
        cell_id="cell-test",
        cell_type_id="test-type",
        assignee_id="user-123"
    )
    
    # Add fragments
    item.fragments = [
        {"id": "f1", "type": "info", "content": "Fragment 1"},
        {"id": "f2", "type": "info", "content": "Fragment 2"},
        {"id": "f3", "type": "info", "content": "Fragment 3"}
    ]
    
    # Test get_fragments_since
    fragments = item.get_fragments_since("f1")
    
    # Verify it returns dicts
    assert len(fragments) == 2
    assert all(isinstance(f, dict) for f in fragments)
    assert fragments[0]["id"] == "f2"
    assert fragments[1]["id"] == "f3"


def test_publish_dict_fragment_handles_redis_error(mock_redis_client, sample_dict_fragment):
    """Test that Redis errors don't prevent dict fragment processing."""
    # Setup Redis to raise error
    mock_redis_client.publish.side_effect = Exception("Redis connection error")
    set_redis_client(mock_redis_client)
    
    with patch('app.orchestrator.helpers.publish_fragment_added_sync') as mock_event_bus:
        # Execute - should not raise
        publish_fragment_to_redis("cell-error", sample_dict_fragment)
        
        # Verify event bus was still called despite Redis error
        mock_event_bus.assert_called_once()
        assert mock_event_bus.call_args[0][1] == sample_dict_fragment


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
