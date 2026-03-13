"""
PipelineItem Integration

Provides PipelineItem-compatible execution interface for the workflow.
"""

import logging
from pathlib import Path

from app.config import OLLAMA_BASE_URL, VECTORSTORE_PATH

try:
    from backend.app.core.models import PipelineItem

    PIPELINE_ITEM_AVAILABLE = True
except ImportError:
    try:
        from app.core.models import PipelineItem

        PIPELINE_ITEM_AVAILABLE = True
    except ImportError:
        PIPELINE_ITEM_AVAILABLE = False

from .collection_mapper import get_collection_name_from_file_type
from .embeddings_chromadb_store import store_chunks_in_chromadb
from .embeddings_chunk_loader import load_chunks_from_json
from .embeddings_model_manager import initialize_embedding_model

logger = logging.getLogger(__name__)


def execute(item: "PipelineItem") -> "PipelineItem":
    """
    Execute embedding generation and storage using PipelineItem.

    This function provides the importlib-compatible interface for the workflow.

    Args:
        item: PipelineItem containing input data

    Returns:
        Updated PipelineItem with results
    """
    if not PIPELINE_ITEM_AVAILABLE:
        item.set_error("PipelineItem not available - import failed")
        return item

    logger.info("=" * 60)
    logger.info("Generate Embeddings and Store Script (PipelineItem mode)")
    logger.info("=" * 60)

    try:
        # Extract parameters from item.data
        chunks_json_path_str = item.data.get("chunks_json_path", "")
        embedding_model_id = item.data.get("embedding_model_id", "mistral")
        file_type = item.data.get("file_type", "")
        document_id = item.data.get("document_id", "")
        ollama_base_url = item.data.get("ollama_base_url", OLLAMA_BASE_URL)
        vectorstore_path = item.data.get("vectorstore_path", VECTORSTORE_PATH)
        collection_name = item.data.get(
            "collection_name", get_collection_name_from_file_type(file_type)
        )

        if not chunks_json_path_str:
            item.set_error("Missing required field: chunks_json_path")
            return item

        if not file_type:
            item.set_error("Missing required field: file_type")
            return item

        if not document_id:
            item.set_error("Missing required field: document_id")
            return item

        chunks_json_path = Path(chunks_json_path_str)

        logger.info("Chunks JSON path: %s", chunks_json_path)
        logger.info("Embedding model: %s", embedding_model_id)
        logger.info("File type: %s", file_type)
        logger.info("Document ID: %s", document_id)
        logger.info("Collection: %s", collection_name)
        logger.info("=" * 60)

        # Step 1: Load chunks from JSON
        chunks = load_chunks_from_json(chunks_json_path)
        logger.info("Loaded %s chunks", len(chunks))

        # Step 2: Initialize embeddings
        embeddings = initialize_embedding_model(embedding_model_id, ollama_base_url)

        # Step 3: Store chunks in ChromaDB
        result = store_chunks_in_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            collection_name=collection_name,
            document_id=document_id,
            file_type=file_type,
            vectorstore_path=vectorstore_path,
        )

        # Update PipelineItem
        item.merge_data(
            {
                "embedding_result": result,
                "vectorstore_path": vectorstore_path,
                "collection_name": collection_name,
            }
        )

        item.add_fragment(
            type="execucao",
            content=f"Embeddings generated and stored: {result['new_chunks_ingested']} new, {result['skipped_chunks']} skipped",
            result=result,
            metadata={"step": "generate_embeddings_and_store"},
        )

        logger.info("=" * 60)
        logger.info("✅ Embedding generation and storage completed successfully!")
        logger.info("New chunks ingested: %s", result['new_chunks_ingested'])
        logger.info("Skipped chunks: %s", result['skipped_chunks'])
        logger.info("=" * 60)

        return item

    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ Embedding generation failed: %s", e)
        logger.error("=" * 60)
        item.set_error(f"Embedding generation failed: {str(e)}")
        return item
