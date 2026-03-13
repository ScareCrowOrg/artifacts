"""
Cell Adapter Implementation (Legacy Wrapper)

This is a thin wrapper around UnifiedNotebookItemAdapter for backward compatibility.
All new code should use UnifiedNotebookItemAdapter directly.

Note on BaseCell Instance Composition:
When instantiating BaseCell implementations, they should be passed the cell_instance
to enable context-aware execution. Example:

    from some_cell_module import MyCellType

    # Get the Cell instance from database
    cell_instance = await get_cell(cell_id)

    # Instantiate BaseCell with instance composition
    base_cell = MyCellType(cell_instance=cell_instance)

    # Execute with access to metadata
    result = await base_cell.execute(input_data)

For more details, see docs/official/ADDING_NEW_CELL_TYPE.md section on Instance Composition.
"""

import logging
from typing import TYPE_CHECKING

from .notebook_item_adapter import UnifiedNotebookItemAdapter

if TYPE_CHECKING:
    from ..content import Cell


logger = logging.getLogger(__name__)


class CellAdapter(UnifiedNotebookItemAdapter):
    """
    Legacy adapter for Cell execution (thin wrapper).

    This adapter is maintained for backward compatibility with existing code.
    It delegates all execution to the unified UnifiedNotebookItemAdapter.

    New code should use UnifiedNotebookItemAdapter directly instead of CellAdapter.

    Usage:
        # Legacy pattern (still works)
        adapter = CellAdapter(cell=my_cell)
        result = await adapter.execute_in_pipeline(pipeline_item)

        # Preferred pattern
        adapter = UnifiedNotebookItemAdapter(item=my_cell, pipeline_context_name="cell_execution")
        result = await adapter.execute_in_pipeline(pipeline_item)
    """

    def __init__(self, cell: "Cell", **kwargs):
        """
        Initialize the CellAdapter.

        Args:
            cell: The Cell instance to wrap
            **kwargs: Additional fields for the adapter
        """
        # Set default pipeline context if not provided
        if "pipeline_context_name" not in kwargs:
            kwargs["pipeline_context_name"] = "cell_execution"

        # Ensure cell has kind='cell' for proper dispatch
        if not hasattr(cell, "kind") or cell.kind is None:
            cell.kind = "cell"

        super().__init__(item=cell, **kwargs)

        logger.debug(
            f"CellAdapter initialized as thin wrapper for cell {cell.id}. "
            "Consider using UnifiedNotebookItemAdapter directly in new code."
        )
