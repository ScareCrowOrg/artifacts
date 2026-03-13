"""
Vector Lifecycle Management - Automatic cleanup and updates for vector store.

This module provides automated maintenance for the vector store:
- Detect and remove vectors for deleted files
- Detect and update vectors for modified files
- Track file hashes to identify changes
- Periodic cleanup routines

Technical naming: All functions and variables in English.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

from langchain_chroma import Chroma

from ..config import BASE_DIR, VECTORSTORE_COLLECTION, VECTORSTORE_PATH

# create_embeddings and load_document_content are imported lazily inside each
# function that uses them (see calls below) to break the cyclic-import chain:
#   services.vector_lifecycle → utils.document_ingestion → services.vector_lifecycle
# document_ingestion already uses a deferred import of vector_lifecycle; making
# this side lazy too eliminates the static cycle entirely.

logger = logging.getLogger(__name__)


def calculate_file_hash(file_path: Path) -> str:
    """
    Calculate SHA256 hash of file content.

    Args:
        file_path: Path to file

    Returns:
        Hexadecimal hash string
    """
    try:
        with open(file_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        return file_hash
    except Exception as e:
        logger.warning("Error calculating hash for %s: %s", file_path, e)
        return ""


def get_all_vectorstore_sources(vectorstore: Chroma) -> Set[str]:
    """
    Get all unique file sources stored in vector store.

    Args:
        vectorstore: ChromaDB vector store instance

    Returns:
        Set of file paths (sources)
    """
    try:
        # Get all documents with metadata
        all_docs = vectorstore.get(include=["metadatas"])

        sources = set()
        for metadata in all_docs["metadatas"]:
            if metadata and "source" in metadata:
                sources.add(metadata["source"])

        logger.info("Found %s unique sources in vector store", len(sources))
        return sources

    except Exception as e:
        logger.error("Error getting vector store sources: %s", e)
        return set()


def remove_vectors_for_deleted_files(
    vectorstore_path: str = VECTORSTORE_PATH,
    collection_name: str = VECTORSTORE_COLLECTION,
    embedding_model: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Remove vectors for files that no longer exist in the repository.

    Process:
    1. Get all file sources from vector store
    2. Check if each source file exists in BASE_DIR
    3. Remove vectors for missing files

    Args:
        vectorstore_path: Path to vector store (default: from config)
        collection_name: Collection name (default: from config)
        embedding_model: Embedding model to use (default: from config)
        dry_run: If True, only report what would be deleted (no actual deletion)

    Returns:
        Dict with results:
            - files_checked: Number of unique files in vector store
            - files_deleted: Number of files removed
            - files_remaining: Number of files still present
            - deleted_sources: List of file paths removed
    """
    logger.info("Starting vector cleanup for deleted files...")

    # Get or create vector store
    try:
        from ..utils.document_ingestion import create_embeddings  # noqa: PLC0415
        embeddings = create_embeddings(model=embedding_model)
        vectorstore_full_path = BASE_DIR / vectorstore_path

        if not vectorstore_full_path.exists():
            logger.warning("Vector store not found at %s", vectorstore_full_path)
            return {
                "files_checked": 0,
                "files_deleted": 0,
                "files_remaining": 0,
                "deleted_sources": [],
            }

        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(vectorstore_full_path),
        )

    except Exception as e:
        logger.error("Error loading vector store: %s", e)
        return {
            "files_checked": 0,
            "files_deleted": 0,
            "files_remaining": 0,
            "deleted_sources": [],
        }

    # Get all sources in vector store
    all_sources = get_all_vectorstore_sources(vectorstore)

    # Check which sources no longer exist
    deleted_sources = []
    for source in all_sources:
        file_path = BASE_DIR / source
        if not file_path.exists():
            deleted_sources.append(source)
            logger.info("File no longer exists: %s", source)

    # Remove vectors for deleted files
    files_deleted = 0
    if deleted_sources and not dry_run:
        try:
            # Get collection
            collection = vectorstore._collection

            for source in deleted_sources:
                # Delete all chunks for this source
                result = collection.delete(where={"source": source})

                files_deleted += 1
                logger.info("Removed vectors for deleted file: %s", source)

        except Exception as e:
            logger.error("Error removing vectors: %s", e)

    elif deleted_sources and dry_run:
        logger.info("DRY RUN: Would delete vectors for %s files", len(deleted_sources))

    results = {
        "files_checked": len(all_sources),
        "files_deleted": files_deleted,
        "files_remaining": len(all_sources) - files_deleted,
        "deleted_sources": deleted_sources,
    }

    logger.info(
        "Cleanup complete: %s files checked, %s deleted, %s remaining",
        results['files_checked'], results['files_deleted'], results['files_remaining']
    )

    return results


