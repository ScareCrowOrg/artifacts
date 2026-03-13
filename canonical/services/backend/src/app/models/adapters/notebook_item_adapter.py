"""
Unified NotebookItemAdapter Implementation

This module implements the unified adapter that handles both cells and books,
replacing separate CellAdapter and BookAdapter with a single, robust execution engine.

Key Features:
- Dispatch by kind: Automatically routes to _run_cell() or _run_book()
- Dual-mode book execution: Supports DAG, Script, and Hybrid modes
- Hierarchical tracing: Tracks execution via executed_by field in fragments
- Fragment management: Centralizes creation and updates of ExecutionFragments
- Status propagation: Parent item status reflects child execution progress

Architecture Reference:
- docs/issues/discovery-planning-system-epic/TO_BE_VISION.md (Section 4.1: Unified Runtime)
- docs/issues/discovery-planning-system-epic/ACTION_PLAN.md (Unified Notebook Runtime)
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime

from .adapters_base import NotebookItemAdapter as BaseAdapter

if TYPE_CHECKING:
    from ...core.models import NotebookItem, PipelineItem, ExecutionFragment
    from ..content import Cell, Book

logger = logging.getLogger(__name__)


class UnifiedNotebookItemAdapter(BaseAdapter):
    """
    Unified adapter for both cells and books.

    This adapter implements the "Despachante Unificado" architecture, providing:
    - Single execution interface for all NotebookItems
    - Dynamic dispatch based on 'kind' field (cell vs book)
    - Hierarchical tracing via executed_by field
    - Fragment-based state management
    - Support for dual-mode book execution (DAG/Script/Hybrid)

    Usage:
        # For a Cell
        cell = Cell(assignee_id="user-123", kind="cell", ...)
        adapter = NotebookItemAdapter(item=cell, pipeline_context_name="unified_runtime")
        result = await adapter.execute_in_pipeline(pipeline_item)

        # For a Book
        book = Book(assignee_id="user-123", kind="book", execution_mode="dag", ...)
        adapter = NotebookItemAdapter(item=book, pipeline_context_name="unified_runtime")
        result = await adapter.execute_in_pipeline(pipeline_item)
    """

    async def execute_in_pipeline(self, pipeline_item_instance: "PipelineItem") -> Any:
        """
        Execute notebook item with unified dispatch.

        This is the main entry point that:
        1. Determines item kind (cell vs book)
        2. Dispatches to appropriate execution method
        3. Manages fragments and status updates
        4. Implements hierarchical tracing

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Execution result (PipelineItem or custom result)

        Raises:
            ValueError: If kind is not recognized
            Exception: If execution fails
        """
        notebook_item = self.item

        # Add execution start fragment
        pipeline_item_instance.add_fragment(
            type="execution",
            content=f"Starting unified execution for {notebook_item.kind or 'unknown'} item {notebook_item.id}",
            metadata={
                "step": "start",
                "notebook_item_id": notebook_item.id,
                "kind": notebook_item.kind,
            },
        )

        # Update status
        pipeline_item_instance.update_status("running")

        try:
            # Dispatch based on kind
            result = await self._dispatch_by_kind(pipeline_item_instance)

            # Add completion fragment
            pipeline_item_instance.add_fragment(
                type="execution",
                content=f"Unified execution completed successfully for {notebook_item.id}",
                metadata={
                    "step": "complete",
                    "notebook_item_id": notebook_item.id,
                    "kind": notebook_item.kind,
                },
            )

            # Update status
            pipeline_item_instance.update_status("completed")

            # Persist execution record
            await self._persist_execution_record(pipeline_item_instance, notebook_item)

            return result

        except Exception as e:
            logger.error("Unified execution failed for %s: %s", notebook_item.id, e, exc_info=True)

            # Handle execution error
            pipeline_item_instance.set_error(str(e))

            # Add error fragment
            notebook_item.fragments.append({
                "tipo": "error",
                "conteudo": f"Unified execution failed: {str(e)}",
                "metadata": {
                    "notebook_item_id": notebook_item.id,
                    "kind": notebook_item.kind,
                },
            })

            # Persist execution record even on error
            await self._persist_execution_record(pipeline_item_instance, notebook_item)

            raise

    async def _dispatch_by_kind(self, pipeline_item_instance: "PipelineItem") -> Any:
        """
        Dispatch execution based on notebook item kind.

        Routes to:
        - _run_cell() if kind='cell'
        - _run_book() if kind='book'
        - Fallback to parent implementation if kind is None

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Execution result

        Raises:
            ValueError: If kind is not recognized
        """
        notebook_item = self.item
        kind = notebook_item.kind

        if kind == "cell":
            logger.info("Dispatching to _run_cell for %s", notebook_item.id)
            return await self._run_cell(pipeline_item_instance)
        elif kind == "book":
            logger.info("Dispatching to _run_book for %s", notebook_item.id)
            return await self._run_book(pipeline_item_instance)
        elif kind is None:
            # Fallback to base implementation for backward compatibility
            logger.warning("No kind specified for %s, falling back to base implementation", notebook_item.id)
            return await super().execute_in_pipeline(pipeline_item_instance)
        else:
            raise ValueError(f"Unknown notebook item kind: {kind}")

    async def _run_cell(self, pipeline_item_instance: "PipelineItem") -> Any:
        """
        Execute a cell.

        Implements cell-specific execution logic:
        1. Extract parameters from cell's initial_data and refs
        2. Invoke workflow execution (ingestion or custom)
        3. Update fragments with results
        4. Return execution result

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Execution result (PipelineItem)
        """
        # Import here to avoid circular dependencies
        from ...workflows.ingestion import execute as execute_ingestion

        notebook_item = self.item

        # Add cell execution start fragment
        pipeline_item_instance.add_fragment(
            type="execution",
            content=f"Starting cell execution for {notebook_item.id}",
            metadata={"step": "cell_start", "notebook_item_id": notebook_item.id},
        )

        try:
            # Execute the ingestion workflow
            # The workflow accesses the original cell via pipeline_item_instance.notebook_item_data
            result_item = execute_ingestion(pipeline_item_instance)

            # Add completion fragment
            result_item.add_fragment(
                type="execution",
                content=f"Cell execution completed successfully",
                metadata={"step": "cell_complete", "notebook_item_id": notebook_item.id},
            )

            return result_item

        except Exception as e:
            logger.error("Cell execution failed for %s: %s", notebook_item.id, e, exc_info=True)
            raise

    async def _run_book(self, pipeline_item_instance: "PipelineItem") -> Any:
        """
        Execute a book with dual-mode dispatch.

        Implements book-specific execution logic with support for three modes:
        1. DAG Mode: Parallel execution using graph orchestrator
        2. Script Mode: Sequential/imperative execution
        3. Hybrid Mode: Mixed parallel and imperative execution

        The execution mode is determined by the book's execution_mode field.
        Default mode is 'dag' if not specified.

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Aggregated execution results

        Raises:
            ValueError: If execution_mode is not recognized
        """
        notebook_item = self.item
        execution_mode = getattr(notebook_item, "execution_mode", "dag")

        # Add book execution start fragment
        pipeline_item_instance.add_fragment(
            type="execution",
            content=f"Starting book execution in {execution_mode} mode",
            metadata={
                "step": "book_start",
                "notebook_item_id": notebook_item.id,
                "execution_mode": execution_mode,
                "cell_count": len(notebook_item.cells or []),
            },
        )

        try:
            # Dispatch based on execution mode
            if execution_mode == "dag":
                result = await self._run_book_dag_mode(pipeline_item_instance)
            elif execution_mode == "script":
                result = await self._run_book_script_mode(pipeline_item_instance)
            elif execution_mode == "hybrid":
                result = await self._run_book_hybrid_mode(pipeline_item_instance)
            else:
                raise ValueError(f"Unknown execution_mode: {execution_mode}")

            # Add book completion fragment
            pipeline_item_instance.add_fragment(
                type="execution",
                content=f"Book execution completed in {execution_mode} mode",
                metadata={
                    "step": "book_complete",
                    "notebook_item_id": notebook_item.id,
                    "execution_mode": execution_mode,
                },
            )

            return result

        except Exception as e:
            logger.error(
                f"Book execution failed for {notebook_item.id} in {execution_mode} mode: {e}",
                exc_info=True,
            )
            raise

    async def _run_book_dag_mode(self, pipeline_item_instance: "PipelineItem") -> Dict[str, Any]:
        """
        Execute book in DAG mode (parallel execution).

        This mode:
        - Executes cells in parallel where possible
        - Respects dependencies defined in the DAG
        - Uses graph orchestrator for execution

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Dictionary with book_id, cells_executed, and results
        """
        notebook_item = self.item

        # For now, fallback to sequential execution
        # TODO: Implement actual DAG orchestrator in future phase
        logger.info("DAG mode for %s - using sequential fallback", notebook_item.id)
        return await self._execute_cells_sequentially(pipeline_item_instance)

    async def _run_book_script_mode(self, pipeline_item_instance: "PipelineItem") -> Dict[str, Any]:
        """
        Execute book in Script mode (imperative execution).

        This mode:
        - Executes cells sequentially in order
        - Allows complex logic (loops, conditionals)
        - Uses book's execute() method if defined

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Dictionary with book_id, cells_executed, and results
        """
        notebook_item = self.item

        logger.info("Script mode for %s - sequential execution", notebook_item.id)
        return await self._execute_cells_sequentially(pipeline_item_instance)

    async def _run_book_hybrid_mode(self, pipeline_item_instance: "PipelineItem") -> Dict[str, Any]:
        """
        Execute book in Hybrid mode (mixed execution).

        This mode:
        - Combines parallel and sequential execution
        - Uses book's logic to determine execution order
        - Provides maximum flexibility

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Dictionary with book_id, cells_executed, and results
        """
        notebook_item = self.item

        logger.info("Hybrid mode for %s - using sequential fallback", notebook_item.id)
        return await self._execute_cells_sequentially(pipeline_item_instance)

    async def _execute_cells_sequentially(
        self, pipeline_item_instance: "PipelineItem"
    ) -> Dict[str, Any]:
        """
        Execute cells sequentially with hierarchical tracing.

        This method:
        1. Iterates through book's cells
        2. Creates adapter for each cell
        3. Executes cell and captures result
        4. Injects book ID into child execution fragments (executed_by)
        5. Checks for AWAITING_REVIEW status and pauses if needed
        6. Aggregates results

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Dictionary with book_id, cells_executed, and results
        """
        from ...database import db
        from ..content import Cell
        from ...core.models import PipelineItem

        notebook_item = self.item
        cells = notebook_item.cells or []
        results = []

        for cell_id in cells:
            # Retrieve the cell
            cell = db.find_one("cells", cell_id, Cell, is_canonical=False)

            if not cell:
                pipeline_item_instance.add_fragment(
                    type="warning",
                    content=f"Cell {cell_id} not found, skipping",
                    metadata={"cell_id": cell_id},
                )
                continue

            # Create a PipelineItem for the cell execution
            cell_pipeline_item = PipelineItem(
                notebook_item_id=cell.id,
                notebook_item_data=cell,
                cell_id=cell.id,
                cell_type_id=cell.notebook_item_type_id,
                assignee_id=cell.assignee_id,
            )

            # Execute the cell using unified adapter
            cell_adapter = NotebookItemAdapter(
                item=cell, pipeline_context_name="cell_execution_from_book"
            )

            try:
                result = await cell_adapter.execute_in_pipeline(cell_pipeline_item)

                # Inject executed_by into child fragments for hierarchical tracing
                self._inject_executed_by(result, notebook_item.id)

                results.append(result)

                # Record cell execution in book's fragment log
                pipeline_item_instance.add_fragment(
                    type="execution",
                    content=f"Completed cell {cell_id}",
                    metadata={
                        "cell_id": cell_id,
                        "status": result.status,
                        "executed_by": cell_id,
                    },
                )

                # Check if we should pause for review
                if result.status == "AWAITING_REVIEW":
                    logger.info("Cell %s requires review, pausing book execution", cell_id)
                    pipeline_item_instance.update_status("AWAITING_REVIEW")
                    break

            except Exception as e:
                logger.error("Cell %s execution failed: %s", cell_id, e, exc_info=True)

                pipeline_item_instance.add_fragment(
                    type="error",
                    content=f"Cell {cell_id} execution failed: {str(e)}",
                    metadata={"cell_id": cell_id},
                )

                # Continue with next cell or raise depending on strategy
                # For now, we raise to stop execution on first error
                raise

        return {
            "book_id": notebook_item.id,
            "cells_executed": len(results),
            "results": results,
        }

    def _inject_executed_by(
        self, pipeline_item: "PipelineItem", parent_book_id: str
    ) -> None:
        """
        Inject parent book ID into child ExecutionFragments for hierarchical tracing.

        IMPORTANT: Only ExecutionFragment objects have the executed_by field.
        Generic Fragment objects are intentionally left untouched - they remain flexible
        data containers without execution semantics.

        This implements hierarchical tracing by setting the executed_by field
        in ExecutionFragment objects to track which book executed which cells.

        Args:
            pipeline_item: Child PipelineItem with fragments to update
            parent_book_id: ID of the parent book
        """
        # Update fragments if they are ExecutionFragment objects
        for fragment in pipeline_item.fragments:
            if isinstance(fragment, dict):
                # Check if this is an ExecutionFragment dict (has step field and executed_by)
                if "step" in fragment and "executed_by" in fragment:
                    # This is an ExecutionFragment dict, update executed_by
                    fragment["executed_by"] = parent_book_id
                # Generic Fragment dicts are left untouched - they don't have executed_by field
            elif hasattr(fragment, "executed_by"):
                # It's an ExecutionFragment object, set executed_by
                fragment.executed_by = parent_book_id

        logger.debug(
            "Injected executed_by=%s into ExecutionFragments in %s",
            parent_book_id, pipeline_item.notebook_item_id
        )


# Rebuild models to resolve forward references
try:
    from ...core.models import NotebookItem
    UnifiedNotebookItemAdapter.model_rebuild()
except Exception:
    pass  # Ignore if already built or dependencies not available
