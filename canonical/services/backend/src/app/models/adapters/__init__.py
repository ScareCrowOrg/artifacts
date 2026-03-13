"""
Adapter Classes for Notebook Items

This module implements the Adapter pattern for notebook items, providing
execution logic while keeping the pure data models clean and focused.

Module Structure:
- adapters_base.py: Base NotebookItemAdapter class
- notebook_item_adapter.py: Unified adapter implementation
- adapters_cell.py: CellAdapter (legacy thin wrapper)
- adapters_book.py: BookAdapter (legacy thin wrapper)

Public API:
- NotebookItemAdapter: Base adapter class (use UnifiedNotebookItemAdapter for new code)
- UnifiedNotebookItemAdapter: Unified adapter for cells and books
- CellAdapter: Legacy wrapper for backward compatibility
- BookAdapter: Legacy wrapper for backward compatibility
"""

from .adapters_base import NotebookItemAdapter
from .adapters_book import BookAdapter
from .adapters_cell import CellAdapter
from .notebook_item_adapter import UnifiedNotebookItemAdapter

__all__ = [
    "NotebookItemAdapter",
    "UnifiedNotebookItemAdapter",
    "CellAdapter",
    "BookAdapter",
]
