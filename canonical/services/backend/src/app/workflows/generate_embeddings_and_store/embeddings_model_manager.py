"""
Embedding Model Management

Handles Ollama embedding model initialization and chunk ID generation.
"""

import hashlib
import logging

from app.config import OLLAMA_BASE_URL

logger = logging.getLogger(__name__)

try:
    from langchain_community.embeddings import OllamaEmbeddings
except ImportError as e:
    logger.error("Failed to import OllamaEmbeddings: %s", e)
    OllamaEmbeddings = None


def initialize_embedding_model(
    embedding_model_id: str, ollama_base_url: str = OLLAMA_BASE_URL
):
    """
    Initialize Ollama embedding model.

    Args:
        embedding_model_id: Model ID (e.g., 'mistral', 'deepseek-coder', 'phi')
        ollama_base_url: Base URL for Ollama API

    Returns:
        OllamaEmbeddings instance configured with specified model

    Raises:
        ImportError: If OllamaEmbeddings is not available
    """
    if OllamaEmbeddings is None:
        raise ImportError(
            "OllamaEmbeddings not available. Install langchain-community."
        )

    logger.info("Initializing Ollama embeddings with model: %s", embedding_model_id)
    logger.info("Ollama base URL: %s", ollama_base_url)

    embeddings = OllamaEmbeddings(model=embedding_model_id, base_url=ollama_base_url)

    return embeddings


def generate_chunk_id(chunk_text: str, source: str) -> str:
    """
    Generate a unique ID for a chunk based on content and source.

    This enables idempotent ingestion: chunks with the same content and source
    will have the same ID, allowing us to skip re-ingestion.

    Args:
        chunk_text: Text content of the chunk
        source: Source file path or identifier

    Returns:
        SHA256 hash as chunk ID
    """
    content = f"{chunk_text}{source}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
