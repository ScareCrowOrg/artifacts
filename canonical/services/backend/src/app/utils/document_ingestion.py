"""
Document Ingestion Module for RAG System

This module handles ingestion of documents from the local repository into a
ChromaDB vector store for RAG (Retrieval Augmented Generation).

Key Features:
- Recursive directory traversal from BASE_DIR
- Support for all text files (UTF-8) and PDFs
- Chunking with RecursiveCharacterTextSplitter
- Ollama embeddings (local models: mistral, phi, deepseek-coder)
- ChromaDB persistence with incremental ingestion

Technical naming: All functions and variables in English.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, List, Optional

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..config import (
    BASE_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
    VECTORSTORE_COLLECTION,
    VECTORSTORE_PATH,
)

logger = logging.getLogger(__name__)

# File extensions to skip (binary files)
BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".pdf",  # PDFs are handled separately
    ".zip",
    ".tar",
    ".gz",
    ".rar",
    ".7z",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
    ".pyo",
    ".class",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".bin",
    ".dat",
    ".pkl",
    ".pickle",
}

# Directories to skip
SKIP_DIRECTORIES = {
    ".git",
    ".github",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "actions-runner",
    "actions-test-runner",
    "chroma_db",
    ".chroma",
    "temp",
    "runtime",  # Skip vector store directory
}


def should_process_file(file_path: Path) -> bool:
    """
    Determine if a file should be processed for ingestion.

    Args:
        file_path: Path to the file

    Returns:
        True if file should be processed, False otherwise
    """
    # Skip if in a skip directory
    for parent in file_path.parents:
        if parent.name in SKIP_DIRECTORIES:
            return False

    # Check file extension
    ext = file_path.suffix.lower()

    # Skip known binary files (except PDFs which we handle)
    if ext in BINARY_EXTENSIONS:
        return False

    return True


def create_embeddings(model: Optional[str] = None) -> OllamaEmbeddings:
    """
    Create an OllamaEmbeddings instance with configured settings.

    Args:
        model: Ollama model to use for embeddings (default: from config)
               Supported models: mistral, phi, deepseek-coder

    Returns:
        OllamaEmbeddings instance configured with project settings

    Example:
        >>> embeddings = create_embeddings()  # Uses OLLAMA_EMBEDDING_MODEL from config
        >>> embeddings = create_embeddings(model="phi")  # Uses specific model
    """
    embedding_model = model or OLLAMA_EMBEDDING_MODEL

    logger.info("Creating embeddings with model: %s", embedding_model)
    embeddings = OllamaEmbeddings(model=embedding_model, base_url=OLLAMA_BASE_URL)

    return embeddings


def load_document_content(file_path: Path) -> Optional[List[Any]]:
    """
    Load document content using appropriate loader.

    This function uses the LangChain loaders to handle different file types:
    - PDFs: PyPDFLoader
    - Text files: TextLoader with UTF-8 encoding

    Args:
        file_path: Path to the document file

    Returns:
        List of LangChain Document objects, or None if loading failed
    """
    try:
        ext = file_path.suffix.lower()

        if ext == ".pdf":
            # Use PyPDFLoader for PDFs
            loader = PyPDFLoader(str(file_path))
            documents = loader.load()
            logger.info("Loaded PDF: %s (%s pages)", file_path, len(documents))
            return documents

        else:
            # Try to load as text file
            try:
                loader = TextLoader(str(file_path), encoding="utf-8")
                documents = loader.load()
                logger.info("Loaded text file: %s", file_path)
                return documents
            except UnicodeDecodeError:
                logger.warning("Failed to decode as UTF-8: %s - skipping", file_path)
                return None

    except Exception as e:
        logger.warning("Failed to load document %s: %s", file_path, e)
        return None


def ingest_documents_to_vectorstore(
    directory_path: Optional[str] = None,
    vectorstore_path: str = VECTORSTORE_PATH,
    collection_name: str = VECTORSTORE_COLLECTION,
    force_recreate: bool = False,
    embedding_model: Optional[str] = None,
) -> Chroma:
    """
    Ingest documents from a directory into a ChromaDB vector store.

    This function implements incremental ingestion: only new or modified chunks
    are processed, avoiding reprocessing of existing content.

    Process:
    1. Recursively traverses the directory
    2. Loads documents (PDFs and text files)
    3. Chunks documents using RecursiveCharacterTextSplitter
    4. Generates embeddings using Ollama local models (mistral, phi, deepseek-coder)
    5. Performs incremental ingestion (skips existing chunks)
    6. Stores in ChromaDB for later retrieval

    Args:
        directory_path: Path to directory to ingest (default: BASE_DIR)
        vectorstore_path: Path to ChromaDB storage (default: from config)
        collection_name: Name of the ChromaDB collection (default: from config)
        force_recreate: If True, delete existing collection and recreate
        embedding_model: Ollama model for embeddings (default: from config)

    Returns:
        Chroma vector store instance

    Example:
        >>> # Basic usage with defaults
        >>> vectorstore = ingest_documents_to_vectorstore()
        >>>
        >>> # Custom directory and model
        >>> vectorstore = ingest_documents_to_vectorstore(
        ...     directory_path="/path/to/docs",
        ...     vectorstore_path="my_chroma_db",
        ...     embedding_model="phi"
        ... )
        >>>
        >>> # Force recreate vector store
        >>> vectorstore = ingest_documents_to_vectorstore(force_recreate=True)
    """
    # Use BASE_DIR if no directory specified
    if directory_path is None:
        directory_path = str(BASE_DIR)

    dir_path = Path(directory_path)
    if not dir_path.exists():
        raise ValueError(f"Directory does not exist: {directory_path}")

    logger.info("Starting document ingestion from: %s", directory_path)
    logger.info("Vector store path: %s", vectorstore_path)
    logger.info("Embedding model: %s", embedding_model or OLLAMA_EMBEDDING_MODEL)

    # NOTE: Pre-ingest vector cleanup is intentionally NOT performed here to
    # avoid a cyclic import with services.vector_lifecycle (which imports this
    # module).  Callers that need cleanup should invoke
    # services.vector_lifecycle.remove_vectors_for_deleted_files() explicitly
    # before calling this function.

    # Initialize text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )

    # Initialize embeddings using Ollama (local models)
    embeddings = create_embeddings(model=embedding_model)

    # Collect all documents
    all_documents = []
    files_processed = 0
    files_skipped = 0

    # Recursively walk directory
    for root, dirs, files in os.walk(dir_path):
        # Filter out skip directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]

        for file_name in files:
            file_path = Path(root) / file_name

            # Check if file should be processed
            if not should_process_file(file_path):
                files_skipped += 1
                continue

            # Load document
            documents = load_document_content(file_path)

            if documents:
                # Add source metadata
                for doc in documents:
                    doc.metadata["source"] = str(file_path.relative_to(BASE_DIR))

                all_documents.extend(documents)
                files_processed += 1
            else:
                files_skipped += 1

    logger.info(
        "Loaded %s documents from %s files (%s files skipped)",
        len(all_documents), files_processed, files_skipped
    )

    if not all_documents:
        logger.warning("No documents loaded for ingestion")
        # Create empty vector store
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=vectorstore_path,
        )
        return vectorstore

    # Split documents into chunks
    logger.info("Splitting documents into chunks...")
    chunks = text_splitter.split_documents(all_documents)
    logger.info("Created %s chunks from %s documents", len(chunks), len(all_documents))

    # Carregar vector store existente (se houver) e buscar chunk_ids
    vectorstore_full_path = BASE_DIR / vectorstore_path
    existing_ids = set()
    if vectorstore_full_path.exists():
        try:
            existing_vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embeddings,
                persist_directory=str(vectorstore_full_path),
            )
            docs = existing_vectorstore.get(include=["metadatas"])
            for meta in docs["metadatas"]:
                if meta and "chunk_id" in meta:
                    existing_ids.add(meta["chunk_id"])
        except Exception as e:
            logger.warning("Could not load existing vectorstore for incremental ingest: %s", e)

    # Gerar hash único para cada chunk e descartar já existentes
    def chunk_id(chunk):
        content = chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        source = chunk.metadata.get("source", "") if hasattr(chunk, "metadata") else ""
        return hashlib.sha256((content + source).encode("utf-8")).hexdigest()

    new_chunks = []
    skipped = 0
    for chunk in chunks:
        cid = chunk_id(chunk)
        chunk.metadata["chunk_id"] = cid
        if cid not in existing_ids:
            new_chunks.append(chunk)
        else:
            skipped += 1

    logger.info("Total new chunks to ingest: %s (skipped: %s)", len(new_chunks), skipped)

    if not new_chunks:
        logger.info("No new chunks to ingest. Vector store is up to date.")
        return Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(vectorstore_full_path),
        )

    # Create or load vector store
    vectorstore_full_path = BASE_DIR / vectorstore_path

    if force_recreate and vectorstore_full_path.exists():
        logger.info("Deleting existing vector store: %s", vectorstore_full_path)
        import shutil

        shutil.rmtree(vectorstore_full_path)

    # Process new chunks in batches by token with rate limiting
    import time

    import tiktoken

    from app.utils.rate_limiter import create_embedding_rate_limiter

    MAX_TOKENS_PER_BATCH = 300000
    encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text):
        return len(encoding.encode(text))

    batches = []
    current_batch = []
    current_tokens = 0
    for chunk in new_chunks:
        chunk_text = (
            chunk.page_content if hasattr(chunk, "page_content") else str(chunk)
        )
        chunk_tokens = count_tokens(chunk_text)
        if current_tokens + chunk_tokens > MAX_TOKENS_PER_BATCH and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
        current_batch.append(chunk)
        current_tokens += chunk_tokens
    if current_batch:
        batches.append(current_batch)

    logger.info("Total batches to process: %s", len(batches))

    # Initialize rate limiter
    rate_limiter = create_embedding_rate_limiter()
    logger.info("Rate limiting enabled: batch_size=%s, delay=%ss", rate_limiter.batch_size, rate_limiter.batch_delay)

    vectorstore = None
    for batch_num, batch in enumerate(batches, 1):
        logger.info("Processing batch %s/%s: %s chunks", batch_num, len(batches), len(batch))
        logger.info("Ollama endpoint: %s | Model: %s", getattr(embeddings, 'base_url', OLLAMA_BASE_URL), getattr(embeddings, 'model', embedding_model or OLLAMA_EMBEDDING_MODEL))
        start_time = time.time()

        # Use rate limiter to control batch processing
        with rate_limiter.acquire():
            if batch_num == 1 and (
                force_recreate or not vectorstore_full_path.exists()
            ):
                vectorstore = Chroma.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    collection_name=collection_name,
                    persist_directory=str(vectorstore_full_path),
                )
            else:
                if not vectorstore:
                    vectorstore = Chroma(
                        collection_name=collection_name,
                        embedding_function=embeddings,
                        persist_directory=str(vectorstore_full_path),
                    )
                vectorstore.add_documents(batch)

        elapsed = time.time() - start_time
        logger.info("Batch %s processed in %ss.", batch_num, elapsed)

        # Add delay between batches (except after last batch)
        if batch_num < len(batches) and rate_limiter.batch_delay > 0:
            logger.debug("Waiting %ss before next batch", rate_limiter.batch_delay)
            time.sleep(rate_limiter.batch_delay)

    # Log rate limiter statistics
    stats = rate_limiter.get_stats()
    logger.info("Rate limiter stats: %s requests in %s batches", stats['total_requests'], stats['total_batches'])

    logger.info("Successfully ingested %s new chunks into vector store", len(new_chunks))
    logger.info("Vector store persisted at: %s", vectorstore_full_path)

    return vectorstore


def get_or_create_vectorstore(
    vectorstore_path: str = VECTORSTORE_PATH,
    collection_name: str = VECTORSTORE_COLLECTION,
    auto_ingest: bool = False,
    embedding_model: Optional[str] = None,
) -> Chroma:
    """
    Get existing vector store or create a new one.

    Args:
        vectorstore_path: Path to ChromaDB storage (default: from config)
        collection_name: Name of the ChromaDB collection (default: from config)
        auto_ingest: If True and store doesn't exist, auto-ingest from BASE_DIR
        embedding_model: Ollama model for embeddings (default: from config)

    Returns:
        Chroma vector store instance

    Raises:
        FileNotFoundError: If vector store doesn't exist and auto_ingest=False

    Example:
        >>> # Get existing or create empty
        >>> vectorstore = get_or_create_vectorstore()
        >>>
        >>> # Get existing or auto-ingest
        >>> vectorstore = get_or_create_vectorstore(auto_ingest=True)
        >>>
        >>> # Use specific model
        >>> vectorstore = get_or_create_vectorstore(embedding_model="phi")
    """
    vectorstore_full_path = BASE_DIR / vectorstore_path

    # Initialize embeddings using Ollama
    embeddings = create_embeddings(model=embedding_model)

    # Check if vector store exists
    if vectorstore_full_path.exists():
        logger.info("Loading existing vector store from: %s", vectorstore_full_path)
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(vectorstore_full_path),
        )
        return vectorstore

    # Vector store doesn't exist
    if auto_ingest:
        logger.info("Vector store doesn't exist, auto-ingesting documents...")
        return ingest_documents_to_vectorstore(
            vectorstore_path=vectorstore_path,
            collection_name=collection_name,
            embedding_model=embedding_model,
        )
    else:
        raise FileNotFoundError(
            f"Vector store not found at {vectorstore_full_path}. "
            "Run document ingestion first or use auto_ingest=True."
        )
