#!/usr/bin/env python3
"""
Generate Code Embeddings and Store Script

This specialized module handles embedding generation and storage for code chunks.
It uses the DeepSeek-Coder model for embeddings and stores in the scareverse_code collection.

Usage:
    CLI: python generate_code_embeddings_and_store.py --chunks-json-path <path> --document-id <id>
    Python: from workflows.generate_code_embeddings_and_store import execute; result_item = execute(pipeline_item)
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add the root directory to PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

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

from app.config import OLLAMA_BASE_URL, VECTORSTORE_PATH

logger = logging.getLogger(__name__)

# Import LangChain components
try:
    from langchain_chroma import Chroma
    from langchain_community.embeddings import OllamaEmbeddings
    from langchain_core.documents import Document
except ImportError as e:
    logger.error("Failed to import required dependencies: %s", e)
    logger.error("Please ensure langchain-chroma and langchain-community are installed")
    sys.exit(1)


def load_code_chunks_from_json(chunks_json_path: str) -> List[Dict[str, Any]]:
    """
    Load code chunks from JSON file.

    Args:
        chunks_json_path: Path to the JSON file containing chunks

    Returns:
        List of chunk dictionaries with 'text' and 'metadata' keys

    Raises:
        FileNotFoundError: If chunks file doesn't exist
        ValueError: If JSON format is invalid
    """
    chunks_path = Path(chunks_json_path)

    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_json_path}")

    logger.info("Loading code chunks from: %s", chunks_json_path)

    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in chunks file: {e}") from e

    # Validate chunks format
    if not isinstance(chunks_data, list):
        raise ValueError("Chunks JSON must be a list of chunk objects")

    for i, chunk in enumerate(chunks_data):
        if not isinstance(chunk, dict):
            raise ValueError(f"Chunk {i} must be a dictionary")
        if "text" not in chunk:
            raise ValueError(f"Chunk {i} missing 'text' field")
        if "metadata" not in chunk:
            # Add empty metadata if not present
            chunk["metadata"] = {}

    logger.info("Loaded %s code chunks successfully", len(chunks_data))
    return chunks_data


def initialize_deepseek_embeddings(
    ollama_base_url: str = OLLAMA_BASE_URL,
) -> OllamaEmbeddings:
    """
    Initialize DeepSeek-Coder embedding model for code.

    Args:
        ollama_base_url: Base URL for Ollama API

    Returns:
        OllamaEmbeddings instance configured with DeepSeek-Coder
    """
    logger.info("Initializing DeepSeek-Coder embeddings for code")
    logger.info("Ollama base URL: %s", ollama_base_url)

    embeddings = OllamaEmbeddings(model="deepseek-coder", base_url=ollama_base_url)

    return embeddings


def generate_chunk_id(chunk_text: str, source: str) -> str:
    """
    Generate a unique ID for a chunk based on content and source.

    Args:
        chunk_text: Text content of the chunk
        source: Source file path or identifier

    Returns:
        SHA256 hash as chunk ID
    """
    content = f"{chunk_text}{source}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def store_code_chunks_in_chromadb(
    chunks: List[Dict[str, Any]],
    embeddings: OllamaEmbeddings,
    document_id: str,
    vectorstore_path: str = VECTORSTORE_PATH,
) -> Dict[str, Any]:
    """
    Store code chunks with embeddings in ChromaDB scareverse_code collection.

    Args:
        chunks: List of chunk dictionaries with 'text' and 'metadata'
        embeddings: OllamaEmbeddings instance (DeepSeek-Coder)
        document_id: Unique identifier for the source document
        vectorstore_path: Path to ChromaDB storage directory

    Returns:
        Dictionary with ingestion statistics
    """
    collection_name = "scareverse_code"
    logger.info("Storing code chunks in ChromaDB collection: %s", collection_name)
    logger.info("Vector store path: %s", vectorstore_path)

    # Convert chunks to LangChain Document objects
    documents = []
    for i, chunk in enumerate(chunks):
        # Enrich metadata
        metadata = chunk.get("metadata", {}).copy()
        metadata["document_id"] = document_id
        metadata["collection_name"] = collection_name
        metadata["embedding_model_id"] = "deepseek-coder"
        metadata["target_collection"] = collection_name
        metadata["chunk_index"] = i

        # Generate chunk_id for idempotency
        source = metadata.get("source", document_id)
        chunk_id = generate_chunk_id(chunk["text"], source)
        metadata["chunk_id"] = chunk_id

        doc = Document(page_content=chunk["text"], metadata=metadata)
        documents.append(doc)

    logger.info("Prepared %s documents for ingestion", len(documents))

    # Load existing vector store to check for duplicates
    vectorstore_full_path = Path(vectorstore_path)
    existing_ids = set()

    if vectorstore_full_path.exists():
        try:
            existing_vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embeddings,
                persist_directory=str(vectorstore_full_path),
            )

            # Get existing chunk IDs
            existing_data = existing_vectorstore.get(include=["metadatas"])
            for meta in existing_data["metadatas"]:
                if meta and "chunk_id" in meta:
                    existing_ids.add(meta["chunk_id"])

            logger.info("Found %s existing chunks in collection", len(existing_ids))

        except Exception as e:
            logger.warning("Could not load existing vectorstore: %s", e)
            logger.info("Will create new collection")

    # Filter out already-existing chunks
    new_documents = []
    skipped_count = 0

    for doc in documents:
        chunk_id = doc.metadata.get("chunk_id")
        if chunk_id not in existing_ids:
            new_documents.append(doc)
        else:
            skipped_count += 1

    logger.info("New chunks to ingest: %s (skipped: %s)", len(new_documents), skipped_count)

    # Store new chunks
    if new_documents:
        if not vectorstore_full_path.exists() or not existing_ids:
            # Create new vector store
            logger.info("Creating new vector store at %s", vectorstore_full_path)
            Chroma.from_documents(
                documents=new_documents,
                embedding=embeddings,
                collection_name=collection_name,
                persist_directory=str(vectorstore_full_path),
            )
        else:
            # Add to existing vector store
            logger.info("Adding chunks to existing vector store")
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embeddings,
                persist_directory=str(vectorstore_full_path),
            )
            vectorstore.add_documents(new_documents)

        logger.info("Successfully ingested %s code chunks", len(new_documents))
    else:
        logger.info("No new chunks to ingest - all chunks already exist")

    return {
        "total_chunks": len(chunks),
        "new_chunks_ingested": len(new_documents),
        "skipped_chunks": skipped_count,
        "collection_name": collection_name,
        "document_id": document_id,
        "embedding_model": "deepseek-coder",
    }


def execute(item: "PipelineItem") -> "PipelineItem":
    """
    Execute code embedding generation and storage using PipelineItem.

    Args:
        item: PipelineItem containing input data

    Returns:
        Updated PipelineItem with results
    """
    if not PIPELINE_ITEM_AVAILABLE:
        item.set_error("PipelineItem not available - import failed")
        return item

    logger.info("=" * 60)
    logger.info("Generate Code Embeddings and Store Script (PipelineItem mode)")
    logger.info("=" * 60)

    try:
        # Extract parameters from item.data
        chunks_json_path_str = item.data.get("code_chunks_path", "")
        document_id = item.data.get("document_id", "")
        ollama_base_url = item.data.get("ollama_base_url", OLLAMA_BASE_URL)
        vectorstore_path = item.data.get("vectorstore_path", VECTORSTORE_PATH)

        if not chunks_json_path_str:
            item.set_error("Missing required field: code_chunks_path")
            return item

        if not document_id:
            item.set_error("Missing required field: document_id")
            return item

        chunks_json_path = Path(chunks_json_path_str)

        logger.info("Code chunks JSON path: %s", chunks_json_path)
        logger.info("Document ID: %s", document_id)
        logger.info("=" * 60)

        # Step 1: Load chunks from JSON
        chunks = load_code_chunks_from_json(chunks_json_path)
        logger.info("Loaded %s code chunks", len(chunks))

        # Step 2: Initialize DeepSeek-Coder embeddings
        embeddings = initialize_deepseek_embeddings(ollama_base_url)

        # Step 3: Store chunks in ChromaDB
        result = store_code_chunks_in_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            document_id=document_id,
            vectorstore_path=vectorstore_path,
        )

        # Update PipelineItem
        item.merge_data(
            {"code_embedding_result": result, "vectorstore_path": vectorstore_path}
        )

        item.add_fragment(
            type="execucao",
            content=f"Code embeddings generated and stored: {result['new_chunks_ingested']} new, {result['skipped_chunks']} skipped",
            result=result,
            metadata={"step": "generate_code_embeddings_and_store"},
        )

        logger.info("=" * 60)
        logger.info("✅ Code embedding generation and storage completed successfully!")
        logger.info("New chunks ingested: %s", result['new_chunks_ingested'])
        logger.info("Skipped chunks: %s", result['skipped_chunks'])
        logger.info("=" * 60)

        return item

    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ Code embedding generation failed: %s", e)
        logger.error("=" * 60)
        item.set_error(f"Code embedding generation failed: {str(e)}")
        return item


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate embeddings for code chunks and store in ChromaDB"
    )

    parser.add_argument(
        "--chunks-json-path",
        required=True,
        help="Path to JSON file containing preprocessed code chunks",
    )

    parser.add_argument(
        "--document-id", required=True, help="Unique identifier for the source document"
    )

    parser.add_argument(
        "--ollama-base-url",
        default=OLLAMA_BASE_URL,
        help=f"Ollama API base URL (default: {OLLAMA_BASE_URL})",
    )

    parser.add_argument(
        "--vectorstore-path",
        default=VECTORSTORE_PATH,
        help=f"Path to ChromaDB storage (default: {VECTORSTORE_PATH})",
    )

    args = parser.parse_args()

    try:
        # Load chunks
        chunks = load_code_chunks_from_json(args.chunks_json_path)

        # Initialize DeepSeek-Coder embedding model
        embeddings = initialize_deepseek_embeddings(args.ollama_base_url)

        # Store chunks in ChromaDB
        result = store_code_chunks_in_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            document_id=args.document_id,
            vectorstore_path=args.vectorstore_path,
        )

        # Print success status to stdout
        status_message = (
            f"Code ingestion successful: {result['new_chunks_ingested']} new chunks "
            f"stored in '{result['collection_name']}' collection "
            f"(total: {result['total_chunks']}, skipped: {result['skipped_chunks']})"
        )
        print(status_message)

        logger.info("Code embedding generation and storage completed successfully")
        sys.exit(0)

    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except ValueError as e:
        logger.error("Invalid input: %s", e)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
