#!/usr/bin/env python3
"""
LangGraph Workflow for Document Ingestion Pipeline - BACKWARD COMPATIBILITY SHIM

⚠️ DEPRECATED: This file is now a backward compatibility shim.
   The ingestion workflow has been modularized for maintainability.

   New location: backend/app/workflows/ingestion/

Please update imports to:
    from app.workflows.ingestion import execute, get_workflow_graph

This shim will remain for backward compatibility but may be removed in future versions.

The workflow includes:
1. URL downloading (if file_path is a URL) or direct file access
2. Preprocessing and chunking of source documents
3. Embedding generation and vector store indexing
4. Context and fragment updates for auditability

Usage:
    This graph is referenced by the ingestion-issue cell type via default_refs['workflow_graph'].
    The orchestrator will dynamically load and execute this graph when
    processing ingestion cells.

    New importlib-based entry point:
        from app.workflows import ingestion_graph
        result_item = ingestion_graph.execute(pipeline_item)
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.models import NotebookItem, PipelineItem

# Re-export all public API from the new modular structure
# Using absolute import to support dynamic module loading via importlib
from app.workflows.ingestion import (
    IngestionState,
    build_ingestion_graph,
    download_from_url,
    execute,
    finalize_ingestion,
    generate_embeddings,
    get_workflow_graph,
    initialize_ingestion,
    is_url,
    preprocess_and_chunk,
    resolve_file_path,
    run_script,
    should_continue_ingestion,
)

# Setup logging
logger = logging.getLogger(__name__)
logger.info(
    "Loading ingestion_graph via backward compatibility shim. "
    "Consider updating imports to: from app.workflows.ingestion import execute"
)


def execute_workflow(
    workflow_path: str,
    pipeline_item: "PipelineItem",
    notebook_item_data: "NotebookItem",
) -> "PipelineItem":
    """
    Execute a generic workflow from a given path.

    This function serves as a generic workflow executor that can be invoked
    by NotebookItemAdapter implementations. It dynamically loads and executes
    the workflow specified by workflow_path.

    Args:
        workflow_path: Path or reference to the workflow graph module
                      (e.g., 'app.workflows.ingestion_graph')
        pipeline_item: PipelineItem managing execution state
        notebook_item_data: The NotebookItem (Cell or Livro) being executed

    Returns:
        Updated PipelineItem with execution results

    Raises:
        Exception: If workflow execution fails
    """
    logger.info("Executing workflow from path: %s", workflow_path)

    # For now, default to the ingestion workflow
    # In the future, this could dynamically load different workflows
    # based on the workflow_path

    try:
        # Ensure notebook_item_data is set in pipeline_item
        if pipeline_item.notebook_item_data is None:
            pipeline_item.notebook_item_data = notebook_item_data

        # Add fragment about workflow execution
        pipeline_item.add_fragment(
            type="execucao",
            content=f"Starting workflow execution: {workflow_path}",
            metadata={"workflow_path": workflow_path},
        )

        # Execute the ingestion workflow
        # This is the default behavior for now
        result_item = execute(pipeline_item)

        # Add completion fragment
        result_item.add_fragment(
            type="execucao",
            content=f"Workflow execution completed: {workflow_path}",
            metadata={"workflow_path": workflow_path},
        )

        return result_item

    except Exception as e:
        logger.error("Workflow execution failed for %s: %s", workflow_path, e)
        pipeline_item.set_error(f"Workflow execution failed: {str(e)}")
        raise


# Define exports for backward compatibility
__all__ = [
    "execute",
    "get_workflow_graph",
    "build_ingestion_graph",
    "IngestionState",
    "initialize_ingestion",
    "resolve_file_path",
    "preprocess_and_chunk",
    "generate_embeddings",
    "finalize_ingestion",
    "should_continue_ingestion",
    "is_url",
    "download_from_url",
    "run_script",
    "execute_workflow",
]
