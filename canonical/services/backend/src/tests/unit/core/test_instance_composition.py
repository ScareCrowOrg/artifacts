"""
Unit tests for BaseCell and BaseBook instance composition pattern.

Tests that BaseCell and BaseBook can optionally reference their runtime instances
for metadata access, following the PipelineItem → NotebookItem composition pattern.

Coverage target: >90% for instance composition functionality
"""

import pytest
from typing import Dict, Any, Optional
import sys
import os

# Add path to backend for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.core.base_cell import (
    BaseCell, CellResult, CellMetadata, ValidationError,
    EnvironmentConfig
)
from app.core.base_book import (
    BaseBook, BookResult, DAGDefinition, DAGNode, DAGEdge
)


# ============ MOCK CELL/BOOK INSTANCES ============


class MockCell:
    """Mock Cell instance for testing"""
    def __init__(self):
        self.id = 'test-cell-id'
        self.assignee_id = 'user-123'
        self.initial_data = {'config_value': 42, 'mode': 'test'}
        self.fragments = ['fragment1', {'type': 'memory', 'content': 'test'}]
        self.refs = {'docs': ['doc1.md'], 'scripts': ['script.py']}
        self.version = '1.0.0'
        self.created_at = '2024-01-01T00:00:00Z'
        self.updated_at = '2024-01-01T00:00:00Z'


class MockBook:
    """Mock Book instance for testing"""
    def __init__(self):
        self.id = 'test-book-id'
        self.assignee_id = 'user-456'
        self.name = 'Test Book'
        self.description = 'Test book description'
        self.initial_data = {'workflow_config': 'enabled'}
        self.fragments = []
        self.refs = {}
        self.cells = ['cell-1', 'cell-2']
        self.children = []
        self.created_at = '2024-01-01T00:00:00Z'
        self.updated_at = '2024-01-01T00:00:00Z'


# ============ TEST CELL IMPLEMENTATIONS ============


class UtilityCell(BaseCell):
    """Test cell that doesn't need instance (utility pattern)"""
    
    def __init__(self):
        # Don't pass cell_instance - utility cell
        super().__init__(cell_instance=None)
    
    async def execute(self, input: Dict[str, Any]) -> CellResult:
        """Pure utility execution"""
        result = input.get('value', 0) * 2
        return CellResult(
            success=True,
            output={'result': result},
            execution_time=0.001
        )
    
    async def describe(self) -> CellMetadata:
        return CellMetadata(
            id='utility-cell',
            name='Utility Cell',
            version='1.0.0',
            description='Pure utility cell',
            inputs={'value': 'number'},
            outputs={'result': 'number'},
            tags=['utility']
        )
    
    def validate(self, input: Dict[str, Any]) -> list:
        return []


class ContextAwareCell(BaseCell):
    """Test cell that uses instance metadata (context-aware pattern)"""
    
    def __init__(self, cell_instance: Optional[Any] = None):
        super().__init__(cell_instance=cell_instance)
    
    async def execute(self, input: Dict[str, Any]) -> CellResult:
        """Execution that uses instance metadata"""
        # Access metadata when available
        owner = self.cell_instance.assignee_id if self.cell_instance else 'unknown'
        config = self.cell_instance.initial_data if self.cell_instance else {}
        version = self.cell_instance.version if self.cell_instance else 'none'
        
        result = {
            'owner': owner,
            'config_value': config.get('config_value', 0),
            'version': version,
            'input_value': input.get('value', 0)
        }
        
        return CellResult(
            success=True,
            output=result,
            execution_time=0.001
        )
    
    async def describe(self) -> CellMetadata:
        return CellMetadata(
            id='context-aware-cell',
            name='Context-Aware Cell',
            version='1.0.0',
            description='Cell that uses instance metadata',
            inputs={'value': 'number'},
            outputs={'owner': 'string', 'config_value': 'number'},
            tags=['context-aware']
        )
    
    def validate(self, input: Dict[str, Any]) -> list:
        return []


# ============ TEST BOOK IMPLEMENTATIONS ============


