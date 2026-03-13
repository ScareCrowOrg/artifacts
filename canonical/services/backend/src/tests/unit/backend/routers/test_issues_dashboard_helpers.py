"""
Unit tests for issues_dashboard/helpers.py

Tests cover:
- get_filtered_cells_and_counts - Cell filtering and status counting
- Issue counts calculation with English status values
- Status filter functionality

Technical naming: All functions and variables in English.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.routers.issues_dashboard.helpers import get_filtered_cells_and_counts
from app.routers.issues_dashboard.models import IssueCounts
from app.models import Cell


@pytest.fixture
def mock_cells():
    """Create mock cells with English status values."""
    cells = []
    
    # Create cells with different statuses
    statuses = [
        ("pending", 5),
        ("running", 3),
        ("completed", 10),
        ("error", 2)
    ]
    
    for status, count in statuses:
        for i in range(count):
            cell = Mock(spec=Cell)
            cell.id = f"cell-{status}-{i}"
            cell.notebook_item_type_id = "ingestion-issue"
            cell.source_book_id = "book-issues-queue-v1"
            cell.status = status
            cell.title = f"Test Cell {status} {i}"
            cells.append(cell)
    
    return cells


@pytest.fixture
def mock_db(mock_cells):
    """Mock database find_many method."""
    with patch('app.routers.issues_dashboard.helpers.db') as mock:
        mock.find_many = AsyncMock(return_value=mock_cells)
        yield mock


class TestGetFilteredCellsAndCounts:
    """Tests for get_filtered_cells_and_counts function."""
    
    @pytest.mark.asyncio
    async def test_counts_with_english_status_values(self, mock_db, mock_cells):
        """Test that issue counts are correctly calculated with English status values."""
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=20
        )
        
        # Verify counts map English status to Portuguese field names
        assert issue_counts.pendente == 5, "Should count 5 'pending' cells as 'pendente'"
        assert issue_counts.executando == 3, "Should count 3 'running' cells as 'executando'"
        assert issue_counts.finalizado == 10, "Should count 10 'completed' cells as 'finalizado'"
        assert issue_counts.erro == 2, "Should count 2 'error' cells as 'erro'"
        
        # Verify total items
        assert total_items == 20, "Should have 20 total cells"
    
    @pytest.mark.asyncio
    async def test_filter_by_pending_status(self, mock_db, mock_cells):
        """Test filtering by 'pending' status."""
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=20,
            status_filter="pending"
        )
        
        # Verify filtered items
        assert total_items == 5, "Should have 5 pending cells"
        assert all(cell.status == "pending" for cell in page_items), "All returned cells should be pending"
        
        # Verify counts still include all statuses
        assert issue_counts.pendente == 5
        assert issue_counts.executando == 3
        assert issue_counts.finalizado == 10
        assert issue_counts.erro == 2
    
    @pytest.mark.asyncio
    async def test_filter_by_running_status(self, mock_db, mock_cells):
        """Test filtering by 'running' status."""
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=20,
            status_filter="running"
        )
        
        # Verify filtered items
        assert total_items == 3, "Should have 3 running cells"
        assert all(cell.status == "running" for cell in page_items), "All returned cells should be running"
    
    @pytest.mark.asyncio
    async def test_filter_by_completed_status(self, mock_db, mock_cells):
        """Test filtering by 'completed' status."""
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=20,
            status_filter="completed"
        )
        
        # Verify filtered items
        assert total_items == 10, "Should have 10 completed cells"
        assert all(cell.status == "completed" for cell in page_items), "All returned cells should be completed"
    
    @pytest.mark.asyncio
    async def test_filter_by_error_status(self, mock_db, mock_cells):
        """Test filtering by 'error' status."""
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=20,
            status_filter="error"
        )
        
        # Verify filtered items
        assert total_items == 2, "Should have 2 error cells"
        assert all(cell.status == "error" for cell in page_items), "All returned cells should be error"
    
    @pytest.mark.asyncio
    async def test_filter_all_returns_all_cells(self, mock_db, mock_cells):
        """Test filtering with 'all' returns all cells."""
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=20,
            status_filter="all"
        )
        
        # Verify all items returned
        assert total_items == 20, "Should have all 20 cells"
    
    @pytest.mark.asyncio
    async def test_pagination_first_page(self, mock_db, mock_cells):
        """Test pagination returns correct first page."""
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=5
        )
        
        assert len(page_items) == 5, "Should return 5 items on first page"
        assert total_pages == 4, "Should have 4 pages total (20 items / 5 per page)"
        assert current_page == 1, "Should be on page 1"
    
    @pytest.mark.asyncio
    async def test_pagination_second_page(self, mock_db, mock_cells):
        """Test pagination returns correct second page."""
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=2,
            limit=5
        )
        
        assert len(page_items) == 5, "Should return 5 items on second page"
        assert current_page == 2, "Should be on page 2"
    
    @pytest.mark.asyncio
    async def test_case_insensitive_status_filter(self, mock_db, mock_cells):
        """Test that status filter is case-insensitive."""
        page_items_lower, _, _, _, _ = await get_filtered_cells_and_counts(
            page=1,
            limit=20,
            status_filter="pending"
        )
        
        page_items_upper, _, _, _, _ = await get_filtered_cells_and_counts(
            page=1,
            limit=20,
            status_filter="PENDING"
        )
        
        page_items_mixed, _, _, _, _ = await get_filtered_cells_and_counts(
            page=1,
            limit=20,
            status_filter="Pending"
        )
        
        # All should return the same results
        assert len(page_items_lower) == len(page_items_upper) == len(page_items_mixed)
    
    @pytest.mark.asyncio
    async def test_counts_sum_equals_total(self, mock_db, mock_cells):
        """Test that sum of all status counts equals total items."""
        _, total_items, _, _, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=20
        )
        
        counts_sum = (
            issue_counts.pendente +
            issue_counts.executando +
            issue_counts.finalizado +
            issue_counts.erro
        )
        
        assert counts_sum == total_items, "Sum of status counts should equal total items"
    
    @pytest.mark.asyncio
    async def test_empty_result_when_no_matching_cells(self, mock_db):
        """Test handling of empty result when no cells match filters."""
        mock_db.find_many = AsyncMock(return_value=[])
        
        page_items, total_items, total_pages, current_page, issue_counts = await get_filtered_cells_and_counts(
            page=1,
            limit=20
        )
        
        assert total_items == 0, "Should have 0 items"
        assert len(page_items) == 0, "Should return empty list"
        assert issue_counts.pendente == 0
        assert issue_counts.executando == 0
        assert issue_counts.finalizado == 0
        assert issue_counts.erro == 0
