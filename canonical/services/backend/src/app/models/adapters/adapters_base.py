"""
Base Adapter for Notebook Items

This module implements the Adapter pattern for notebook items, providing
execution logic while keeping the pure data models clean and focused.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from pydantic import BaseModel, Field

from ..interfaces import IPipelineExecutable

if TYPE_CHECKING:
    from ...core.models import NotebookItem, PipelineItem


logger = logging.getLogger(__name__)


class NotebookItemAdapter(IPipelineExecutable, BaseModel):
    """
    Base adapter class for notebook items.

    This class implements the Adapter pattern, wrapping a pure NotebookItem
    data model and providing execution logic via the IPipelineExecutable interface.

    The adapter composes (not inherits) a NotebookItem, maintaining separation
    of concerns between data representation and execution logic.

    Concrete adapters (CellAdapter, BookAdapter) extend this base class to
    provide specific execution behavior for different types of notebook items.
    """

    # Composition: wrap a NotebookItem (stored internally without leading underscore)
    item: "NotebookItem" = Field(..., description="The wrapped NotebookItem")

    # Pipeline context identifier
    pipeline_context_name: str = Field(
        ...,
        description="Name of the pipeline context for this adapter (e.g., 'cell_execution', 'book_orchestration')",
    )

    class Config:
        arbitrary_types_allowed = True

    def get_references(self) -> Dict[str, List[str]]:
        """
        Get file references from the wrapped notebook item.

        Returns:
            Dictionary mapping reference types to file paths
        """
        return self.item.refs

    def get_pipeline_context_name(self) -> str:
        """
        Get the pipeline context name for this adapter.

        Returns:
            Pipeline context identifier string
        """
        return self.pipeline_context_name

    def get_notebook_item(self) -> "NotebookItem":
        """
        Get the wrapped notebook item.

        Returns:
            The underlying NotebookItem instance
        """
        return self.item

    async def execute_in_pipeline(self, pipeline_item_instance: "PipelineItem") -> Any:
        """
        Execute the notebook item in a pipeline.

        Enhanced implementation with dynamic workflow loading:
        1. Fetches NotebookItemType to get default_refs
        2. Determines workflow_path with priority: instance refs > type default_refs
        3. Respects allow_instance_override_refs flag
        4. Dynamically loads workflow module using importlib
        5. Executes workflow by passing PipelineItem and NotebookItem instances directly

        Concrete adapters (CellAdapter, BookAdapter) can override this for
        specific behavior or call super().execute_in_pipeline() to use this default.

        Args:
            pipeline_item_instance: PipelineItem managing execution state

        Returns:
            Execution result (PipelineItem or custom result)
        """
        import importlib

        # Get the wrapped notebook item
        notebook_item = self.item

        # Add execution start fragment
        pipeline_item_instance.add_fragment(
            type="execution",
            content=f"Starting execution for notebook item {notebook_item.id}",
            metadata={"step": "start", "notebook_item_id": notebook_item.id},
        )

        # Update pipeline status
        pipeline_item_instance.update_status("running")

        # Determine workflow path with priority
        workflow_path = None
        notebook_item_type = None

        # Try to fetch NotebookItemType if the item has notebook_item_type_id
        notebook_item_type_id = getattr(notebook_item, "notebook_item_type_id", None)

        if notebook_item_type_id:
            try:
                from ...database import db
                from ..content import NotebookItemType

                # Fetch the NotebookItemType
                notebook_item_type = db.find_one(
                    "notebook_item_types",
                    notebook_item_type_id,
                    NotebookItemType,
                    is_canonical=True,
                )

                if notebook_item_type:
                    logger.info("Found NotebookItemType: %s", notebook_item_type.name)

                    # Check if instance overrides are allowed
                    if notebook_item_type.allow_instance_override_refs:
                        # Priority: instance refs > type default_refs
                        instance_workflow_refs = notebook_item.refs.get(
                            "workflow_graph", []
                        )
                        if instance_workflow_refs:
                            workflow_path = instance_workflow_refs[0]
                            logger.info("Using instance workflow ref: %s", workflow_path)
                        else:
                            # Fallback to type default_refs
                            type_workflow_refs = notebook_item_type.default_refs.get(
                                "workflow_graph", []
                            )
                            if type_workflow_refs:
                                workflow_path = type_workflow_refs[0]
                                logger.info("Using type default workflow ref: %s", workflow_path)
                    else:
                        # Overrides not allowed, use type default_refs only
                        type_workflow_refs = notebook_item_type.default_refs.get(
                            "workflow_graph", []
                        )
                        if type_workflow_refs:
                            workflow_path = type_workflow_refs[0]
                            logger.info("Using type default workflow ref (overrides disabled): %s", workflow_path)
                else:
                    logger.warning("NotebookItemType %s not found", notebook_item_type_id)
            except Exception as e:
                logger.error("Error fetching NotebookItemType: %s", e)

        # If no type or workflow not found via type, fallback to instance refs
        if not workflow_path:
            instance_workflow_refs = notebook_item.refs.get("workflow_graph", [])
            if instance_workflow_refs:
                workflow_path = instance_workflow_refs[0]
                logger.info("Using instance workflow ref (no type or type had no workflow): %s", workflow_path)

        # Execute workflow if found
        if workflow_path:
            try:
                # Dynamic workflow loading using importlib
                logger.info("Loading workflow dynamically: %s", workflow_path)

                # Try to import as module path first
                try:
                    workflow_module = importlib.import_module(workflow_path)
                    logger.info("Successfully imported workflow module: %s", workflow_path)
                except ModuleNotFoundError:
                    # If not a module path, try treating as file path
                    logger.warning("Could not import as module path, trying as file path: %s", workflow_path)

                    # For now, fallback to the default ingestion workflow
                    from ...workflows.ingestion_graph import execute_workflow

                    result_item = execute_workflow(
                        workflow_path=workflow_path,
                        pipeline_item=pipeline_item_instance,
                        notebook_item_data=notebook_item,
                    )

                    # Add completion fragment
                    result_item.add_fragment(
                        type="execution",
                        content=f"Workflow execution completed successfully for {notebook_item.id}",
                        metadata={
                            "step": "complete",
                            "notebook_item_id": notebook_item.id,
                        },
                    )

                    result_item.update_status("completed")

                    # Persist execution record to notebook_item.fragments
                    await self._persist_execution_record(result_item, notebook_item)

                    return result_item

                # If module loaded successfully, look for execute_workflow function
                if hasattr(workflow_module, "execute_workflow"):
                    execute_fn = workflow_module.execute_workflow

                    # Execute workflow with direct object passing (no stdin/stdout)
                    result_item = execute_fn(
                        workflow_path=workflow_path,
                        pipeline_item=pipeline_item_instance,
                        notebook_item_data=notebook_item,
                    )

                    # Add completion fragment
                    result_item.add_fragment(
                        type="execution",
                        content=f"Workflow execution completed successfully for {notebook_item.id}",
                        metadata={
                            "step": "complete",
                            "notebook_item_id": notebook_item.id,
                        },
                    )

                    result_item.update_status("completed")

                    # Persist execution record to notebook_item.fragments
                    await self._persist_execution_record(result_item, notebook_item)

                    return result_item
                elif hasattr(workflow_module, "execute"):
                    # Alternative: execute function
                    execute_fn = workflow_module.execute

                    result_item = execute_fn(pipeline_item_instance)

                    result_item.add_fragment(
                        type="execution",
                        content=f"Workflow execution completed successfully for {notebook_item.id}",
                        metadata={
                            "step": "complete",
                            "notebook_item_id": notebook_item.id,
                        },
                    )

                    result_item.update_status("completed")

                    # Persist execution record to notebook_item.fragments
                    await self._persist_execution_record(result_item, notebook_item)

                    return result_item
                else:
                    raise AttributeError(
                        f"Workflow module {workflow_path} does not have 'execute_workflow' or 'execute' function"
                    )

            except Exception as e:
                logger.error("Workflow execution failed: %s", e)
                pipeline_item_instance.set_error(str(e))

                # Add error fragment to the notebook item itself for traceability
                notebook_item.fragments.append(
                    {
                        "tipo": "error",
                        "conteudo": f"Workflow execution failed: {str(e)}",
                        "metadata": {"notebook_item_id": notebook_item.id},
                    }
                )

                # Persist execution record even on error for traceability
                await self._persist_execution_record(
                    pipeline_item_instance, notebook_item
                )

                raise
        else:
            # No workflow_graph found - mark as completed/skipped
            logger.info("No workflow_graph reference found for %s, marking as skipped", notebook_item.id)

            pipeline_item_instance.add_fragment(
                type="execution",
                content=f"No workflow_graph reference found for notebook item {notebook_item.id}. Execution skipped.",
                metadata={"step": "skipped", "notebook_item_id": notebook_item.id},
            )

            pipeline_item_instance.update_status("completed")

            # Persist execution record to notebook_item.fragments
            await self._persist_execution_record(pipeline_item_instance, notebook_item)

            return pipeline_item_instance

    async def _persist_execution_record(
        self, pipeline_item: "PipelineItem", notebook_item: "NotebookItem"
    ) -> None:
        """
        Create an ExecutionRecord from PipelineItem and persist it to NotebookItem.fragments.

        This method:
        1. Creates an ExecutionRecord DTO from the completed PipelineItem
        2. Converts it to dict with type marker
        3. Appends to notebook_item.fragments
        4. Persists the updated notebook_item to database

        Args:
            pipeline_item: Completed PipelineItem with execution results
            notebook_item: NotebookItem to update with execution record
        """
        from ...database import db
        from ...models.execution_models import ExecutionRecord

        try:
            # Create ExecutionRecord DTO from PipelineItem
            execution_record = ExecutionRecord(
                pipeline_item_id=pipeline_item.id,
                status=pipeline_item.status,
                assignee_id=pipeline_item.assignee_id,
                created_at=pipeline_item.created_at,
                updated_at=pipeline_item.updated_at,
                fragments=pipeline_item.fragments,
                error=pipeline_item.error,
                initial_data_snapshot=(
                    notebook_item.initial_data.copy()
                    if notebook_item.initial_data
                    else None
                ),
            )

            # Convert to dict with type marker (already has type="execution_record" by default)
            execution_record_dict = execution_record.model_dump(mode="json")

            # Append to notebook_item.fragments
            notebook_item.fragments.append(execution_record_dict)

            # Update notebook_item timestamp
            notebook_item.updated_at = pipeline_item.updated_at

            # Persist the updated notebook_item
            # Determine collection name based on notebook_item type
            collection = "cells"  # Default to cells
            if hasattr(notebook_item, "cells"):
                # It's a Livro (Book)
                collection = "books"

            # Determine if canonical based on notebook_item attributes
            is_canonical = False
            user_id = notebook_item.assignee_id

            # Update the document
            success = db.update(
                collection=collection,
                doc_id=notebook_item.id,
                updates={
                    "fragments": [
                        f if isinstance(f, str) else f for f in notebook_item.fragments
                    ],
                    "updated_at": notebook_item.updated_at.isoformat(),
                },
                user_id=user_id,
                is_canonical=is_canonical,
            )

            if success:
                logger.info(
                    "Successfully persisted execution record %s to %s in %s",
                    pipeline_item.id, notebook_item.id, collection
                )
            else:
                logger.warning(
                    "Failed to persist execution record %s to %s - document may not exist in database",
                    pipeline_item.id, notebook_item.id
                )

        except Exception as e:
            logger.error(
                "Error persisting execution record %s to %s: %s",
                pipeline_item.id, notebook_item.id, e, exc_info=True
            )
            # Don't raise - we don't want to fail the execution just because
            # we couldn't persist the record
