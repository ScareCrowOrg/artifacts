"""
Unit tests for Cell Promotion Service.

Tests cover NotebookItemType creation, asset persistence, and promotion workflow.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cell_promotion_service import CellPromotionService
from app.models import (
    Cell,
    NotebookItemType,
    CellPromotionRequest,
    CellPromotionResponse,
    DynamicRef,
    CellStatus
)


class TestCellPromotionService:
    """Unit tests for CellPromotionService."""
    
    @pytest.fixture
    def service(self):
        """Create a CellPromotionService instance for testing."""
        return CellPromotionService(redis_service=None)
    
    @pytest.fixture
    def sample_cell_with_validated_refs(self):
        """Create a sample cell with validated dynamic refs."""
        return Cell(
            assignee_id="user-123",
            notebook_item_type_id="unclassified-cell-type",
            title="Test Cell",
            content="Test content",
            initial_data={
                "dynamic_refs": [
                    {
                        "type": "visual",
                        "lang": "svg",
                        "path": "sandbox/assets/visual_123.svg",
                        "filename": "visual_123.svg",
                        "size_bytes": 100,
                        "validated": True
                    },
                    {
                        "type": "logic",
                        "lang": "js",
                        "path": "sandbox/assets/logic_456.js",
                        "filename": "logic_456.js",
                        "size_bytes": 200,
                        "validated": True
                    }
                ],
                "generation_metadata": {
                    "prompt": "Generate chart",
                    "model": "gpt-4",
                    "promotion_ready": True
                }
            }
        )
    
    @pytest.fixture
    def promotion_request(self, sample_cell_with_validated_refs):
        """Create a sample promotion request."""
        return CellPromotionRequest(
            cell_id=sample_cell_with_validated_refs.id,
            new_type_name="custom-chart-cell",
            new_type_description="Custom chart component",
            category="generated"
        )
    
    @pytest.mark.asyncio
    async def test_promote_cell_success(self, service, sample_cell_with_validated_refs, promotion_request):
        """Test successful cell promotion."""
        with patch('app.services.cell_promotion_service.db') as mock_db:
            mock_db.insert = AsyncMock()
            mock_db.update = AsyncMock()
            
            result = await service.promote_cell(promotion_request, sample_cell_with_validated_refs)
            
            # Verify result
            assert isinstance(result, CellPromotionResponse)
            assert result.success is True
            assert result.new_cell_type_id is not None
            assert result.new_cell_id is not None
            assert result.layout_book_synced is True
            assert result.persisted_assets_count == 2
            
            # Verify database operations were called
            assert mock_db.insert.call_count == 2  # cell type + new cell
    
    @pytest.mark.asyncio
    async def test_promote_cell_no_refs(self, service, promotion_request):
        """Test promoting cell without dynamic refs."""
        cell_without_refs = Cell(
            assignee_id="user-123",
            notebook_item_type_id="unclassified-cell-type",
            initial_data={}
        )
        
        with pytest.raises(ValueError, match="no dynamic refs"):
            await service.promote_cell(promotion_request, cell_without_refs)
    
    def test_get_dynamic_refs(self, service, sample_cell_with_validated_refs):
        """Test extracting dynamic refs from cell."""
        refs = service._get_dynamic_refs(sample_cell_with_validated_refs)
        
        assert len(refs) == 2
        assert all(isinstance(ref, DynamicRef) for ref in refs)
        assert refs[0].type == "visual"
        assert refs[1].type == "logic"
    
    @pytest.mark.asyncio
    async def test_create_notebook_item_type(self, service, promotion_request):
        """Test creating NotebookItemType from promotion request."""
        refs = [
            DynamicRef(
                type="visual",
                lang="svg",
                path="sandbox/assets/visual_123.svg",
                filename="visual_123.svg",
                size_bytes=100
            ),
            DynamicRef(
                type="logic",
                lang="js",
                path="sandbox/assets/logic_456.js",
                filename="logic_456.js",
                size_bytes=200
            )
        ]
        
        cell_type = await service._create_notebook_item_type(promotion_request, refs)
        
        # Verify cell type properties
        assert isinstance(cell_type, NotebookItemType)
        assert cell_type.name == promotion_request.new_type_name
        assert cell_type.description == promotion_request.new_type_description
        assert cell_type.can_render_dynamically is True
        assert cell_type.allow_instance_override_refs is True
        
        # Verify default_refs were created
        assert "visual" in cell_type.default_refs
        assert "logic" in cell_type.default_refs
        assert len(cell_type.default_refs["visual"]) == 1
        assert len(cell_type.default_refs["logic"]) == 1
        
        # Verify default_initial_data
        assert cell_type.default_initial_data["category"] == promotion_request.category
        assert cell_type.default_initial_data["generated"] is True
        assert cell_type.default_initial_data["source"] == "cell_factory"
    
    @pytest.mark.asyncio
    async def test_persist_assets_to_gridfs(self, service):
        """Test persisting assets to GridFS."""
        refs = [
            DynamicRef(
                type="visual",
                lang="svg",
                path="sandbox/assets/visual_123.svg",
                filename="visual_123.svg",
                size_bytes=100
            ),
            DynamicRef(
                type="logic",
                lang="js",
                path="sandbox/assets/logic_456.js",
                filename="logic_456.js",
                size_bytes=200
            )
        ]
        
        count = await service._persist_assets_to_gridfs(refs, "cell-type-123")
        
        # For MVP 1, should return count of refs
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_register_cell_type(self, service):
        """Test registering cell type in database."""
        cell_type = NotebookItemType(
            name="test-cell-type",
            description="Test cell type"
        )
        
        with patch('app.services.cell_promotion_service.db') as mock_db:
            mock_db.insert = AsyncMock()
            
            await service._register_cell_type(cell_type)
            
            # Verify database insert was called with correct parameters
            mock_db.insert.assert_called_once_with(
                "notebook_item_types",
                cell_type,
                user_id="system",
                session_id="default",
                is_canonical=True
            )
    
    @pytest.mark.asyncio
    async def test_update_layout_book(self, service):
        """Test updating Layout Book with new cell type."""
        cell_type = NotebookItemType(
            name="test-cell-type",
            description="Test cell type"
        )
        
        result = await service._update_layout_book(cell_type)
        
        # For MVP 1, should always return True
        assert result is True
    
    @pytest.mark.asyncio
    async def test_create_cell_instance(self, service, sample_cell_with_validated_refs):
        """Test creating new cell instance from promoted cell."""
        cell_type = NotebookItemType(
            name="test-cell-type",
            description="Test cell type",
            default_refs={"visual": ["path/to/visual.svg"]},
            default_initial_data={"category": "generated"}
        )
        
        with patch('app.services.cell_promotion_service.db') as mock_db:
            mock_db.insert = AsyncMock()
            
            new_cell = await service._create_cell_instance(
                sample_cell_with_validated_refs,
                cell_type
            )
            
            # Verify new cell properties
            assert isinstance(new_cell, Cell)
            assert new_cell.assignee_id == sample_cell_with_validated_refs.assignee_id
            assert new_cell.notebook_item_type_id == cell_type.id
            assert new_cell.source_book_id == sample_cell_with_validated_refs.source_book_id
            assert new_cell.title == sample_cell_with_validated_refs.title
            assert new_cell.content == sample_cell_with_validated_refs.content
            assert new_cell.category == "generated"
            
            # Verify database insert was called
            mock_db.insert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_opfs(self, service):
        """Test OPFS cleanup after promotion."""
        refs = [
            DynamicRef(
                type="visual",
                lang="svg",
                path="sandbox/assets/visual_123.svg",
                filename="visual_123.svg",
                size_bytes=100
            )
        ]
        
        # Should not raise any errors
        await service._cleanup_opfs(refs)
    
    @pytest.mark.asyncio
    async def test_promote_cell_error_handling(self, service, sample_cell_with_validated_refs, promotion_request):
        """Test error handling in promotion."""
        with patch('app.services.cell_promotion_service.db') as mock_db:
            # Simulate database error
            mock_db.insert = AsyncMock(side_effect=Exception("Database error"))
            
            # Should raise ValueError with wrapped exception
            with pytest.raises(ValueError, match="Cell promotion failed"):
                await service.promote_cell(promotion_request, sample_cell_with_validated_refs)
    
    @pytest.mark.asyncio
    async def test_promotion_workflow_order(self, service, sample_cell_with_validated_refs, promotion_request):
        """Test that promotion workflow steps execute in correct order."""
        call_order = []
        
        async def track_call(name):
            call_order.append(name)
        
        async def mock_insert(collection, *args, **kwargs):
            await track_call(f"insert_{collection}")
        
        with patch('app.services.cell_promotion_service.db') as mock_db:
            mock_db.insert = AsyncMock(side_effect=mock_insert)
            
            await service.promote_cell(promotion_request, sample_cell_with_validated_refs)
            
            # Verify order: cell type inserted before new cell
            assert "insert_notebook_item_types" in call_order
            assert "insert_cells" in call_order
            assert call_order.index("insert_notebook_item_types") < call_order.index("insert_cells")
