#!/usr/bin/env python3
"""
Integration tests for ingestion workflow fragment tracking.

Tests the complete flow of fragment tracking through the LangGraph nodes
when a PipelineItem is provided in the IngestionState.

These tests validate Issue #1041 implementation: complete fragment tracking
in the ingestion workflow.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from app.core.models import PipelineItem, NotebookItem
from app.workflows.ingestion.ingestion_node_types import (
    IngestionState,
    initialize_ingestion,
    resolve_file_path,
    finalize_ingestion
)


class TestIngestionFragmentTracking:
    """Integration tests for fragment tracking in ingestion workflow."""
    
    @pytest.fixture
    def notebook_item(self):
        """Create a test NotebookItem (Cell)."""
        return NotebookItem(
            assignee_id="test-agent-123",
            refs={"workflow_graph": ["backend/app/workflows/ingestion_graph.py"]},
            initial_data={
                "file_path": "/tmp/test_document.md",
                "file_type": "markdown",
                "document_id": "test-doc-456"
            }
        )
    
    @pytest.fixture
    def pipeline_item(self, notebook_item):
        """Create a test PipelineItem for execution tracking."""
        return PipelineItem(
            notebook_item_id=notebook_item.id,
            notebook_item_data=notebook_item,
            cell_id=notebook_item.id,
            cell_type_id="ingestion-issue",
            assignee_id=notebook_item.assignee_id,
            data={
                "file_path": "/tmp/test_document.md",
                "file_type": "markdown",
                "document_id": "test-doc-456"
            }
        )
    
    @pytest.fixture
    def initial_state(self, pipeline_item):
        """Create initial IngestionState with PipelineItem."""
        state: IngestionState = {
            "cell_id": pipeline_item.cell_id,
            "cell_data": pipeline_item.data,
            "agent_data": {"ia_model_id": "mistral"},
            "file_path": "",
            "file_type": "",
            "document_id": "",
            "local_file_path": None,
            "chunks_path": None,
            "doc_chunks_path": None,
            "code_chunks_path": None,
            "embedding_status": None,
            "fragments": [],
            "context": {},
            "error": None,
            "completed": False,
            "pipeline_item": pipeline_item
        }
        return state
    
    def test_initialize_ingestion_updates_status_to_running(self, initial_state, pipeline_item):
        """Test that initialize_ingestion updates cell status to 'running'."""
        # Initially status is pending
        assert pipeline_item.status == "pending"
        assert len(pipeline_item.fragments) == 0
        
        # Execute node
        result_state = initialize_ingestion(initial_state)
        
        # Verify status was updated
        assert pipeline_item.status == "running"
        
        # Verify fragment was added to PipelineItem
        assert len(pipeline_item.fragments) > 0
        assert isinstance(pipeline_item.fragments[0], dict)
        assert pipeline_item.fragments[0]["type"] == "execution"
        assert "initialized" in pipeline_item.fragments[0]["content"].lower()
        
        # Verify metadata includes step information
        metadata = pipeline_item.fragments[0]["metadata"]
        assert metadata["step"] == "initialize"
        assert metadata["workflow"] == "ingestion"
        assert "file_path" in metadata
        assert "file_type" in metadata
    
    def test_initialize_ingestion_also_adds_state_fragment(self, initial_state):
        """Test backward compatibility: fragments still added to state."""
        result_state = initialize_ingestion(initial_state)
        
        # Verify state fragments (backward compatibility)
        assert len(result_state["fragments"]) > 0
        assert result_state["fragments"][0]["tipo"] == "execucao"
    
    def test_resolve_file_path_local_adds_fragment(self, initial_state, pipeline_item):
        """Test that resolve_file_path adds fragment for local paths."""
        # Initialize first
        state = initialize_ingestion(initial_state)
        
        # Clear fragments to isolate this test
        initial_fragment_count = len(pipeline_item.fragments)
        
        # Execute resolve node
        result_state = resolve_file_path(state)
        
        # Verify new fragment was added
        assert len(pipeline_item.fragments) > initial_fragment_count
        
        # Find the resolve fragment
        resolve_fragment = None
        for frag in pipeline_item.fragments[initial_fragment_count:]:
            if "metadata" in frag and frag["metadata"].get("step") == "resolve_file_path":
                resolve_fragment = frag
                break
        
        assert resolve_fragment is not None
        assert "local" in resolve_fragment["content"].lower() or "path" in resolve_fragment["content"].lower()
    
    @patch('app.workflows.ingestion.ingestion_workflow_utils.is_url', return_value=True)
    @patch('app.workflows.ingestion.ingestion_workflow_utils.download_from_url', side_effect=Exception("Network error"))
    def test_resolve_file_path_error_updates_status(self, mock_download, mock_is_url, initial_state, pipeline_item):
        """Test that errors in resolve_file_path update status to error."""
        # Initialize first
        state = initialize_ingestion(initial_state)
        
        # Modify state to use a URL
        state["file_path"] = "https://example.com/document.md"
        
        # Execute resolve node (will fail)
        result_state = resolve_file_path(state)
        
        # Verify status was updated to error
        assert pipeline_item.status == "error"
        assert pipeline_item.error is not None
        assert "Network error" in pipeline_item.error or "download" in pipeline_item.error.lower()
    
    def test_finalize_ingestion_updates_status_to_completed(self, initial_state, pipeline_item):
        """Test that finalize_ingestion updates cell status to 'completed'."""
        # Initialize and set required state
        state = initialize_ingestion(initial_state)
        state["local_file_path"] = "/tmp/test_document.md"
        state["doc_chunks_path"] = "/tmp/doc_chunks.json"
        state["embedding_status"] = "Success"
        
        # Execute finalize node
        result_state = finalize_ingestion(state)
        
        # Verify status was updated
        assert pipeline_item.status == "completed"
        
        # Verify summary fragment was added
        finalize_fragments = [
            f for f in pipeline_item.fragments
            if isinstance(f, dict) and f.get("metadata", {}).get("step") == "finalize"
        ]
        assert len(finalize_fragments) > 0
        
        # Verify summary includes result data
        summary_fragment = finalize_fragments[0]
        assert summary_fragment["type"] == "memory"
        assert "result" in summary_fragment
        assert summary_fragment["result"]["document_id"] == "test-doc-456"
    
    def test_workflow_without_pipeline_item_still_works(self):
        """Test backward compatibility: workflow works without PipelineItem."""
        # Create state WITHOUT pipeline_item
        state: IngestionState = {
            "cell_id": "test-cell-123",
            "cell_data": {
                "file_path": "/tmp/test.md",
                "file_type": "markdown",
                "document_id": "test-doc"
            },
            "agent_data": {"ia_model_id": "mistral"},
            "file_path": "",
            "file_type": "",
            "document_id": "",
            "local_file_path": None,
            "chunks_path": None,
            "doc_chunks_path": None,
            "code_chunks_path": None,
            "embedding_status": None,
            "fragments": [],
            "context": {},
            "error": None,
            "completed": False,
            "pipeline_item": None  # Explicitly None
        }
        
        # Execute nodes - should work without errors
        state = initialize_ingestion(state)
        assert state["file_path"] == "/tmp/test.md"
        assert len(state["fragments"]) > 0
        
        state = resolve_file_path(state)
        assert state["local_file_path"] is not None
        
        # No PipelineItem means no persistent fragments, but state fragments should exist
        assert len(state["fragments"]) >= 2
    
    def test_fragment_chronological_order(self, initial_state, pipeline_item):
        """Test that fragments are added in chronological order."""
        # Execute multiple nodes
        state = initialize_ingestion(initial_state)
        state = resolve_file_path(state)
        state["embedding_status"] = "Success"
        state = finalize_ingestion(state)
        
        # Verify we have multiple fragments
        assert len(pipeline_item.fragments) >= 3
        
        # Verify timestamps are in chronological order
        timestamps = []
        for f in pipeline_item.fragments:
            if isinstance(f, dict):
                # Check both Fragment model format and dict format
                if "timestamp" in f and isinstance(f["timestamp"], str):
                    timestamps.append(f["timestamp"])
                elif "timestamp" in f and hasattr(f["timestamp"], 'isoformat'):
                    timestamps.append(f["timestamp"].isoformat())
        
        # Parse timestamps and verify they're increasing
        parsed_timestamps = [datetime.fromisoformat(ts) for ts in timestamps if ts]
        assert len(parsed_timestamps) >= 2, "Should have at least 2 timestamps"
        
        for i in range(len(parsed_timestamps) - 1):
            assert parsed_timestamps[i] <= parsed_timestamps[i + 1], \
                "Fragments should be in chronological order"
    
    def test_fragment_metadata_structure(self, initial_state, pipeline_item):
        """Test that all fragments have proper metadata structure."""
        # Execute workflow
        state = initialize_ingestion(initial_state)
        state = resolve_file_path(state)
        
        # Check all PipelineItem fragments
        for fragment in pipeline_item.fragments:
            assert isinstance(fragment, dict)
            assert "type" in fragment
            assert "content" in fragment
            assert "timestamp" in fragment
            
            # All workflow fragments should have metadata with 'step' and 'workflow'
            if fragment.get("metadata"):
                assert "step" in fragment["metadata"]
                assert fragment["metadata"].get("workflow") == "ingestion"