def update_vectors_for_modified_files(
    vectorstore_path: str = VECTORSTORE_PATH,
    collection_name: str = VECTORSTORE_COLLECTION,
    embedding_model: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Update vectors for files that have been modified.

    Process:
    1. Get all file sources from vector store with their stored hashes
    2. Calculate current hash for each file
    3. If hash differs, remove old vectors and re-ingest file

    Args:
        vectorstore_path: Path to vector store (default: from config)
        collection_name: Collection name (default: from config)
        embedding_model: Embedding model to use (default: from config)
        dry_run: If True, only report what would be updated (no actual update)

    Returns:
        Dict with results:
            - files_checked: Number of files checked
            - files_updated: Number of files re-ingested
            - files_unchanged: Number of files with no changes
            - updated_sources: List of file paths updated
    """
    logger.info("Starting vector update for modified files...")

    # Get or create vector store
    try:
        from ..utils.document_ingestion import create_embeddings  # noqa: PLC0415
        embeddings = create_embeddings(model=embedding_model)
        vectorstore_full_path = BASE_DIR / vectorstore_path

        if not vectorstore_full_path.exists():
            logger.warning("Vector store not found at %s", vectorstore_full_path)
            return {
                "files_checked": 0,
                "files_updated": 0,
                "files_unchanged": 0,
                "updated_sources": [],
            }

        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(vectorstore_full_path),
        )

    except Exception as e:
        logger.error("Error loading vector store: %s", e)
        return {
            "files_checked": 0,
            "files_updated": 0,
            "files_unchanged": 0,
            "updated_sources": [],
        }

    # Get all sources in vector store
    all_sources = get_all_vectorstore_sources(vectorstore)

    # Check for modifications
    modified_sources = []
    files_checked = 0

    for source in all_sources:
        file_path = BASE_DIR / source

        # Skip if file doesn't exist (handled by cleanup)
        if not file_path.exists():
            continue

        files_checked += 1

        # Get stored hash from metadata (if available)
        try:
            docs = vectorstore.get(
                where={"source": source}, limit=1, include=["metadatas"]
            )

            stored_hash = None
            if docs and docs["metadatas"] and len(docs["metadatas"]) > 0:
                stored_hash = docs["metadatas"][0].get("file_hash")

            # Calculate current hash
            current_hash = calculate_file_hash(file_path)

            # Compare hashes
            if stored_hash and current_hash and stored_hash != current_hash:
                modified_sources.append(source)
                logger.info("File modified (hash changed): %s", source)
            elif not stored_hash:
                # No hash stored, consider as potentially modified
                logger.info("No hash found for file (will update): %s", source)
                modified_sources.append(source)

        except Exception as e:
            logger.warning("Error checking file %s: %s", source, e)

    # Update vectors for modified files
    files_updated = 0
    if modified_sources and not dry_run:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        from ..config import CHUNK_OVERLAP, CHUNK_SIZE

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            is_separator_regex=False,
        )

        collection = vectorstore._collection

        for source in modified_sources:
            try:
                file_path = BASE_DIR / source

                # Step 1: Remove old vectors
                collection.delete(where={"source": source})
                logger.info("Removed old vectors for: %s", source)

                # Step 2: Load and re-ingest file
                from ..utils.document_ingestion import load_document_content  # noqa: PLC0415
                documents = load_document_content(file_path)

                if documents:
                    # Add source and hash metadata
                    file_hash = calculate_file_hash(file_path)
                    for doc in documents:
                        doc.metadata["source"] = str(file_path.relative_to(BASE_DIR))
                        doc.metadata["file_hash"] = file_hash

                    # Split into chunks
                    chunks = text_splitter.split_documents(documents)

                    # Add chunk IDs
                    for chunk in chunks:
                        content = (
                            chunk.page_content
                            if hasattr(chunk, "page_content")
                            else str(chunk)
                        )
                        chunk_id = hashlib.sha256(
                            (content + source).encode("utf-8")
                        ).hexdigest()
                        chunk.metadata["chunk_id"] = chunk_id

                    # Re-ingest
                    vectorstore.add_documents(chunks)
                    files_updated += 1
                    logger.info("Re-ingested %s chunks for: %s", len(chunks), source)
                else:
                    logger.warning("Could not load content for: %s", source)

            except Exception as e:
                logger.error("Error updating file %s: %s", source, e)

    elif modified_sources and dry_run:
        logger.info("DRY RUN: Would update vectors for %s files", len(modified_sources))

    results = {
        "files_checked": files_checked,
        "files_updated": files_updated,
        "files_unchanged": files_checked - files_updated,
        "updated_sources": modified_sources,
    }

    logger.info(
        "Update complete: %s files checked, %s updated, %s unchanged",
        results['files_checked'], results['files_updated'], results['files_unchanged']
    )

    return results


def perform_full_maintenance(
    vectorstore_path: str = VECTORSTORE_PATH,
    collection_name: str = VECTORSTORE_COLLECTION,
    embedding_model: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Perform full vector store maintenance.

    Combines cleanup and update operations:
    1. Remove vectors for deleted files
    2. Update vectors for modified files

    Args:
        vectorstore_path: Path to vector store (default: from config)
        collection_name: Collection name (default: from config)
        embedding_model: Embedding model to use (default: from config)
        dry_run: If True, only report what would be done (no actual changes)

    Returns:
        Dict with combined results from both operations
    """
    logger.info("Starting full vector store maintenance...")

    # Step 1: Remove vectors for deleted files
    cleanup_results = remove_vectors_for_deleted_files(
        vectorstore_path=vectorstore_path,
        collection_name=collection_name,
        embedding_model=embedding_model,
        dry_run=dry_run,
    )

    # Step 2: Update vectors for modified files
    update_results = update_vectors_for_modified_files(
        vectorstore_path=vectorstore_path,
        collection_name=collection_name,
        embedding_model=embedding_model,
        dry_run=dry_run,
    )

    results = {
        "cleanup": cleanup_results,
        "update": update_results,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info("Full maintenance complete")

    return results
