#!/usr/bin/env python3
"""
Unit Tests for Workflow Executor Contract Enforcement

This test suite validates that the WorkflowExecutor properly enforces the
mandatory PipelineItem execution contract for all custom workflows.

Tests cover:
- Enforcement of execute(pipeline_item) function requirement
- Proper error handling when execute() is missing
- Proper error handling when module import fails
- Proper error handling when execute() raises exceptions
- Verification that compliant workflows execute successfully
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime

from app.orchestrator.core.workflow_executor import WorkflowExecutor
from app.models import Cell, NotebookItemType, Agent, CellStatus
from app.core.models import PipelineItem


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager for testing."""
    manager = AsyncMock()
    manager.update_cell_state = AsyncMock()
    manager.extract_outputs_from_state = AsyncMock(return_value={})
    return manager


@pytest.fixture
def workflow_executor(mock_state_manager):
    """Create a WorkflowExecutor instance with mocked dependencies."""
    with patch('app.orchestrator.core.workflow_executor.build_workflow_graph'):
        executor = WorkflowExecutor(mock_state_manager)
        return executor


@pytest.fixture
def mock_cell():
    """Create a mock Cell instance."""
    cell = Mock(spec=Cell)
    cell.id = "test-cell-123"
    cell.notebook_item_type_id = "test-type-456"
    cell.assignee_id = "test-agent-789"
    cell.initial_data = {
        "file_path": "/test/file.md",
        "file_type": "markdown",
        "document_id": "doc-001"
    }
    cell.fragments = []
    cell.created_at = datetime.now()
    cell.updated_at = datetime.now()
    cell.model_dump = Mock(return_value={"id": cell.id, "status": "running"})
    return cell


@pytest.fixture
def mock_cell_type():
    """Create a mock NotebookItemType instance."""
    cell_type = Mock(spec=NotebookItemType)
    cell_type.id = "test-type-456"
    cell_type.name = "test-workflow"
    cell_type.default_refs = {
        "workflow_graph": ["backend/app/workflows/test_workflow.py"]
    }
    cell_type.yaml_refs = []
    cell_type.workflows = {}
    return cell_type


@pytest.fixture
def mock_agent():
    """Create a mock Agent instance."""
    agent = Mock(spec=Agent)
    agent.id = "test-agent-789"
    agent.name = "Test Agent"
    agent.ia_model_id = "mistral"
    agent.agent_type_id = "test-type"
    return agent


@pytest.fixture
def mock_pipeline_item():
    """Create a mock PipelineItem instance."""
    item = Mock(spec=PipelineItem)
    item.id = "pipeline-item-123"
    item.cell_id = "test-cell-123"
    item.status = "pending"
    item.data = {
        "file_path": "/test/file.md",
        "file_type": "markdown",
        "document_id": "doc-001"
    }
    item.fragments = []
    item.error = None
    item.update_status = Mock()
    item.add_fragment = Mock()
    item.model_dump = Mock(return_value={"id": item.id, "status": "completed"})
    return item


