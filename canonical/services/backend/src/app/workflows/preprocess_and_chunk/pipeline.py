"""
Pipeline Execution Module

This module provides the PipelineItem execute function
for workflow integration.
"""

import logging
import traceback
from pathlib import Path

from .chunker import chunk_text_intelligent
from .loader import generate_document_id, load_file_content
from .output_handler import save_chunks_to_separate_json_files
from .preprocessor import preprocess_text

logger = logging.getLogger(__name__)

# Import PipelineItem for execute function
try:
    from backend.app.core.models import PipelineItem

    PIPELINE_ITEM_AVAILABLE = True
except ImportError:
    try:
        from app.core.models import PipelineItem

        PIPELINE_ITEM_AVAILABLE = True
    except ImportError:
        PIPELINE_ITEM_AVAILABLE = False


def execute(item: "PipelineItem") -> "PipelineItem":
    """
    Execute preprocessing and chunking using PipelineItem.

    This function provides the importlib-compatible interface for the workflow.

    New Architecture Support:
    - item.data: Contains execution parameters (merged from initial_data + execution params)
    - item.notebook_item_data: Direct access to the original NotebookItem (Cell)
    - item.fragments: Execution-specific fragments (for this pipeline run)
    - item.notebook_item_data.fragments: Entity-level fragments (cell's memory/diary)
    - item.notebook_item_data.initial_data: Cell's initial data
    - item.notebook_item_data.refs: Cell's file references

    Args:
        item: PipelineItem containing input data and execution context

    Returns:
        Updated PipelineItem with results
    """
    if not PIPELINE_ITEM_AVAILABLE:
        item.set_error("PipelineItem not available - import failed")
        return item

    logger.info("=" * 60)
    logger.info("Preprocess and Chunk Script (PipelineItem mode)")
    logger.info("=" * 60)

    try:
        # Extract parameters from item.data (execution context)
        file_path_str = item.data.get("file_path", "")
        file_type = item.data.get("file_type", "")
        document_id = item.data.get("document_id", generate_document_id())
        output_dir_str = item.data.get("output_dir", "/tmp")
        chunk_size = item.data.get("chunk_size", 1000)
        chunk_overlap = item.data.get("chunk_overlap", 200)

        # ALTERNATIVE: Could also extract from notebook_item_data if needed
        # For example, if parameters are stored in the cell's initial_data:
        # cell_initial_data = item.notebook_item_data.initial_data
        # file_path_str = file_path_str or cell_initial_data.get("file_path", "")

        if not file_path_str:
            item.set_error("Missing required field: file_path")
            return item

        if not file_type:
            item.set_error("Missing required field: file_type")
            return item

        # Convert paths
        file_path = Path(file_path_str).resolve()
        output_dir = Path(output_dir_str).resolve()

        logger.info("File path: %s", file_path)
        logger.info("File type: %s", file_type)
        logger.info("Document ID: %s", document_id)
        logger.info("Output directory: %s", output_dir)
        logger.info("Chunk size: %s", chunk_size)
        logger.info("Chunk overlap: %s", chunk_overlap)
        logger.info("=" * 60)

        # Step 1: Load file content
        content = load_file_content(file_path, file_type)

        # Step 2: Preprocess text
        preprocessed_content = preprocess_text(content)

        # Step 3: Chunk text using intelligent strategies
        doc_chunks, code_chunks = chunk_text_intelligent(
            preprocessed_content,
            file_path,
            file_type,
            document_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # Step 4: Save chunks to separate JSON files
        doc_chunks_path, code_chunks_path = save_chunks_to_separate_json_files(
            doc_chunks, code_chunks, output_dir, document_id
        )

        # Update PipelineItem execution data
        result_data = {
            "document_id": document_id,
            "num_doc_chunks": len(doc_chunks),
            "num_code_chunks": len(code_chunks),
        }

        if doc_chunks_path:
            result_data["doc_chunks_path"] = str(doc_chunks_path.resolve())
        if code_chunks_path:
            result_data["code_chunks_path"] = str(code_chunks_path.resolve())

        item.merge_data(result_data)

        # Add execution fragment to PipelineItem (for this run's traceability)
        item.add_fragment(
            type="execucao",
            content=f"Document preprocessed and chunked: {len(doc_chunks)} doc chunks, {len(code_chunks)} code chunks created",
            result={
                "doc_chunks_path": str(doc_chunks_path.resolve())
                if doc_chunks_path
                else None,
                "code_chunks_path": str(code_chunks_path.resolve())
                if code_chunks_path
                else None,
                "num_doc_chunks": len(doc_chunks),
                "num_code_chunks": len(code_chunks),
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            },
            metadata={"step": "preprocess_and_chunk"},
        )

        # OPTIONAL: Add memory fragment to the original NotebookItem (Cell)
        # for entity-level traceability and "diary" functionality
        # This creates a persistent record in the cell's history:
        # item.notebook_item_data.fragments.append({
        #     "tipo": "memoria",
        #     "conteudo": f"Processed document {document_id}: {len(chunks)} chunks generated",
        #     "metadata": {
        #         "document_id": document_id,
        #         "num_chunks": len(chunks),
        #         "timestamp": datetime.utcnow().isoformat()
        #     }
        # })

        logger.info("=" * 60)
        logger.info("✅ Processing completed successfully!")
        logger.info("=" * 60)

        return item

    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ Processing failed: %s", e)
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        item.set_error(f"Preprocessing failed: {str(e)}")
        return item
