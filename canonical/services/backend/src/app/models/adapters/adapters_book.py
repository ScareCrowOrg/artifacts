"""
Book Adapter Implementation (Legacy Wrapper)

This is a thin wrapper around UnifiedNotebookItemAdapter for backward compatibility.
All new code should use UnifiedNotebookItemAdapter directly.

Note on BaseBook Instance Composition:
When instantiating BaseBook implementations, they should be passed the book_instance
to enable context-aware execution. Example:

    from some_book_module import MyBookType

    # Get the Book instance from database
    book_instance = await get_book(book_id)

    # Instantiate BaseBook with instance composition
    base_book = MyBookType(book_instance=book_instance)

    # Execute with access to metadata
    result = await base_book.execute(input_data)

For more details, see docs/official/ADDING_NEW_BOOK_TYPE.md section on Instance Composition.
"""

import logging
from typing import TYPE_CHECKING

from .notebook_item_adapter import UnifiedNotebookItemAdapter

if TYPE_CHECKING:
    from ..content import Book


logger = logging.getLogger(__name__)


class BookAdapter(UnifiedNotebookItemAdapter):
    """
    Legacy adapter for Book execution (thin wrapper).

    This adapter is maintained for backward compatibility with existing code.
    It delegates all execution to the unified UnifiedNotebookItemAdapter.

    New code should use UnifiedNotebookItemAdapter directly instead of BookAdapter.

    Usage:
        # Legacy pattern (still works)
        adapter = BookAdapter(book=my_book)
        result = await adapter.execute_in_pipeline(pipeline_item)

        # Preferred pattern
        adapter = UnifiedNotebookItemAdapter(item=my_book, pipeline_context_name="book_orchestration")
        result = await adapter.execute_in_pipeline(pipeline_item)
    """

    def __init__(self, book: "Book", **kwargs):
        """
        Initialize the BookAdapter.

        Args:
            book: The Book instance to wrap
            **kwargs: Additional fields for the adapter
        """
        # Set default pipeline context if not provided
        if "pipeline_context_name" not in kwargs:
            kwargs["pipeline_context_name"] = "book_orchestration"

        # Ensure book has kind='book' for proper dispatch
        if not hasattr(book, "kind") or book.kind is None:
            book.kind = "book"

        # Ensure book has default execution_mode if not set
        if not hasattr(book, "execution_mode") or book.execution_mode is None:
            book.execution_mode = "dag"

        super().__init__(item=book, **kwargs)

        logger.debug(
            f"BookAdapter initialized as thin wrapper for book {book.id}. "
            "Consider using UnifiedNotebookItemAdapter directly in new code."
        )
