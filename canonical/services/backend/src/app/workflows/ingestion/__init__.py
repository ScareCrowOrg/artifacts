"""
Document Ingestion Workflow Module

This module provides the LangGraph-based workflow for document ingestion
into the ScareVerse RAG system.

The workflow is now modularized for maintainability:
- ingestion_orchestrator: Main PipelineItem-based execution entry point
- ingestion_graph_builder: LangGraph construction and configuration
- ingestion_node_types: Individual workflow node implementations
- ingestion_workflow_utils: Shared utility functions

Public API (backward compatible):
- execute(item: PipelineItem) -> PipelineItem: Main execution entry point
- get_workflow_graph() -> StateGraph: Get compiled workflow graph
- build_ingestion_graph() -> StateGraph: Build workflow graph

Usage:
    from app.workflows.ingestion import execute
    result = execute(pipeline_item)

    # Or for dynamic loading:
    from app.workflows.ingestion import get_workflow_graph
    graph = get_workflow_graph()
"""

# Import from submodules to maintain public API
from .ingestion_graph_builder import build_ingestion_graph, get_workflow_graph
from .ingestion_node_types import (
    IngestionState,
    finalize_ingestion,
    generate_embeddings,
    initialize_ingestion,
    preprocess_and_chunk,
    resolve_file_path,
    should_continue_ingestion,
)
from .ingestion_orchestrator import execute
from .ingestion_workflow_utils import download_from_url, is_url, run_script

# Define public API exports
__all__ = [
    # Main entry points (most commonly used)
    "execute",
    "get_workflow_graph",
    "build_ingestion_graph",
    # Node functions (for advanced usage)
    "IngestionState",
    "initialize_ingestion",
    "resolve_file_path",
    "preprocess_and_chunk",
    "generate_embeddings",
    "finalize_ingestion",
    "should_continue_ingestion",
    # Utility functions (for advanced usage)
    "is_url",
    "download_from_url",
    "run_script",
]
