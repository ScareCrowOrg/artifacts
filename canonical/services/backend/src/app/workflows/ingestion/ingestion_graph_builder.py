#!/usr/bin/env python3
"""
LangGraph Builder for Document Ingestion Workflow

This module constructs the LangGraph workflow for document ingestion.
It assembles the nodes and defines the edges that connect them.

The graph includes:
1. Node initialization and configuration
2. Conditional edge routing
3. Graph compilation and export

Functions:
- build_ingestion_graph: Construct and compile the graph
- get_workflow_graph: Entry point for dynamic loading
"""

import logging

from langgraph.graph import END, StateGraph

from app.core.models import NotebookItem, PipelineItem

from .ingestion_node_types import (
    IngestionState,
    finalize_ingestion,
    generate_embeddings,
    initialize_ingestion,
    preprocess_and_chunk,
    resolve_file_path,
    should_continue_ingestion,
)

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# Graph Builder
# ============================================================================


def build_ingestion_graph() -> StateGraph:
    """
    Build the LangGraph workflow for document ingestion.

    Returns:
        Compiled StateGraph for ingestion workflow
    """
    workflow = StateGraph(IngestionState)

    # Add nodes
    workflow.add_node("initialize", initialize_ingestion)
    workflow.add_node("resolve", resolve_file_path)
    workflow.add_node("preprocess", preprocess_and_chunk)
    workflow.add_node("embed", generate_embeddings)
    workflow.add_node("finalize", finalize_ingestion)

    # Set entry point
    workflow.set_entry_point("initialize")

    # Add edges
    workflow.add_conditional_edges(
        "initialize", should_continue_ingestion, {"resolve": "resolve", "end": END}
    )

    workflow.add_conditional_edges(
        "resolve", should_continue_ingestion, {"preprocess": "preprocess", "end": END}
    )

    workflow.add_conditional_edges(
        "preprocess", should_continue_ingestion, {"embed": "embed", "end": END}
    )

    workflow.add_conditional_edges(
        "embed", should_continue_ingestion, {"finalize": "finalize", "end": END}
    )

    workflow.add_edge("finalize", END)

    return workflow.compile()


# ============================================================================
# Entry Point for Dynamic Loading
# ============================================================================


def get_workflow_graph():
    """
    Entry point for dynamic graph loading by the orchestrator.

    Returns:
        Compiled LangGraph workflow
    """
    return build_ingestion_graph()


# For testing
if __name__ == "__main__":
    # Example usage with PipelineItem integration (v2.1)
    # Create a NotebookItem (Cell) for testing
    notebook_item = NotebookItem(
        assignee_id="test-agent",
        refs={"workflow_graph": ["backend/app/workflows/ingestion_graph.py"]},
        initial_data={
            "file_path": "https://example.com/document.md",
            "file_type": "markdown",
            "document_id": "test-doc-456",
        },
    )

    # Create PipelineItem for execution tracking
    pipeline_item = PipelineItem(
        notebook_item_id=notebook_item.id,
        notebook_item_data=notebook_item,
        cell_id=notebook_item.id,
        cell_type_id="ingestion-issue",
        assignee_id=notebook_item.assignee_id,
        data={
            "file_path": "https://example.com/document.md",
            "file_type": "markdown",
            "document_id": "test-doc-456",
        },
    )

    # Build graph
    graph = build_ingestion_graph()

    # Example initial state WITH pipeline_item (v2.1 - enables fragment tracking)
    initial_state: IngestionState = {
        "cell_id": pipeline_item.cell_id,
        "cell_data": pipeline_item.data,
        "agent_data": {"ia_model_id": "mistral"},
        "file_path": "",
        "file_type": "",
        "document_id": "",
        "local_file_path": None,
        "chunks_path": None,
        "doc_chunks_path": None,
        "code_chunks_path": None,
        "embedding_status": None,
        "fragments": [],
        "context": {},
        "error": None,
        "completed": False,
        "pipeline_item": pipeline_item,  # NEW (v2.1): Enables persistent fragment tracking
    }

    print("Ingestion graph structure:")
    print(f"Nodes: {list(graph.get_graph().nodes())}")
    print(f"Edges: {list(graph.get_graph().edges())}")
    print(
        f"\nPipelineItem integration: {'Enabled' if initial_state.get('pipeline_item') else 'Disabled'}"
    )
    print("Note: With PipelineItem, all nodes will persist fragments to the cell")
