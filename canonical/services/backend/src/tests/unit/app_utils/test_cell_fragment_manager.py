#!/usr/bin/env python3
"""
Unit tests for CellFragmentManager

Tests the fragment management utilities for cells, including:
- Adding memory fragments
- Adding result fragments
- Updating status with fragments
- Generic fragment addition
- Error handling and edge cases
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.utils.cell_fragment_manager import (
    CellFragmentManager,
    get_cell_fragment_manager
)


class TestCellFragmentManager:
    """Test suite for CellFragmentManager."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database instance."""
        mock = MagicMock()
        mock.update = AsyncMock(return_value=True)
        return mock
    
    @pytest.fixture
    def manager(self, mock_db):
        """Create a CellFragmentManager with mocked database."""
        manager = CellFragmentManager()
        manager.db = mock_db
        return manager
    
    @pytest.mark.asyncio
    async def test_add_memory_fragment_success(self, manager, mock_db):
        """Test successful addition of memory fragment."""
        cell_id = "test_cell_123"
        content = {"key": "value", "status": "processed"}
        metadata = {"source": "test", "workflow": "ingestion"}
        
        result = await manager.add_memory_fragment(
            cell_id=cell_id,
            content=content,
            metadata=metadata
        )
        
        assert result is True
        mock_db.update.assert_called_once()
        
        # Verify call arguments
        call_args = mock_db.update.call_args
        assert call_args.kwargs["collection"] == "celulas"
        assert call_args.kwargs["doc_id"] == cell_id
        
        # Verify fragment structure in $push operation
        updates = call_args.kwargs["updates"]
        assert "$push" in updates
        assert "fragmentos" in updates["$push"]
        
        fragment = updates["$push"]["fragmentos"]
        assert fragment["tipo"] == "memoria"
        assert fragment["conteudo"] == content
        assert fragment["metadata"] == metadata
        assert "timestamp" in fragment
    
    @pytest.mark.asyncio
    async def test_add_memory_fragment_without_metadata(self, manager, mock_db):
        """Test adding memory fragment without metadata."""
        cell_id = "test_cell_456"
        content = "Simple text content"
        
        result = await manager.add_memory_fragment(
            cell_id=cell_id,
            content=content
        )
        
        assert result is True
        
        # Verify fragment doesn't have metadata field
        call_args = mock_db.update.call_args
        fragment = call_args.kwargs["updates"]["$push"]["fragmentos"]
        assert "metadata" not in fragment
        assert fragment["conteudo"] == content
    
    @pytest.mark.asyncio
    async def test_add_result_fragment_success(self, manager, mock_db):
        """Test successful addition of result fragment."""
        cell_id = "test_cell_result"
        content = "Operation completed successfully"
        result_data = {"chunks_created": 42, "duration_ms": 1234}
        metadata = {"step": "preprocess"}
        
        result = await manager.add_result_fragment(
            cell_id=cell_id,
            content=content,
            result=result_data,
            metadata=metadata
        )
        
        assert result is True
        
        # Verify fragment structure
        call_args = mock_db.update.call_args
        fragment = call_args.kwargs["updates"]["$push"]["fragmentos"]
        assert fragment["tipo"] == "execucao"
        assert fragment["conteudo"] == content
        assert fragment["resultado"] == result_data
        assert fragment["metadata"] == metadata
    
    @pytest.mark.asyncio
    async def test_update_status_with_fragment_to_running(self, manager, mock_db):
        """Test updating status to running with fragment."""
        cell_id = "test_cell_status"
        new_status = "running"
        fragment_content = "Workflow started"
        metadata = {"workflow": "ingestion"}
        
        result = await manager.update_status_with_fragment(
            cell_id=cell_id,
            new_status=new_status,
            fragment_content=fragment_content,
            metadata=metadata
        )
        
        assert result is True
        
        # Verify combined update operation
        call_args = mock_db.update.call_args
        updates = call_args.kwargs["updates"]
        
        # Check status update
        assert "$set" in updates
        assert updates["$set"]["status"] == new_status
        assert "updated_at" in updates["$set"]
        
        # Check fragment creation
        assert "$push" in updates
        fragment = updates["$push"]["fragmentos"]
        assert fragment["tipo"] == "execucao"
        assert fragment["conteudo"] == fragment_content
        assert fragment["metadata"]["status_update"] == new_status
    
    @pytest.mark.asyncio
    async def test_update_status_with_fragment_to_error(self, manager, mock_db):
        """Test updating status to error with error message."""
        cell_id = "test_cell_error"
        new_status = "error"
        fragment_content = "Processing failed"
        error_message = "File not found: /path/to/file"
        
        result = await manager.update_status_with_fragment(
            cell_id=cell_id,
            new_status=new_status,
            fragment_content=fragment_content,
            error_message=error_message
        )
        
        assert result is True
        
        # Verify error message is included in update
        call_args = mock_db.update.call_args
        updates = call_args.kwargs["updates"]
        assert updates["$set"]["error"] == error_message
    
    @pytest.mark.asyncio
    async def test_get_cell_fragment_manager_singleton(self):
        """Test singleton pattern for get_cell_fragment_manager."""
        manager1 = get_cell_fragment_manager()
        manager2 = get_cell_fragment_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, CellFragmentManager)