class ContextAwareBook(BaseBook):
    """Test book that uses instance metadata"""
    
    def __init__(self, book_instance: Optional[Any] = None):
        super().__init__(book_instance=book_instance)
    
    async def execute(self, input: Dict[str, Any]) -> BookResult:
        """Execution that uses instance metadata"""
        # Access metadata when available
        owner = self.book_instance.assignee_id if self.book_instance else 'unknown'
        config = self.book_instance.initial_data if self.book_instance else {}
        cells = self.book_instance.cells if self.book_instance else []
        
        result = {
            'owner': owner,
            'workflow_config': config.get('workflow_config', 'disabled'),
            'cell_count': len(cells)
        }
        
        return BookResult(
            success=True,
            output=result,
            execution_time=0.001
        )
    
    async def describe(self) -> CellMetadata:
        return CellMetadata(
            id='context-aware-book',
            name='Context-Aware Book',
            version='1.0.0',
            description='Book that uses instance metadata',
            inputs={'data': 'object'},
            outputs={'owner': 'string', 'workflow_config': 'string'},
            tags=['context-aware', 'book']
        )
    
    def get_dag(self) -> DAGDefinition:
        return DAGDefinition(
            nodes=[
                DAGNode(id='step1', cell_type='test-cell', input={'value': 42})
            ],
            edges=[]
        )


# ============ TESTS FOR BASECELL COMPOSITION ============


class TestBaseCellComposition:
    """Tests for BaseCell instance composition pattern"""
    
    @pytest.mark.asyncio
    async def test_utility_cell_without_instance(self):
        """Test that utility cells work without instance reference"""
        cell = UtilityCell()
        
        # Verify no instance attached
        assert cell.cell_instance is None
        
        # Execute should work fine
        result = await cell.execute({'value': 21})
        
        assert result.success is True
        assert result.output['result'] == 42
    
    @pytest.mark.asyncio
    async def test_context_aware_cell_without_instance(self):
        """Test that context-aware cells handle missing instance gracefully"""
        cell = ContextAwareCell(cell_instance=None)
        
        # Verify no instance attached
        assert cell.cell_instance is None
        
        # Execute should work with defaults
        result = await cell.execute({'value': 100})
        
        assert result.success is True
        assert result.output['owner'] == 'unknown'
        assert result.output['config_value'] == 0
        assert result.output['version'] == 'none'
        assert result.output['input_value'] == 100
    
    @pytest.mark.asyncio
    async def test_context_aware_cell_with_instance(self):
        """Test that context-aware cells can access instance metadata"""
        mock_cell = MockCell()
        cell = ContextAwareCell(cell_instance=mock_cell)
        
        # Verify instance attached
        assert cell.cell_instance is not None
        assert cell.cell_instance.id == 'test-cell-id'
        
        # Execute should access metadata
        result = await cell.execute({'value': 100})
        
        assert result.success is True
        assert result.output['owner'] == 'user-123'
        assert result.output['config_value'] == 42
        assert result.output['version'] == '1.0.0'
        assert result.output['input_value'] == 100
    
    @pytest.mark.asyncio
    async def test_cell_instance_metadata_access(self):
        """Test that all instance metadata fields are accessible"""
        mock_cell = MockCell()
        cell = ContextAwareCell(cell_instance=mock_cell)
        
        # Verify all metadata accessible
        assert cell.cell_instance.id == 'test-cell-id'
        assert cell.cell_instance.assignee_id == 'user-123'
        assert cell.cell_instance.initial_data == {'config_value': 42, 'mode': 'test'}
        assert len(cell.cell_instance.fragments) == 2
        assert cell.cell_instance.refs == {'docs': ['doc1.md'], 'scripts': ['script.py']}
        assert cell.cell_instance.version == '1.0.0'
    
    def test_basecell_constructor_accepts_instance(self):
        """Test that BaseCell constructor accepts cell_instance parameter"""
        mock_cell = MockCell()
        
        # Should not raise
        cell = ContextAwareCell(cell_instance=mock_cell)
        
        assert cell.cell_instance == mock_cell


# ============ TESTS FOR BASEBOOK COMPOSITION ============


