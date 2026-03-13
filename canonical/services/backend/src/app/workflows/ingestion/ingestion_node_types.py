#!/usr/bin/env python3
"""
Workflow Node Implementations for Document Ingestion

This module contains the individual node functions used in the LangGraph
workflow for document ingestion. Each node represents a step in the
ingestion pipeline.

Node Functions:
- initialize_ingestion: Initialize workflow state
- resolve_file_path: Download from URL or use local path
- preprocess_and_chunk: Preprocess and chunk documents
- generate_embeddings: Generate and store embeddings
- finalize_ingestion: Complete workflow and add summary
- should_continue_ingestion: Routing logic for conditional edges
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from app.core.models import PipelineItem

from .ingestion_workflow_utils import download_from_url, is_url, run_script

# TYPE_CHECKING is used to avoid circular imports at runtime while still
# providing type hints for static analysis tools. PipelineItem is only
# needed for type checking, not at runtime.
# (Now imported at runtime for LangGraph compatibility)

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# State Definition
# ============================================================================


class IngestionState(TypedDict):
    """
    State for the ingestion workflow.

    This TypedDict defines the structure of the state object that flows
    through the LangGraph workflow. It includes cell context, workflow data,
    step outputs, and execution tracking.

    **New in v2.1**: The `pipeline_item` field allows nodes to directly
    access the PipelineItem for fragment tracking and status updates,
    ensuring complete traceability of the ingestion process.
    """

    # Cell context
    cell_id: str
    cell_data: Dict[str, Any]
    agent_data: Dict[str, Any]

    # Workflow data
    file_path: str  # Can be local path or URL
    file_type: str
    document_id: str
    local_file_path: Optional[str]  # Local path after URL download

    # Step outputs
    chunks_path: Optional[
        str
    ]  # DEPRECATED (v2.0): Use doc_chunks_path or code_chunks_path instead
    doc_chunks_path: Optional[str]  # Path to documentation chunks JSON
    code_chunks_path: Optional[str]  # Path to code chunks JSON
    embedding_status: Optional[str]

    # Execution tracking
    fragments: List[Dict[str, Any]]
    context: Dict[str, Any]
    error: Optional[str]
    completed: bool

    # NEW (v2.1): PipelineItem reference for direct fragment tracking
    # Optional to maintain backward compatibility with existing code
    pipeline_item: Optional["PipelineItem"]


# ============================================================================
# Workflow Nodes
# ============================================================================


def initialize_ingestion(state: IngestionState) -> IngestionState:
    """
    Initialize the ingestion workflow.

    This node extracts relevant data from the cell and prepares the state
    for subsequent processing steps.

    **New in v2.1**: Updates cell status to 'running' and adds fragments
    to the persistent cell via PipelineItem if available.
    """
    logger.info("Initializing ingestion for cell: %s", state['cell_id'])

    # Get PipelineItem reference if available
    pipeline_item = state.get("pipeline_item")

    # Extract file information from cell data
    cell_data = state.get("cell_data", {})
    state["file_path"] = cell_data.get("file_path", "")
    state["file_type"] = cell_data.get("file_type", "")
    state["document_id"] = cell_data.get("document_id", str(uuid.uuid4()))

    # Initialize tracking structures
    state["fragments"] = []
    state["context"] = {
        "workflow": "ingestion",
        "started_at": datetime.utcnow().isoformat(),
        "steps_completed": [],
    }
    state["local_file_path"] = None
    state["chunks_path"] = None
    state["doc_chunks_path"] = None
    state["code_chunks_path"] = None
    state["embedding_status"] = None
    state["error"] = None
    state["completed"] = False

    # NEW (v2.1): Update cell status to 'running' via PipelineItem
    if pipeline_item:
        pipeline_item.update_status("running")

        # NEW (v2.1): Add fragment to persistent cell (not just state)
        pipeline_item.add_fragment(
            type="execution",
            content=f"Ingestion workflow initialized for document: {state['document_id']}",
            metadata={
                "step": "initialize",
                "file_path": state["file_path"],
                "file_type": state["file_type"],
                "workflow": "ingestion",
            },
        )
        logger.debug("Updated cell %s status to 'running' and added initialization fragment", state['cell_id'])

    # Keep backward compatibility: also add to state fragments
    state["fragments"].append(
        {
            "tipo": "execucao",
            "conteudo": f"Ingestion workflow initialized for document: {state['document_id']}",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    logger.info("Ingestion initialized for: %s (%s)", state['file_path'], state['file_type'])
    return state


def resolve_file_path(state: IngestionState) -> IngestionState:
    """
    Resolve the file path - download from URL if needed.

    This node handles both local file paths and URLs.
    If file_path is a URL, it downloads the content to a local file.

    **New in v2.1**: Adds fragments to persistent cell and updates status
    on errors via PipelineItem if available.
    """
    file_path = state["file_path"]
    pipeline_item = state.get("pipeline_item")

    if is_url(file_path):
        logger.info("Detected URL input: %s", file_path)

        try:
            # Download from URL
            local_path = download_from_url(file_path)
            state["local_file_path"] = local_path

            # Update context
            state["context"]["steps_completed"].append("download_from_url")
            state["context"]["original_url"] = file_path
            state["context"]["downloaded_to"] = local_path

            # Add fragment to state (backward compat)
            state["fragments"].append(
                {
                    "tipo": "execucao",
                    "conteudo": f"Downloaded file from URL: {file_path} to {local_path}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # NEW (v2.1): Add fragment to persistent cell
            if pipeline_item:
                pipeline_item.add_fragment(
                    type="execution",
                    content=f"Downloaded file from URL to {local_path}",
                    metadata={
                        "step": "resolve_file_path",
                        "original_url": file_path,
                        "local_path": local_path,
                        "workflow": "ingestion",
                    },
                )

            logger.info("File downloaded successfully to: %s", local_path)

        except Exception as e:
            error_msg = f"Failed to download from URL: {str(e)}"
            state["error"] = error_msg
            logger.error(error_msg)

            # Add error fragment to state
            state["fragments"].append(
                {
                    "tipo": "execucao",
                    "conteudo": f"Download error: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # NEW (v2.1): Update status to error and add error fragment to cell
            if pipeline_item:
                pipeline_item.set_error(error_msg)
                logger.debug("Updated cell %s status to 'error' due to download failure", state['cell_id'])
    else:
        # Local file path - use directly
        logger.info("Using local file path: %s", file_path)
        state["local_file_path"] = file_path

        state["context"]["steps_completed"].append("resolve_local_path")

        # Add fragment to state
        state["fragments"].append(
            {
                "tipo": "execucao",
                "conteudo": f"Using local file path: {file_path}",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # NEW (v2.1): Add fragment to persistent cell
        if pipeline_item:
            pipeline_item.add_fragment(
                type="execution",
                content=f"Using local file path: {file_path}",
                metadata={
                    "step": "resolve_file_path",
                    "local_path": file_path,
                    "workflow": "ingestion",
                },
            )

    return state


def preprocess_and_chunk(state: IngestionState) -> IngestionState:
    """
    Preprocess and chunk the source document.

    This node calls the preprocess_and_chunk.py script to:
    - Load the source file (from local_file_path)
    - Apply text preprocessing
    - Split into chunks
    - Save chunks to separate JSON files (doc and code)

    The script outputs a JSON object with doc_chunks_path and code_chunks_path.

    **New in v2.1**: Adds progress and error fragments to persistent cell
    via PipelineItem if available.
    """
    file_to_process = state["local_file_path"]
    pipeline_item = state.get("pipeline_item")
    logger.info("Starting preprocessing and chunking for: %s", file_to_process)

    # Prepare script inputs
    inputs = {
        "file_path": file_to_process,
        "file_type": state["file_type"],
        "document_id": state["document_id"],
        "output_dir": "/tmp",
    }

    # Execute preprocessing script
    result = run_script("scripts/ingestion/preprocess_and_chunk.py", inputs)

    if not result["success"]:
        error_msg = f"Preprocessing failed: {result['stderr']}"
        state["error"] = error_msg
        logger.error(error_msg)

        # Add error fragment to state
        state["fragments"].append(
            {
                "tipo": "execucao",
                "conteudo": f"Preprocessing error: {result['stderr']}",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # NEW (v2.1): Update status to error and add error fragment to cell
        if pipeline_item:
            pipeline_item.set_error(error_msg)
            logger.debug("Updated cell %s status to 'error' due to preprocessing failure", state['cell_id'])

        return state

    # Parse JSON output from the script
    # The script outputs: {"doc_chunks_path": "...", "code_chunks_path": "..."}
    stdout_lines = result["stdout"].strip().split("\n")
    if stdout_lines:
        try:
            # Get the last line which contains the JSON output
            chunks_info = json.loads(stdout_lines[-1])

            state["doc_chunks_path"] = chunks_info.get("doc_chunks_path")
            state["code_chunks_path"] = chunks_info.get("code_chunks_path")

            # Keep chunks_path for backward compatibility (prefer code over doc)
            if state["code_chunks_path"]:
                state["chunks_path"] = state["code_chunks_path"]
            elif state["doc_chunks_path"]:
                state["chunks_path"] = state["doc_chunks_path"]

            logger.info("Doc chunks path: %s", state['doc_chunks_path'])
            logger.info("Code chunks path: %s", state['code_chunks_path'])

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse chunks output JSON: {e}. Output was: {stdout_lines[-1]}"
            state["error"] = error_msg
            logger.error(error_msg)

            # Add error fragment to state
            state["fragments"].append(
                {
                    "tipo": "execucao",
                    "conteudo": f"JSON parsing error: {state['error']}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # NEW (v2.1): Update status to error
            if pipeline_item:
                pipeline_item.set_error(error_msg)
                logger.debug("Updated cell %s status to 'error' due to JSON parsing failure", state['cell_id'])

            return state

    # Update context
    state["context"]["steps_completed"].append("preprocess_and_chunk")
    state["context"]["doc_chunks_path"] = state["doc_chunks_path"]
    state["context"]["code_chunks_path"] = state["code_chunks_path"]

    # Add success fragment
    chunk_summary = []
    if state["doc_chunks_path"]:
        chunk_summary.append(f"doc chunks: {state['doc_chunks_path']}")
    if state["code_chunks_path"]:
        chunk_summary.append(f"code chunks: {state['code_chunks_path']}")

    fragment_content = (
        f"Document preprocessed and chunked successfully. {', '.join(chunk_summary)}"
    )

    # Add to state fragments
    state["fragments"].append(
        {
            "tipo": "execucao",
            "conteudo": fragment_content,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    # NEW (v2.1): Add fragment to persistent cell
    if pipeline_item:
        pipeline_item.add_fragment(
            type="execution",
            content=fragment_content,
            metadata={
                "step": "preprocess_and_chunk",
                "doc_chunks_path": state["doc_chunks_path"],
                "code_chunks_path": state["code_chunks_path"],
                "workflow": "ingestion",
            },
        )

    logger.info("Preprocessing and chunking completed successfully")
    return state


def generate_embeddings(state: IngestionState) -> IngestionState:
    """
    Generate embeddings and store in vector database.

    This node calls the generate_embeddings_and_store.py script to:
    - Load chunks from JSON (handles both doc and code chunks separately)
    - Generate embeddings using the specified model
    - Store embeddings in ChromaDB

    The script is called once for doc chunks and once for code chunks if they exist.

    **New in v2.1**: Adds result and error fragments to persistent cell
    via PipelineItem if available.
    """
    # Get embedding model from agent data
    agent_data = state.get("agent_data", {})
    embedding_model_id = agent_data.get("ia_model_id", "mistral")
    pipeline_item = state.get("pipeline_item")

    embedding_results = []

    # Process doc chunks if they exist
    if state.get("doc_chunks_path"):
        logger.info("Starting embedding generation for doc chunks: %s", state['doc_chunks_path'])

        inputs = {
            "chunks_json_path": state["doc_chunks_path"],
            "embedding_model_id": embedding_model_id,
            "file_type": state["file_type"],
            "document_id": state["document_id"],
        }

        result = run_script(
            "scripts/ingestion/generate_embeddings_and_store.py", inputs
        )

        if not result["success"]:
            error_msg = f"Doc embedding generation failed: {result['stderr']}"
            state["error"] = error_msg
            logger.error(error_msg)

            state["fragments"].append(
                {
                    "tipo": "execucao",
                    "conteudo": f"Doc embedding generation error: {result['stderr']}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # NEW (v2.1): Update status to error
            if pipeline_item:
                pipeline_item.set_error(error_msg)
                logger.debug("Updated cell %s status to 'error' due to doc embedding failure", state['cell_id'])

            return state

        doc_status = result["stdout"].strip()
        embedding_results.append(f"Doc: {doc_status}")
        logger.info("Doc embedding status: %s", doc_status)

    # Process code chunks if they exist
    if state.get("code_chunks_path"):
        logger.info("Starting embedding generation for code chunks: %s", state['code_chunks_path'])

        inputs = {
            "chunks_json_path": state["code_chunks_path"],
            "embedding_model_id": embedding_model_id,
            "file_type": state["file_type"],
            "document_id": state["document_id"],
        }

        result = run_script(
            "scripts/ingestion/generate_embeddings_and_store.py", inputs
        )

        if not result["success"]:
            error_msg = f"Code embedding generation failed: {result['stderr']}"
            state["error"] = error_msg
            logger.error(error_msg)

            state["fragments"].append(
                {
                    "tipo": "execucao",
                    "conteudo": f"Code embedding generation error: {result['stderr']}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # NEW (v2.1): Update status to error
            if pipeline_item:
                pipeline_item.set_error(error_msg)
                logger.debug("Updated cell %s status to 'error' due to code embedding failure", state['cell_id'])

            return state

        code_status = result["stdout"].strip()
        embedding_results.append(f"Code: {code_status}")
        logger.info("Code embedding status: %s", code_status)

    # Check if we processed any chunks
    if not embedding_results:
        error_msg = "No chunks available for embedding generation"
        state["error"] = error_msg
        logger.error(error_msg)

        state["fragments"].append(
            {
                "tipo": "execucao",
                "conteudo": "Embedding generation error: No chunks available",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # NEW (v2.1): Update status to error
        if pipeline_item:
            pipeline_item.set_error(error_msg)

        return state

    # Store combined embedding status
    state["embedding_status"] = "; ".join(embedding_results)
    logger.info("Combined embedding status: %s", state['embedding_status'])

    # Update context
    state["context"]["steps_completed"].append("generate_embeddings")
    state["context"]["embedding_model"] = embedding_model_id
    state["context"]["embedding_status"] = state["embedding_status"]

    # Add success fragment
    fragment_content = f"Embeddings generated and stored successfully using model: {embedding_model_id}. Results: {state['embedding_status']}"

    state["fragments"].append(
        {
            "tipo": "execucao",
            "conteudo": fragment_content,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    # NEW (v2.1): Add fragment to persistent cell
    if pipeline_item:
        pipeline_item.add_fragment(
            type="execution",
            content=fragment_content,
            metadata={
                "step": "generate_embeddings",
                "embedding_model": embedding_model_id,
                "embedding_status": state["embedding_status"],
                "workflow": "ingestion",
            },
        )

    logger.info("Embedding generation completed successfully")
    return state


def finalize_ingestion(state: IngestionState) -> IngestionState:
    """
    Finalize the ingestion workflow.

    This node marks the workflow as completed and adds a summary fragment.

    **New in v2.1**: Updates cell status to 'completed' and adds comprehensive
    summary fragment to persistent cell via PipelineItem if available.
    """
    logger.info("Finalizing ingestion for cell: %s", state['cell_id'])
    pipeline_item = state.get("pipeline_item")

    state["completed"] = True
    state["context"]["completed_at"] = datetime.utcnow().isoformat()

    # Create comprehensive summary
    summary_data = {
        "document_id": state["document_id"],
        "file_path": state["file_path"],
        "local_file_path": state["local_file_path"],
        "file_type": state["file_type"],
        "doc_chunks_path": state["doc_chunks_path"],
        "code_chunks_path": state["code_chunks_path"],
        "chunks_path": state["chunks_path"],  # Deprecated but kept for compatibility
        "embedding_status": state["embedding_status"],
        "steps_completed": state["context"]["steps_completed"],
    }

    # Add summary fragment to state
    summary = {
        "tipo": "memoria",
        "conteudo": json.dumps(summary_data, indent=2),
        "timestamp": datetime.utcnow().isoformat(),
    }
    state["fragments"].append(summary)

    # NEW (v2.1): Update cell status to 'completed'
    if pipeline_item:
        pipeline_item.update_status("completed")

        # NEW (v2.1): Add comprehensive summary fragment to persistent cell
        pipeline_item.add_fragment(
            type="memory",
            content="Ingestion workflow completed successfully",
            result=summary_data,
            metadata={
                "step": "finalize",
                "workflow": "ingestion",
                "completed_at": state["context"]["completed_at"],
                "steps_completed": state["context"]["steps_completed"],
            },
        )
        logger.debug("Updated cell %s status to 'completed' and added summary fragment", state['cell_id'])

    logger.info("Ingestion workflow finalized successfully")
    return state


def should_continue_ingestion(state: IngestionState) -> str:
    """
    Decide whether to continue the workflow or end.

    Returns:
        "resolve" - Continue to file path resolution
        "preprocess" - Continue to preprocessing
        "embed" - Continue to embedding
        "finalize" - Continue to finalization
        "end" - End workflow (due to completion or error)
    """
    if state.get("error"):
        logger.error("Workflow error detected: %s", state['error'])
        return "end"

    if state.get("completed"):
        return "end"

    # Determine next step based on completed steps
    steps_completed = state.get("context", {}).get("steps_completed", [])

    if not steps_completed:
        return "resolve"
    elif (
        "download_from_url" in steps_completed
        or "resolve_local_path" in steps_completed
    ) and "preprocess_and_chunk" not in steps_completed:
        return "preprocess"
    elif (
        "preprocess_and_chunk" in steps_completed
        and "generate_embeddings" not in steps_completed
    ):
        return "embed"
    elif "generate_embeddings" in steps_completed:
        return "finalize"

    return "end"
