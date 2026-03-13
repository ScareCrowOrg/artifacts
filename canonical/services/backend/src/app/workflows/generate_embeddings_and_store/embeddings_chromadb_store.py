"""
ChromaDB Storage Operations

Handles chunk storage and deletion in ChromaDB vector stores with rate limiting.
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from app.config import OLLAMA_BASE_URL, VECTORSTORE_PATH
from app.utils.rate_limiter import create_embedding_rate_limiter

logger = logging.getLogger(__name__)

try:
    from langchain_chroma import Chroma
    from langchain_community.embeddings import OllamaEmbeddings
    from langchain_core.documents import Document
except ImportError as e:
    logger.error("Failed to import required dependencies: %s", e)
    Chroma = None
    Document = None
    OllamaEmbeddings = None

from .collection_mapper import get_embedding_model_for_collection
from .embeddings_model_manager import generate_chunk_id


def store_chunks_in_chromadb(
    chunks: List[Dict[str, Any]],
    embeddings,
    collection_name: str,
    document_id: str,
    file_type: str,
    vectorstore_path: str = VECTORSTORE_PATH,
) -> Dict[str, Any]:
    """
    Store chunks with embeddings in ChromaDB with idempotency.

    This function:
    1. Checks for existing chunks by chunk_id
    2. Only adds new chunks that don't already exist
    3. Updates metadata to include document_id, file_type, and collection_name

    Args:
        chunks: List of chunk dictionaries with 'text' and 'metadata'
        embeddings: OllamaEmbeddings instance for generating embeddings
        collection_name: Name of the ChromaDB collection to use
        document_id: Unique identifier for the source document
        file_type: Type of the source file
        vectorstore_path: Path to ChromaDB storage directory

    Returns:
        Dictionary with ingestion statistics

    Raises:
        ImportError: If required dependencies are not available
    """
    if Chroma is None or Document is None:
        raise ImportError(
            "Required dependencies not available. Install langchain-chroma and langchain-core."
        )

    logger.info("Storing chunks in ChromaDB collection: %s", collection_name)
    logger.info("Vector store path: %s", vectorstore_path)

    # Convert chunks to LangChain Document objects
    documents = []
    for i, chunk in enumerate(chunks):
        # Enrich metadata
        metadata = chunk.get("metadata", {}).copy()
        metadata["document_id"] = document_id
        metadata["file_type"] = file_type
        metadata["collection_name"] = collection_name
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

    # Store new chunks with rate limiting
    if new_documents:
        # Initialize rate limiter for batch processing
        rate_limiter = create_embedding_rate_limiter()

        logger.info(
            "Using rate limiting: batch_size=%s, delay=%ss, max_concurrent=%s",
            rate_limiter.batch_size, rate_limiter.batch_delay, rate_limiter.max_concurrent
        )

        vectorstore = None

        if not vectorstore_full_path.exists() or not existing_ids:
            # Create new vector store with first batch, then add remaining in batches
            logger.info("Creating new vector store at %s", vectorstore_full_path)

            # Split documents into batches
            batches = [
                new_documents[i : i + rate_limiter.batch_size]
                for i in range(0, len(new_documents), rate_limiter.batch_size)
            ]

            for batch_idx, batch_docs in enumerate(batches, 1):
                with rate_limiter.acquire():
                    if vectorstore is None:
                        # First batch: create vectorstore
                        vectorstore = Chroma.from_documents(
                            documents=batch_docs,
                            embedding=embeddings,
                            collection_name=collection_name,
                            persist_directory=str(vectorstore_full_path),
                        )
                        logger.info("Created vectorstore with %s documents", len(batch_docs))
                    else:
                        # Subsequent batches: add to existing
                        vectorstore.add_documents(batch_docs)
                        logger.info("Added %s documents to vectorstore", len(batch_docs))

                    # Log progress
                    logger.info("Progress: %s/%s batches completed", batch_idx, len(batches))

                    # Add delay between batches (except after last batch)
                    if batch_idx < len(batches) and rate_limiter.batch_delay > 0:
                        logger.debug("Waiting %ss before next batch", rate_limiter.batch_delay)
                        time.sleep(rate_limiter.batch_delay)

        else:
            # Add to existing vector store in batches
            logger.info("Adding chunks to existing vector store in batches")
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embeddings,
                persist_directory=str(vectorstore_full_path),
            )

            # Split documents into batches
            batches = [
                new_documents[i : i + rate_limiter.batch_size]
                for i in range(0, len(new_documents), rate_limiter.batch_size)
            ]

            for batch_idx, batch_docs in enumerate(batches, 1):
                with rate_limiter.acquire():
                    vectorstore.add_documents(batch_docs)
                    logger.info("Added batch of %s documents", len(batch_docs))

                    # Log progress
                    logger.info("Progress: %s/%s batches completed", batch_idx, len(batches))

                    # Add delay between batches (except after last batch)
                    if batch_idx < len(batches) and rate_limiter.batch_delay > 0:
                        logger.debug("Waiting %ss before next batch", rate_limiter.batch_delay)
                        time.sleep(rate_limiter.batch_delay)

        # Log completion
        logger.info("Processed %s documents in %s batches", len(new_documents), len(batches))
        logger.info("Successfully ingested %s chunks with rate limiting", len(new_documents))
    else:
        logger.info("No new chunks to ingest - all chunks already exist")

    return {
        "total_chunks": len(chunks),
        "new_chunks_ingested": len(new_documents),
        "skipped_chunks": skipped_count,
        "collection_name": collection_name,
        "document_id": document_id,
    }


def delete_embeddings_by_document_id(
    item: "PipelineItem", vectorstore_path: str = VECTORSTORE_PATH
) -> Dict[str, Any]:
    """
    Delete all embeddings associated with a document ID from vector stores.

    This function removes embeddings from all collections (docs, code, config)
    to ensure complete cleanup when a document is deleted or needs to be updated.

    Args:
        item: PipelineItem containing the document_id to delete
        vectorstore_path: Path to ChromaDB storage directory

    Returns:
        Dictionary with deletion statistics

    Raises:
        ValueError: If document_id is missing from item.data
    """
    document_id = item.data.get("document_id")
    if not document_id:
        raise ValueError("Missing required field: document_id")

    logger.info("Deleting embeddings for document: %s", document_id)

    # Collections to check
    collections = ["scareverse_docs", "scareverse_code", "scareverse_config"]

    total_deleted = 0
    deletion_results = {}

    vectorstore_full_path = Path(vectorstore_path)

    if not vectorstore_full_path.exists():
        logger.warning("Vector store path does not exist: %s", vectorstore_path)
        return {
            "document_id": document_id,
            "total_deleted": 0,
            "collections_checked": collections,
            "status": "no_vectorstore",
        }

    for collection_name in collections:
        try:
            # Ensure OllamaEmbeddings is available
            if OllamaEmbeddings is None:
                logger.error("OllamaEmbeddings not available, skipping collection")
                deletion_results[collection_name] = (
                    "error: OllamaEmbeddings not available"
                )
                continue

            # Determine correct embedding model for this collection
            embedding_model_id = get_embedding_model_for_collection(collection_name)

            # Initialize embeddings with correct model
            embeddings = OllamaEmbeddings(
                model=embedding_model_id, base_url=OLLAMA_BASE_URL
            )

            # Load vector store
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embeddings,
                persist_directory=str(vectorstore_full_path),
            )

            # Query for documents with this document_id
            results = vectorstore.get(
                where={"document_id": document_id}, include=["metadatas"]
            )

            ids_to_delete = results["ids"]

            if ids_to_delete:
                # Delete the documents
                vectorstore.delete(ids=ids_to_delete)
                deleted_count = len(ids_to_delete)
                total_deleted += deleted_count
                deletion_results[collection_name] = deleted_count
                logger.info("Deleted %s embeddings from %s", deleted_count, collection_name)
            else:
                deletion_results[collection_name] = 0
                logger.debug("No embeddings found in %s for document %s", collection_name, document_id)

        except Exception as e:
            logger.warning("Error deleting from %s: %s", collection_name, e)
            deletion_results[collection_name] = f"error: {str(e)}"

    result = {
        "document_id": document_id,
        "total_deleted": total_deleted,
        "collections_checked": collections,
        "deletion_results": deletion_results,
        "status": "completed",
    }

    logger.info("Deletion complete: %s total embeddings removed", total_deleted)
    return result