class TestWorkflowExecutorContractEnforcement:
    """Test suite for contract enforcement in WorkflowExecutor."""
    
    @pytest.mark.asyncio
    async def test_workflow_missing_execute_function_fails(
        self, 
        workflow_executor, 
        mock_cell, 
        mock_cell_type,
        mock_agent
    ):
        """Test that workflows without execute() function fail with explicit error."""
        
        # Mock database calls
        with patch('app.orchestrator.core.workflow_executor.db') as mock_db:
            mock_db.find_one = AsyncMock(side_effect=[
                mock_cell,       # First call returns cell
                mock_cell_type,  # Second call returns cell type
                mock_agent       # Third call returns agent
            ])
            
            # Mock find_graph_reference to return a workflow path
            with patch('app.orchestrator.core.workflow_executor.find_graph_reference') as mock_find:
                mock_find.return_value = "backend/app/workflows/test_workflow.py"
                
                # Mock importlib to return a module without execute() function
                mock_module = MagicMock(spec=[])  # Empty spec means no attributes
                
                with patch('app.orchestrator.core.workflow_executor.importlib.import_module') as mock_import:
                    mock_import.return_value = mock_module
                    
                    # Mock the helper functions
                    with patch('app.orchestrator.core.workflow_executor.cell_to_pipeline_item') as mock_convert:
                        with patch('app.orchestrator.core.workflow_executor.publish_pipeline_fragments'):
                            mock_pipeline_item = Mock(spec=PipelineItem)
                            mock_pipeline_item.fragments = []
                            mock_pipeline_item.update_status = Mock()
                            mock_convert.return_value = mock_pipeline_item
                            
                            # Execute workflow
                            result = await workflow_executor.execute_cell_workflow("test-cell-123")
                            
                            # Verify failure
                            assert result is False
                            
                            # Verify error state was set with explicit message
                            workflow_executor.state_manager.update_cell_state.assert_called()
                            call_args = workflow_executor.state_manager.update_cell_state.call_args_list[-1]
                            assert call_args[0][0] == "test-cell-123"
                            assert call_args[0][1] == CellStatus.ERROR
                            
                            # Verify error message mentions execute(pipeline_item)
                            error_data = call_args[1]['error_data']
                            assert "execute(pipeline_item)" in error_data
                            assert "INGESTION_EXECUTION_CONTRACT.md" in error_data
    
    @pytest.mark.asyncio
    async def test_workflow_import_error_fails_gracefully(
        self,
        workflow_executor,
        mock_cell,
        mock_cell_type,
        mock_agent
    ):
        """Test that import errors are handled gracefully with clear error messages."""
        
        # Mock database calls
        with patch('app.orchestrator.core.workflow_executor.db') as mock_db:
            mock_db.find_one = AsyncMock(side_effect=[
                mock_cell,
                mock_cell_type,
                mock_agent
            ])
            
            # Mock find_graph_reference
            with patch('app.orchestrator.core.workflow_executor.find_graph_reference') as mock_find:
                mock_find.return_value = "backend/app/workflows/test_workflow.py"
                
                # Mock importlib to raise ImportError
                with patch('app.orchestrator.core.workflow_executor.importlib.import_module') as mock_import:
                    mock_import.side_effect = ImportError("No module named 'missing_dependency'")
                    
                    # Mock helper functions
                    with patch('app.orchestrator.core.workflow_executor.cell_to_pipeline_item') as mock_convert:
                        mock_pipeline_item = Mock(spec=PipelineItem)
                        mock_pipeline_item.fragments = []
                        mock_pipeline_item.update_status = Mock()
                        mock_convert.return_value = mock_pipeline_item
                        
                        # Execute workflow
                        result = await workflow_executor.execute_cell_workflow("test-cell-123")
                        
                        # Verify failure
                        assert result is False
                        
                        # Verify error state was set
                        workflow_executor.state_manager.update_cell_state.assert_called()
                        call_args = workflow_executor.state_manager.update_cell_state.call_args_list[-1]
                        assert call_args[0][1] == CellStatus.ERROR
                        
                        # Verify error message is informative
                        error_data = call_args[1]['error_data']
                        assert "Failed to import" in error_data
                        assert "missing_dependency" in error_data
    
    @pytest.mark.asyncio
    async def test_workflow_execute_exception_fails_gracefully(
        self,
        workflow_executor,
        mock_cell,
        mock_cell_type,
        mock_agent
    ):
        """Test that exceptions during execute() are handled gracefully."""
        
        # Mock database calls
        with patch('app.orchestrator.core.workflow_executor.db') as mock_db:
            mock_db.find_one = AsyncMock(side_effect=[
                mock_cell,
                mock_cell_type,
                mock_agent
            ])
            
            # Mock find_graph_reference
            with patch('app.orchestrator.core.workflow_executor.find_graph_reference') as mock_find:
                mock_find.return_value = "backend/app/workflows/test_workflow.py"
                
                # Mock module with execute() that raises exception
                mock_module = MagicMock()
                mock_module.execute = Mock(side_effect=RuntimeError("Workflow processing failed"))
                
                with patch('app.orchestrator.core.workflow_executor.importlib.import_module') as mock_import:
                    mock_import.return_value = mock_module
                    
                    # Mock helper functions
                    with patch('app.orchestrator.core.workflow_executor.cell_to_pipeline_item') as mock_convert:
                        mock_pipeline_item = Mock(spec=PipelineItem)
                        mock_pipeline_item.fragments = []
                        mock_pipeline_item.update_status = Mock()
                        mock_convert.return_value = mock_pipeline_item
                        
                        # Execute workflow
                        result = await workflow_executor.execute_cell_workflow("test-cell-123")
                        
                        # Verify failure
                        assert result is False
                        
                        # Verify error state was set
                        workflow_executor.state_manager.update_cell_state.assert_called()
                        call_args = workflow_executor.state_manager.update_cell_state.call_args_list[-1]
                        assert call_args[0][1] == CellStatus.ERROR
                        
                        # Verify error message mentions the exception
                        error_data = call_args[1]['error_data']
                        assert "Workflow processing failed" in error_data
    
    @pytest.mark.asyncio
    async def test_compliant_workflow_executes_successfully(
        self,
        workflow_executor,
        mock_cell,
        mock_cell_type,
        mock_agent
    ):
        """Test that compliant workflows with execute() function execute successfully."""
        
        # Mock database calls
        with patch('app.orchestrator.core.workflow_executor.db') as mock_db:
            # Create a properly mocked cell for the final state change
            final_cell = Mock(spec=Cell)
            final_cell.model_dump = Mock(return_value={"id": "test-cell-123", "status": "completed"})
            
            mock_db.find_one = AsyncMock(side_effect=[
                mock_cell,       # Initial cell load
                mock_cell_type,  # Cell type load
                mock_agent,      # Agent load
                final_cell       # Final cell load for state change
            ])
            
            # Mock find_graph_reference
            with patch('app.orchestrator.core.workflow_executor.find_graph_reference') as mock_find:
                mock_find.return_value = "backend/app/workflows/test_workflow.py"
                
                # Create a compliant mock module with execute()
                mock_module = MagicMock()
                result_item = Mock(spec=PipelineItem)
                result_item.error = None  # No error
                result_item.status = "completed"
                result_item.update_status = Mock()
                result_item.model_dump = Mock(return_value={"id": "pipeline-123", "status": "completed"})
                mock_module.execute = Mock(return_value=result_item)
                
                with patch('app.orchestrator.core.workflow_executor.importlib.import_module') as mock_import:
                    mock_import.return_value = mock_module
                    
                    # Mock helper functions
                    with patch('app.orchestrator.core.workflow_executor.cell_to_pipeline_item') as mock_convert:
                        with patch('app.orchestrator.core.workflow_executor.publish_pipeline_fragments'):
                            with patch('app.orchestrator.core.workflow_executor.update_cell_from_pipeline_item') as mock_update:
                                with patch('app.orchestrator.core.workflow_executor.publish_cell_state_changed_sync'):
                                    mock_pipeline_item = Mock(spec=PipelineItem)
                                    mock_pipeline_item.fragments = []
                                    mock_pipeline_item.update_status = Mock()
                                    mock_convert.return_value = mock_pipeline_item
                                    mock_update.return_value = AsyncMock(return_value=True)
                                    
                                    # Execute workflow
                                    result = await workflow_executor.execute_cell_workflow("test-cell-123")
                                    
                                    # Verify success
                                    assert result is True
                                    
                                    # Verify execute() was called with PipelineItem
                                    mock_module.execute.assert_called_once()
                                    call_args = mock_module.execute.call_args
                                    assert call_args[0][0] == mock_pipeline_item
    
    @pytest.mark.asyncio
    async def test_workflow_with_error_result_fails_appropriately(
        self,
        workflow_executor,
        mock_cell,
        mock_cell_type,
        mock_agent
    ):
        """Test that workflows returning PipelineItem with error are handled correctly."""
        
        # Mock database calls
        with patch('app.orchestrator.core.workflow_executor.db') as mock_db:
            mock_db.find_one = AsyncMock(side_effect=[
                mock_cell,
                mock_cell_type,
                mock_agent
            ])
            
            # Mock find_graph_reference
            with patch('app.orchestrator.core.workflow_executor.find_graph_reference') as mock_find:
                mock_find.return_value = "backend/app/workflows/test_workflow.py"
                
                # Create module that returns PipelineItem with error
                mock_module = MagicMock()
                result_item = Mock(spec=PipelineItem)
                result_item.error = "Workflow processing failed"  # Error present
                result_item.status = "error"
                mock_module.execute = Mock(return_value=result_item)
                
                with patch('app.orchestrator.core.workflow_executor.importlib.import_module') as mock_import:
                    mock_import.return_value = mock_module
                    
                    # Mock helper functions
                    with patch('app.orchestrator.core.workflow_executor.cell_to_pipeline_item') as mock_convert:
                        with patch('app.orchestrator.core.workflow_executor.publish_pipeline_fragments'):
                            with patch('app.orchestrator.core.workflow_executor.update_cell_from_pipeline_item') as mock_update:
                                mock_pipeline_item = Mock(spec=PipelineItem)
                                mock_pipeline_item.fragments = []
                                mock_pipeline_item.update_status = Mock()
                                mock_convert.return_value = mock_pipeline_item
                                mock_update.return_value = AsyncMock(return_value=True)
                                
                                # Execute workflow
                                result = await workflow_executor.execute_cell_workflow("test-cell-123")
                                
                                # Verify failure
                                assert result is False
                                
                                # Verify error state was set
                                workflow_executor.state_manager.update_cell_state.assert_called()
                                call_args = workflow_executor.state_manager.update_cell_state.call_args_list[-1]
                                assert call_args[0][1] == CellStatus.ERROR
                                assert "Workflow processing failed" in call_args[1]['error_data']


class TestNoLegacyFallback:
    """Test suite to verify that legacy fallback has been completely removed."""
    
    def test_no_execute_langgraph_custom_graph_method(self):
        """Verify that _execute_langgraph_custom_graph method does not exist."""
        with patch('app.orchestrator.core.workflow_executor.build_workflow_graph'):
            executor = WorkflowExecutor(AsyncMock())
            
            # Verify method does not exist
            assert not hasattr(executor, '_execute_langgraph_custom_graph')
    
    def test_no_load_custom_graph_import(self):
        """Verify that load_custom_graph is not imported in workflow_executor."""
        import app.orchestrator.core.workflow_executor as module
        
        # Verify load_custom_graph is not in the module's namespace
        # (it should not be imported since it's no longer used)
        # Note: This test checks the import statement, not the function existence
        # in app.workflow_executor module
        assert 'load_custom_graph' not in dir(module)
