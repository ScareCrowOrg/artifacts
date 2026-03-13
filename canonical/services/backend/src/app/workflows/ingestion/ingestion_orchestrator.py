#!/usr/bin/env python3
"""
PipelineItem-based Orchestrator for Document Ingestion

This module provides the main execution entry point for the ingestion workflow.
It handles the lifecycle of ingestion operations using the PipelineItem model.

The orchestrator supports three operation types:
- 'new': Full ingestion (preprocess → embed → store)
- 'update': Re-ingestion (delete old embeddings → preprocess → embed → store)
- 'delete': Cleanup only (delete embeddings)

Functions:
- execute: Main entry point for importlib-based execution
"""

import json
import logging
import uuid

from .ingestion_workflow_utils import download_from_url, is_url

# Setup logging
logger = logging.getLogger(__name__)

# Import PipelineItem for execution model
try:
    from app.core.models import PipelineItem
except ImportError:
    # Fallback for when running as script
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.core.models import PipelineItem


# ============================================================================
# PipelineItem-based Execution (New Approach)
# ============================================================================


def execute(item: PipelineItem) -> PipelineItem:
    """
    Execute the ingestion workflow using PipelineItem with lifecycle support.

    This is the main entry point for importlib-based execution.
    The orchestrator calls this function directly with a PipelineItem instance.

    Handles three operation types:
    - 'new': Full ingestion (preprocess → embed → store)
    - 'update': Re-ingestion (delete old embeddings → preprocess → embed → store)
    - 'delete': Cleanup only (delete embeddings)

    Args:
        item: PipelineItem containing cell data and context

    Returns:
        Updated PipelineItem with execution results and fragments
    """
    logger.info("Starting ingestion workflow for cell: %s", item.cell_id)

    try:
        # Extract required data from item
        file_path = item.data.get("file_path", "")
        file_type = item.data.get("file_type", "")
        document_id = item.data.get("document_id", str(uuid.uuid4()))
        operation_type = item.data.get("operation_type", "new")
        previous_cell_id = item.data.get("previous_cell_id")

        if not file_path:
            item.set_error("Missing required field: file_path")
            return item

        if not file_type:
            item.set_error("Missing required field: file_type")
            return item

        # Update status
        item.update_status("running")

        # Add initialization fragment
        item.add_fragment(
            type="execucao",
            content=f"Ingestion workflow initialized for document: {document_id} (operation: {operation_type})",
            metadata={
                "workflow": "ingestion",
                "document_id": document_id,
                "operation_type": operation_type,
                "previous_cell_id": previous_cell_id,
            },
        )

        # Handle DELETE operation
        if operation_type == "delete":
            logger.info("Processing DELETE operation for document: %s", document_id)

            try:
                from .. import generate_embeddings_and_store as embed_module

                # Delete embeddings
                if hasattr(embed_module, "delete_embeddings_by_document_id"):
                    logger.info("Calling delete_embeddings_by_document_id...")
                    deletion_result = embed_module.delete_embeddings_by_document_id(
                        item
                    )

                    item.merge_data({"deletion_result": deletion_result})
                    item.add_fragment(
                        type="execucao",
                        content=f"Embeddings deleted for document {document_id}",
                        result=deletion_result,
                        metadata={"step": "delete_embeddings"},
                    )
                else:
                    item.set_error(
                        "delete_embeddings_by_document_id function not found"
                    )
                    return item

                if item.error:
                    return item

            except Exception as e:
                item.set_error(f"Embedding deletion failed: {str(e)}")
                return item

            # Mark as completed
            item.update_status("completed")
            item.add_fragment(
                type="memoria",
                content=f"Delete operation completed for document: {document_id}",
                result={
                    "document_id": document_id,
                    "operation_type": "delete",
                    "deletion_result": item.data.get("deletion_result"),
                },
            )

            logger.info("Delete operation completed for cell: %s", item.cell_id)
            return item

        # Handle UPDATE operation (delete old embeddings first)
        if operation_type == "update":
            logger.info("Processing UPDATE operation for document: %s", document_id)

            try:
                from .. import generate_embeddings_and_store as embed_module

                # Delete old embeddings
                if hasattr(embed_module, "delete_embeddings_by_document_id"):
                    logger.info("Deleting old embeddings before update...")
                    deletion_result = embed_module.delete_embeddings_by_document_id(
                        item
                    )

                    item.merge_data({"deletion_result": deletion_result})
                    item.add_fragment(
                        type="execucao",
                        content=f"Old embeddings deleted for document {document_id} (update operation)",
                        result=deletion_result,
                        metadata={"step": "delete_embeddings_before_update"},
                    )
                else:
                    logger.warning(
                        "delete_embeddings_by_document_id function not found, skipping deletion"
                    )

                if item.error:
                    return item

            except Exception as e:
                logger.warning("Failed to delete old embeddings: %s", e)
                # Continue with update even if deletion fails
                item.add_fragment(
                    type="execucao",
                    content=f"Warning: Failed to delete old embeddings: {str(e)}",
                    metadata={
                        "step": "delete_embeddings_before_update",
                        "warning": True,
                    },
                )

        # Continue with NEW or UPDATE processing (both need full ingestion)
        logger.info("Processing %s operation - full ingestion", operation_type.upper())

        # Step 1: Resolve file path (download if URL)
        local_file_path = file_path
        if is_url(file_path):
            logger.info("Detected URL: %s", file_path)
            try:
                local_file_path = download_from_url(file_path)
                item.add_fragment(
                    type="execucao",
                    content=f"Downloaded file from URL: {file_path}",
                    metadata={"original_url": file_path, "local_path": local_file_path},
                )
                item.merge_data({"local_file_path": local_file_path})
            except Exception as e:
                item.set_error(f"Failed to download from URL: {str(e)}")
                return item
        else:
            item.add_fragment(
                type="execucao",
                content=f"Using local file path: {file_path}",
                metadata={"local_path": file_path},
            )

        # Step 2: Preprocess and chunk using importlib
        logger.info("Calling preprocess_and_chunk via importlib...")
        try:
            # Try to import and call the script's execute function
            from .. import preprocess_and_chunk as preprocess_module

            # Prepare data for preprocessing
            item.merge_data(
                {
                    "file_path": local_file_path,
                    "file_type": file_type,
                    "document_id": document_id,
                    "output_dir": "/tmp",
                }
            )

            # Check if module has execute function
            if hasattr(preprocess_module, "execute"):
                logger.info("Using execute() function from preprocess_and_chunk")
                item = preprocess_module.execute(item)
            else:
                # Fallback to subprocess execution
                from .ingestion_workflow_utils import run_script

                logger.info("No execute() function, using subprocess fallback")
                result = run_script(
                    "scripts/ingestion/preprocess_and_chunk.py",
                    {
                        "file_path": local_file_path,
                        "file_type": file_type,
                        "document_id": document_id,
                        "output_dir": "/tmp",
                    },
                )

                if not result["success"]:
                    item.set_error(f"Preprocessing failed: {result['stderr']}")
                    return item

                # Parse JSON output from stdout
                # The script outputs: {"doc_chunks_path": "...", "code_chunks_path": "..."}
                stdout_lines = result["stdout"].strip().split("\n")
                if stdout_lines:
                    try:
                        chunks_info = json.loads(stdout_lines[-1])

                        doc_chunks_path = chunks_info.get("doc_chunks_path")
                        code_chunks_path = chunks_info.get("code_chunks_path")

                        # Store both paths in item data
                        item.merge_data(
                            {
                                "doc_chunks_path": doc_chunks_path,
                                "code_chunks_path": code_chunks_path,
                                "chunks_path": code_chunks_path
                                or doc_chunks_path,  # Backward compat
                            }
                        )

                        chunk_summary = []
                        if doc_chunks_path:
                            chunk_summary.append(f"doc chunks: {doc_chunks_path}")
                        if code_chunks_path:
                            chunk_summary.append(f"code chunks: {code_chunks_path}")

                        item.add_fragment(
                            type="execucao",
                            content=f"Document preprocessed and chunked successfully. {', '.join(chunk_summary)}",
                            metadata={
                                "doc_chunks_path": doc_chunks_path,
                                "code_chunks_path": code_chunks_path,
                            },
                        )
                    except json.JSONDecodeError as e:
                        item.set_error(f"Failed to parse chunks output JSON: {e}")
                        return item

            if item.error:
                return item

        except Exception as e:
            item.set_error(f"Preprocessing failed: {str(e)}")
            return item

        # Step 3: Generate embeddings using branched workflow
        logger.info("Processing chunks for branched embedding generation...")

        doc_chunks_path = item.data.get("doc_chunks_path")
        code_chunks_path = item.data.get("code_chunks_path")

        # Branch 1: Process documentation chunks if present
        if doc_chunks_path:
            logger.info("Generating documentation embeddings with Mistral...")
            try:
                from .. import generate_doc_embeddings_and_store as doc_embed_module

                if hasattr(doc_embed_module, "execute"):
                    logger.info(
                        "Using execute() function from generate_doc_embeddings_and_store"
                    )
                    item = doc_embed_module.execute(item)

                    if item.error:
                        logger.error("Doc embedding generation failed")
                        return item
                else:
                    logger.warning("Doc embedding module has no execute function")

            except ImportError as e:
                logger.warning("Could not import doc embedding module: %s", e)
            except Exception as e:
                item.set_error(f"Doc embedding generation failed: {str(e)}")
                return item
        else:
            logger.info("No documentation chunks to process")

        # Branch 2: Process code chunks if present
        if code_chunks_path:
            logger.info("Generating code embeddings with DeepSeek-Coder...")
            try:
                from .. import generate_code_embeddings_and_store as code_embed_module

                if hasattr(code_embed_module, "execute"):
                    logger.info(
                        "Using execute() function from generate_code_embeddings_and_store"
                    )
                    item = code_embed_module.execute(item)

                    if item.error:
                        logger.error("Code embedding generation failed")
                        return item
                else:
                    logger.warning("Code embedding module has no execute function")

            except ImportError as e:
                logger.warning("Could not import code embedding module: %s", e)
            except Exception as e:
                item.set_error(f"Code embedding generation failed: {str(e)}")
                return item
        else:
            logger.info("No code chunks to process")

        # Validate at least one branch processed successfully
        if not doc_chunks_path and not code_chunks_path:
            item.set_error("No chunks were generated during preprocessing")
            return item

        # Mark as completed
        item.update_status("completed")
        item.add_fragment(
            type="memoria",
            content=f"Ingestion workflow completed successfully (operation: {operation_type})",
            result={
                "document_id": document_id,
                "file_path": file_path,
                "local_file_path": local_file_path,
                "file_type": file_type,
                "operation_type": operation_type,
                "doc_chunks_path": doc_chunks_path,
                "code_chunks_path": code_chunks_path,
                "num_doc_chunks": item.data.get("num_doc_chunks", 0),
                "num_code_chunks": item.data.get("num_code_chunks", 0),
                "doc_embedding_result": item.data.get("doc_embedding_result"),
                "code_embedding_result": item.data.get("code_embedding_result"),
                "deletion_result": (
                    item.data.get("deletion_result")
                    if operation_type == "update"
                    else None
                ),
            },
        )

        logger.info("Ingestion workflow completed for cell: %s", item.cell_id)
        return item

    except Exception as e:
        logger.error("Unexpected error in ingestion workflow: %s", e, exc_info=True)
        item.set_error(f"Workflow error: {str(e)}")
        return item