class TestBaseBookComposition:
    """Tests for BaseBook instance composition pattern"""
    
    @pytest.mark.asyncio
    async def test_book_without_instance(self):
        """Test that books work without instance reference"""
        book = ContextAwareBook(book_instance=None)
        
        # Verify no instance attached
        assert book.book_instance is None
        
        # Execute should work with defaults
        result = await book.execute({'data': 'test'})
        
        assert result.success is True
        assert result.output['owner'] == 'unknown'
        assert result.output['workflow_config'] == 'disabled'
        assert result.output['cell_count'] == 0
    
    @pytest.mark.asyncio
    async def test_book_with_instance(self):
        """Test that books can access instance metadata"""
        mock_book = MockBook()
        book = ContextAwareBook(book_instance=mock_book)
        
        # Verify instance attached
        assert book.book_instance is not None
        assert book.book_instance.id == 'test-book-id'
        
        # Execute should access metadata
        result = await book.execute({'data': 'test'})
        
        assert result.success is True
        assert result.output['owner'] == 'user-456'
        assert result.output['workflow_config'] == 'enabled'
        assert result.output['cell_count'] == 2
    
    @pytest.mark.asyncio
    async def test_book_instance_metadata_access(self):
        """Test that all book instance metadata fields are accessible"""
        mock_book = MockBook()
        book = ContextAwareBook(book_instance=mock_book)
        
        # Verify all metadata accessible
        assert book.book_instance.id == 'test-book-id'
        assert book.book_instance.assignee_id == 'user-456'
        assert book.book_instance.name == 'Test Book'
        assert book.book_instance.description == 'Test book description'
        assert book.book_instance.initial_data == {'workflow_config': 'enabled'}
        assert book.book_instance.cells == ['cell-1', 'cell-2']
    
    def test_basebook_constructor_accepts_instance(self):
        """Test that BaseBook constructor accepts book_instance parameter"""
        mock_book = MockBook()
        
        # Should not raise
        book = ContextAwareBook(book_instance=mock_book)
        
        assert book.book_instance == mock_book


# ============ TESTS FOR BACKWARD COMPATIBILITY ============


class TestBackwardCompatibility:
    """Tests to ensure the composition pattern is backward compatible"""
    
    @pytest.mark.asyncio
    async def test_existing_cells_still_work(self):
        """Test that existing cells without instance parameter still work"""
        # Old-style cell (no __init__ override)
        class OldStyleCell(BaseCell):
            async def execute(self, input: Dict[str, Any]) -> CellResult:
                return CellResult(
                    success=True,
                    output={'result': 42},
                    execution_time=0.001
                )
            
            async def describe(self) -> CellMetadata:
                return CellMetadata(
                    id='old-cell',
                    name='Old Cell',
                    version='1.0.0',
                    description='Old style cell',
                    inputs={},
                    outputs={},
                    tags=[]
                )
            
            def validate(self, input: Dict[str, Any]) -> list:
                return []
        
        # Should work without any changes
        cell = OldStyleCell()
        result = await cell.execute({})
        
        assert result.success is True
        assert result.output['result'] == 42
    
    def test_cell_instance_is_optional(self):
        """Test that cell_instance is truly optional"""
        # Should not raise when no instance provided
        cell1 = UtilityCell()
        assert cell1.cell_instance is None
        
        # Should not raise when None provided explicitly
        cell2 = ContextAwareCell(cell_instance=None)
        assert cell2.cell_instance is None
        
        # Should accept instance when provided
        mock_cell = MockCell()
        cell3 = ContextAwareCell(cell_instance=mock_cell)
        assert cell3.cell_instance is not None


# ============ INTEGRATION TESTS ============


class TestCompositionIntegration:
    """Integration tests for composition pattern"""
    
    @pytest.mark.asyncio
    async def test_cell_composition_passing_context(self):
        """Test that cells can share context when composed"""
        mock_cell = MockCell()
        
        # Create two cells with shared instance
        cell_a = ContextAwareCell(cell_instance=mock_cell)
        cell_b = ContextAwareCell(cell_instance=mock_cell)
        
        # Both should access same metadata
        result_a = await cell_a.execute({'value': 1})
        result_b = await cell_b.execute({'value': 2})
        
        assert result_a.output['owner'] == result_b.output['owner']
        assert result_a.output['config_value'] == result_b.output['config_value']
    
    @pytest.mark.asyncio
    async def test_mixed_utility_and_context_aware_cells(self):
        """Test that utility and context-aware cells can coexist"""
        mock_cell = MockCell()
        
        utility = UtilityCell()
        context_aware = ContextAwareCell(cell_instance=mock_cell)
        
        # Both should execute successfully
        result1 = await utility.execute({'value': 10})
        result2 = await context_aware.execute({'value': 10})
        
        assert result1.success is True
        assert result2.success is True
        
        # Utility has no metadata access
        assert result1.output == {'result': 20}
        
        # Context-aware has metadata access
        assert result2.output['owner'] == 'user-123'
        assert result2.output['config_value'] == 42
