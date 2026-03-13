"""
Unit tests for Redis Explorer Service.

Tests hierarchical key scanning, value inspection, and deletion operations.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from app.services.redis_explorer_service import RedisExplorerService


class TestRedisExplorerService:
    """Test suite for Redis Explorer Service."""
    
    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        client = AsyncMock()
        
        # Mock SCAN command
        client.scan = AsyncMock()
        
        # Mock key operations
        client.exists = AsyncMock(return_value=1)
        client.type = AsyncMock(return_value=b"string")
        client.ttl = AsyncMock(return_value=-1)
        client.get = AsyncMock(return_value='{"test": "value"}')
        client.hgetall = AsyncMock(return_value={})
        client.lrange = AsyncMock(return_value=[])
        client.smembers = AsyncMock(return_value=set())
        client.zrange = AsyncMock(return_value=[])
        client.memory_usage = AsyncMock(return_value=100)
        
        # Mock pipeline
        pipeline_mock = MagicMock()
        pipeline_mock.delete = MagicMock(return_value=pipeline_mock)
        pipeline_mock.execute = AsyncMock(return_value=[1])
        client.pipeline = MagicMock(return_value=pipeline_mock)
        
        # Mock info and dbsize
        client.info = AsyncMock(return_value={
            "redis_version": "7.0.0",
            "used_memory_human": "1.5M",
            "used_memory": 1572864,
            "connected_clients": 5,
            "uptime_in_seconds": 3600,
            "role": "master"
        })
        client.dbsize = AsyncMock(return_value=42)
        
        # Mock FLUSHDB
        client.flushdb = AsyncMock()
        
        return client
    
    @pytest.fixture
    async def service(self, mock_redis_client):
        """Create a Redis Explorer Service with mocked Redis."""
        service = RedisExplorerService()
        service.redis = mock_redis_client
        return service
    
    # ========================================================================
    # Hierarchical Key Scanning Tests
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_scan_keys_root_level(self, service, mock_redis_client):
        """Test scanning keys at root level."""
        # Mock SCAN returning top-level prefixes
        mock_redis_client.scan.side_effect = [
            (0, [b"aider:session:123", b"ollama:job:456", b"sd:gen:789"])
        ]
        
        result = await service.scan_keys_by_prefix(prefix="", max_depth=1)
        
        assert result["prefix"] == ""
        assert "aider" in result["nodes"]
        assert "ollama" in result["nodes"]
        assert "sd" in result["nodes"]
        assert len(result["keys"]) == 0  # No final keys at root with depth=1
    
    @pytest.mark.asyncio
    async def test_scan_keys_with_prefix(self, service, mock_redis_client):
        """Test scanning keys with specific prefix."""
        # Mock SCAN returning keys under "aider:session"
        mock_redis_client.scan.side_effect = [
            (0, [
                b"aider:session:123:data",
                b"aider:session:456:data",
                b"aider:session:123:config"
            ])
        ]
        
        result = await service.scan_keys_by_prefix(
            prefix="aider:session",
            max_depth=1
        )
        
        assert result["prefix"] == "aider:session"
        assert "123" in result["nodes"]
        assert "456" in result["nodes"]
    
    @pytest.mark.asyncio
    async def test_scan_keys_pagination(self, service, mock_redis_client):
        """Test SCAN pagination with cursor."""
        # Mock SCAN returning data in multiple iterations
        mock_redis_client.scan.side_effect = [
            (100, [b"key1", b"key2"]),
            (200, [b"key3", b"key4"]),
            (0, [b"key5"])  # cursor=0 means end
        ]
        
        result = await service.scan_keys_by_prefix(prefix="test")
        
        assert result["total_scanned"] == 5
        assert mock_redis_client.scan.call_count == 3
    
    @pytest.mark.asyncio
    async def test_scan_keys_with_custom_delimiter(self, service, mock_redis_client):
        """Test scanning with custom delimiter."""
        mock_redis_client.scan.side_effect = [
            (0, [b"test/path/file1", b"test/path/file2"])
        ]
        
        result = await service.scan_keys_by_prefix(
            prefix="test",
            delimiter="/",
            max_depth=1
        )
        
        assert result["delimiter"] == "/"
        assert "path" in result["nodes"]
    
    @pytest.mark.asyncio
    async def test_scan_keys_error_handling(self, service, mock_redis_client):
        """Test error handling during key scanning."""
        mock_redis_client.scan.side_effect = Exception("Redis connection failed")
        
        with pytest.raises(Exception) as exc_info:
            await service.scan_keys_by_prefix(prefix="test")
        
        assert "Failed to scan Redis keys" in str(exc_info.value)
    
    # ========================================================================
    # Key Value Inspection Tests
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_get_key_value_string(self, service, mock_redis_client):
        """Test getting string value with JSON parsing."""
        test_data = {"user": "test", "value": 123}
        mock_redis_client.get.return_value = json.dumps(test_data)
        mock_redis_client.type.return_value = b"string"
        
        result = await service.get_key_value("test:key")
        
        assert result["key"] == "test:key"
        assert result["type"] == "string"
        assert result["value"] == test_data
        assert result["ttl"] == -1
        assert result["size"] == 100
    
    @pytest.mark.asyncio
    async def test_get_key_value_non_json_string(self, service, mock_redis_client):
        """Test getting non-JSON string value."""
        mock_redis_client.get.return_value = "plain text"
        mock_redis_client.type.return_value = b"string"
        
        result = await service.get_key_value("test:key")
        
        assert result["value"] == "plain text"
    
    @pytest.mark.asyncio
    async def test_get_key_value_hash(self, service, mock_redis_client):
        """Test getting hash value."""
        hash_data = {"field1": "value1", "field2": "value2"}
        mock_redis_client.hgetall.return_value = hash_data
        mock_redis_client.type.return_value = b"hash"
        
        result = await service.get_key_value("test:hash")
        
        assert result["type"] == "hash"
        assert result["value"] == hash_data
    
    @pytest.mark.asyncio
    async def test_get_key_value_list(self, service, mock_redis_client):
        """Test getting list value."""
        list_data = ["item1", "item2", "item3"]
        mock_redis_client.lrange.return_value = list_data
        mock_redis_client.type.return_value = b"list"
        
        result = await service.get_key_value("test:list")
        
        assert result["type"] == "list"
        assert result["value"] == list_data
    
    @pytest.mark.asyncio
    async def test_get_key_value_set(self, service, mock_redis_client):
        """Test getting set value."""
        set_data = {"a", "b", "c"}
        mock_redis_client.smembers.return_value = set_data
        mock_redis_client.type.return_value = b"set"
        
        result = await service.get_key_value("test:set")
        
        assert result["type"] == "set"
        assert len(result["value"]) == 3
    
    @pytest.mark.asyncio
    async def test_get_key_value_with_ttl(self, service, mock_redis_client):
        """Test getting key with TTL."""
        mock_redis_client.ttl.return_value = 3600  # 1 hour
        
        result = await service.get_key_value("test:key")
        
        assert result["ttl"] == 3600
    
    @pytest.mark.asyncio
    async def test_get_key_value_nonexistent(self, service, mock_redis_client):
        """Test getting non-existent key."""
        mock_redis_client.exists.return_value = 0
        
        with pytest.raises(Exception) as exc_info:
            await service.get_key_value("nonexistent:key")
        
        assert "does not exist" in str(exc_info.value)
    
    # ========================================================================
    # Key Deletion Tests
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_delete_keys_dry_run(self, service, mock_redis_client):
        """Test dry run deletion (preview only)."""
        mock_redis_client.scan.side_effect = [
            (0, [b"test:1", b"test:2", b"test:3"])
        ]
        
        result = await service.delete_keys_by_prefix(
            prefix="test:",
            dry_run=True
        )
        
        assert result["dry_run"] is True
        assert result["keys_found"] == 3
        assert result["keys_deleted"] == 0
        assert len(result["sample_keys"]) == 3
        # Verify pipeline was not executed
        mock_redis_client.pipeline.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_keys_actual(self, service, mock_redis_client):
        """Test actual key deletion."""
        mock_redis_client.scan.side_effect = [
            (0, [b"test:1", b"test:2", b"test:3"])
        ]
        
        result = await service.delete_keys_by_prefix(
            prefix="test:",
            dry_run=False
        )
        
        assert result["dry_run"] is False
        assert result["keys_found"] == 3
        assert result["keys_deleted"] == 3
        # Verify pipeline was used
        mock_redis_client.pipeline.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_keys_no_matches(self, service, mock_redis_client):
        """Test deletion when no keys match."""
        mock_redis_client.scan.side_effect = [(0, [])]
        
        result = await service.delete_keys_by_prefix(
            prefix="nonexistent:",
            dry_run=False
        )
        
        assert result["keys_found"] == 0
        assert result["keys_deleted"] == 0
    
    @pytest.mark.asyncio
    async def test_delete_keys_sample_limit(self, service, mock_redis_client):
        """Test sample keys are limited to 10."""
        # Create 20 keys
        keys = [f"test:{i}".encode() for i in range(20)]
        mock_redis_client.scan.side_effect = [(0, keys)]
        
        result = await service.delete_keys_by_prefix(
            prefix="test:",
            dry_run=True
        )
        
        assert result["keys_found"] == 20
        assert len(result["sample_keys"]) == 10  # Limited to 10
    
    # ========================================================================
    # Redis Info Tests
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_get_redis_info(self, service, mock_redis_client):
        """Test getting Redis server information."""
        result = await service.get_redis_info()
        
        assert result["version"] == "7.0.0"
        assert result["used_memory"] == "1.5M"
        assert result["total_keys"] == 42
        assert result["connected_clients"] == 5
        assert result["uptime_seconds"] == 3600
        assert result["role"] == "master"
    
    @pytest.mark.asyncio
    async def test_get_redis_info_error(self, service, mock_redis_client):
        """Test error handling when getting Redis info."""
        mock_redis_client.info.side_effect = Exception("Connection timeout")
        
        with pytest.raises(Exception) as exc_info:
            await service.get_redis_info()
        
        assert "Failed to get Redis info" in str(exc_info.value)
    
    # ========================================================================
    # Redis Connection Tests
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_ensure_redis_not_available(self):
        """Test behavior when Redis is not available."""
        service = RedisExplorerService()
        # Don't initialize Redis client
        
        with patch('app.services.redis_explorer_service.get_redis_client', return_value=None):
            with pytest.raises(Exception) as exc_info:
                await service._ensure_redis()
            
            assert "Redis is not available" in str(exc_info.value)
