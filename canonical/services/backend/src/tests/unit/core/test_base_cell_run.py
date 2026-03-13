"""
Unit tests for BaseCell.run() method.

Tests the atomic execution lifecycle: setup → execute → save
with fragment tracing, error handling, and output passing.

Coverage target: >90% for BaseCell.run() method
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any
import sys
import os

# Add path to backend for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.core.base_cell import (
    BaseCell, CellResult, CellMetadata, ValidationError,
    EnvironmentConfig, HealthCheckResult, HealthStatus
)


# ============ TEST CELL IMPLEMENTATION ============


class TestCell(BaseCell):
    """Test cell implementation for run() testing"""
    
    def __init__(self):
        self.setup_called = False
        self.execute_call_count = 0
        self.output_store = {}
        self.should_fail = False
        self.fail_at_step = None
    
    async def execute(self, input: Dict[str, Any]) -> CellResult:
        """Execute test logic"""
        self.execute_call_count += 1
        
        if self.should_fail and self.fail_at_step == 'execute':
            raise RuntimeError("Execute failed as requested")
        
        # Simulate processing
        result_value = input.get('value', 0) * 2
        self.output_store = {'result': result_value}
        
        return CellResult(
            success=True,
            output=self.output_store,
            execution_time=0.001
        )
    
    async def describe(self) -> CellMetadata:
        """Describe test cell"""
        return CellMetadata(
            id='test-cell',
            name='Test Cell',
            version='1.0.0',
            description='Cell for testing run() method',
            inputs={'value': 'number'},
            outputs={'result': 'number'},
            tags=['test']
        )
    
    def validate(self, input: Dict[str, Any]) -> list:
        """Validate input"""
        errors = []
        if 'value' not in input:
            errors.append(ValidationError('value', 'Required'))
        return errors
    
    async def setup(self, config: EnvironmentConfig) -> None:
        """Setup test cell"""
        self.setup_called = True
        if self.should_fail and self.fail_at_step == 'setup':
            raise RuntimeError("Setup failed as requested")


# ============ FIXTURES ============


@pytest.fixture
def test_cell():
    """Create test cell instance"""
    return TestCell()


@pytest.fixture
def basic_lifecycle():
    """Basic lifecycle configuration"""
    return {
        'execute': {
            'action': 'process',
            'params': {'value': 5}
        }
    }


@pytest.fixture
def full_lifecycle():
    """Full lifecycle with all steps"""
    return {
        'setup': {
            'has_gpu': False,
            'gpu_vram_mb': 0,
            'cpu_cores': 4,
            'headless_mode': True,
            'timeout_seconds': 300
        },
        'execute': [
            {'action': 'process', 'params': {'value': 5}},
            {'action': 'transform', 'params': {'value': 10}}
        ],
        'save': True
    }


# ============ TESTS ============


@pytest.mark.asyncio
async def test_run_basic_execution(test_cell, basic_lifecycle):
    """Test basic run() with single execute action"""
    result = await test_cell.run(basic_lifecycle)
    
    assert result['id'] == 'test-cell'
    assert result['status'] == 'completed'
    assert result['success'] is True
    assert 'output' in result
    assert 'fragments' in result
    assert result['execution_time'] > 0
    
    # Check fragments
    fragments = result['fragments']
    assert len(fragments) >= 2  # execute + save
    assert any(f['type'] == 'execute' for f in fragments)
    assert any(f['type'] == 'save' for f in fragments)


@pytest.mark.asyncio
async def test_run_with_setup(test_cell, full_lifecycle):
    """Test run() with setup step"""
    result = await test_cell.run(full_lifecycle)
    
    assert test_cell.setup_called is True
    assert result['status'] == 'completed'
    
    # Check setup fragment
    fragments = result['fragments']
    setup_fragment = next((f for f in fragments if f['type'] == 'setup'), None)
    assert setup_fragment is not None
    assert setup_fragment['status'] == 'completed'


@pytest.mark.asyncio
async def test_run_multiple_actions(test_cell):
    """Test run() with multiple execute actions"""
    lifecycle = {
        'execute': [
            {'action': 'first', 'params': {'value': 5}},
            {'action': 'second', 'params': {'value': 10}},
            {'action': 'third', 'params': {'value': 15}}
        ]
    }
    
    result = await test_cell.run(lifecycle)
    
    assert result['status'] == 'completed'
    assert test_cell.execute_call_count == 3
    
    # Check execute fragments
    execute_fragments = [f for f in result['fragments'] if f['type'] == 'execute']
    assert len(execute_fragments) == 3
    assert execute_fragments[0]['action'] == 'first'
    assert execute_fragments[1]['action'] == 'second'
    assert execute_fragments[2]['action'] == 'third'


@pytest.mark.asyncio
async def test_run_single_action_as_dict(test_cell):
    """Test run() with execute as single dict (not array)"""
    lifecycle = {
        'execute': {'action': 'process', 'params': {'value': 5}}
    }
    
    result = await test_cell.run(lifecycle)
    
    assert result['status'] == 'completed'
    assert test_cell.execute_call_count == 1


@pytest.mark.asyncio
async def test_run_save_disabled(test_cell, basic_lifecycle):
    """Test run() with save disabled"""
    basic_lifecycle['save'] = False
    
    result = await test_cell.run(basic_lifecycle)
    
    assert result['status'] == 'completed'
    
    # Should not have save fragment
    save_fragments = [f for f in result['fragments'] if f['type'] == 'save']
    assert len(save_fragments) == 0


@pytest.mark.asyncio
async def test_run_error_in_setup(test_cell, full_lifecycle):
    """Test run() handles error in setup step"""
    test_cell.should_fail = True
    test_cell.fail_at_step = 'setup'
    
    result = await test_cell.run(full_lifecycle)
    
    assert result['status'] == 'failed'
    assert result['success'] is False
    assert 'error' in result
    assert result['error'] == 'Setup failed as requested'
    
    # Check error fragment
    error_fragments = [f for f in result['fragments'] if f['type'] == 'error']
    assert len(error_fragments) == 1
    assert error_fragments[0]['status'] == 'failed'
    assert 'Setup failed' in error_fragments[0]['error']
    
    # Execute should not have been called
    assert test_cell.execute_call_count == 0


@pytest.mark.asyncio
async def test_run_error_in_execute(test_cell, basic_lifecycle):
    """Test run() handles error in execute step"""
    test_cell.should_fail = True
    test_cell.fail_at_step = 'execute'
    
    result = await test_cell.run(basic_lifecycle)
    
    assert result['status'] == 'failed'
    assert result['success'] is False
    assert 'error' in result
    assert 'Execute failed' in result['error']
    
    # Check error fragment
    error_fragments = [f for f in result['fragments'] if f['type'] == 'error']
    assert len(error_fragments) == 1


@pytest.mark.asyncio
async def test_run_fragments_tracing(test_cell, full_lifecycle):
    """Test that fragments correctly trace execution"""
    result = await test_cell.run(full_lifecycle)
    
    fragments = result['fragments']
    
    # Should have: setup, execute (x2), save
    assert len(fragments) == 4
    
    # Check order and types
    assert fragments[0]['type'] == 'setup'
    assert fragments[1]['type'] == 'execute'
    assert fragments[2]['type'] == 'execute'
    assert fragments[3]['type'] == 'save'
    
    # All should be completed
    for fragment in fragments:
        assert fragment['status'] == 'completed'


@pytest.mark.asyncio
async def test_run_execution_time_recorded(test_cell, basic_lifecycle):
    """Test that execution time is recorded"""
    result = await test_cell.run(basic_lifecycle)
    
    assert 'execution_time' in result
    assert result['execution_time'] > 0
    assert result['execution_time'] < 10  # Should be very fast


@pytest.mark.asyncio
async def test_run_missing_action_key(test_cell):
    """Test run() handles missing 'action' key in execute"""
    lifecycle = {
        'execute': {'params': {'value': 5}}  # Missing 'action' key
    }
    
    result = await test_cell.run(lifecycle)
    
    assert result['status'] == 'failed'
    assert result['success'] is False
    assert 'action' in result['error'].lower()


@pytest.mark.asyncio
async def test_run_output_stored(test_cell, basic_lifecycle):
    """Test that output is stored in result"""
    result = await test_cell.run(basic_lifecycle)
    
    assert 'output' in result
    assert result['output'] == {'result': 10}  # 5 * 2


@pytest.mark.asyncio
async def test_run_with_save_config_object(test_cell, basic_lifecycle):
    """Test run() with save as config object"""
    basic_lifecycle['save'] = {'format': 'json', 'compress': True}
    
    result = await test_cell.run(basic_lifecycle)
    
    assert result['status'] == 'completed'
    
    # Should have save fragment
    save_fragments = [f for f in result['fragments'] if f['type'] == 'save']
    assert len(save_fragments) == 1


@pytest.mark.asyncio
async def test_run_empty_execute_actions(test_cell):
    """Test run() with empty execute actions"""
    lifecycle = {
        'execute': []
    }
    
    result = await test_cell.run(lifecycle)
    
    # Should fail because execute is empty (validation added)
    assert result['status'] == 'failed'
    assert test_cell.execute_call_count == 0


@pytest.mark.asyncio
async def test_run_missing_execute_key(test_cell):
    """Test run() with missing execute key"""
    lifecycle = {}  # Missing 'execute' key
    
    result = await test_cell.run(lifecycle)
    
    # Should fail with validation error
    assert result['status'] == 'failed'
    assert result['success'] is False
    assert 'execute' in result['error'].lower()


@pytest.mark.asyncio
async def test_run_returns_cell_id_from_describe(test_cell, basic_lifecycle):
    """Test that run() returns cell ID from describe()"""
    result = await test_cell.run(basic_lifecycle)
    
    assert result['id'] == 'test-cell'


@pytest.mark.asyncio  
async def test_run_fragments_have_action_name(test_cell):
    """Test that execute fragments include action name"""
    lifecycle = {
        'execute': [
            {'action': 'generate', 'params': {'value': 5}},
            {'action': 'transform', 'params': {'value': 10}}
        ]
    }
    
    result = await test_cell.run(lifecycle)
    
    execute_fragments = [f for f in result['fragments'] if f['type'] == 'execute']
    assert execute_fragments[0]['action'] == 'generate'
    assert execute_fragments[1]['action'] == 'transform'
