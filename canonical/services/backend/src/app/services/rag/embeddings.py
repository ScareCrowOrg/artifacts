"""
Embedding Functions - Embedding model management for RAG.

This module provides functions to create and configure embedding models
for both Ollama (local) and OpenAI (API) providers.

Technical naming: All functions and variables in English.
"""

import logging
from typing import Optional

from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from ...config import (
    OLLAMA_BASE_URL,
    OPENAI_API_KEY,
)

logger = logging.getLogger(__name__)


def get_embedding_function_for_model_id(
    model_id: str, api_key: Optional[str] = None
) -> Embeddings:
    """
    Get embedding function for a given model ID.

    Supports both Ollama (local) and OpenAI (API) embedding models.

    Args:
        model_id: Model identifier (e.g., 'mistral', 'deepseek-coder', 'text-embedding-3-small')
        api_key: API key for OpenAI embeddings (optional)

    Returns:
        Embeddings instance configured for the specified model

    Raises:
        ValueError: If model_id is not recognized or OpenAI key is missing

    Example:
        >>> # Ollama model
        >>> embeddings = get_embedding_function_for_model_id('mistral')
        >>>
        >>> # OpenAI model
        >>> embeddings = get_embedding_function_for_model_id(
        ...     'text-embedding-3-small',
        ...     api_key='sk-...'
        ... )
    """
    # Check if it's an OpenAI model
    openai_models = [
        "text-embedding-ada-002",
        "text-embedding-3-small",
        "text-embedding-3-large",
    ]

    if model_id in openai_models:
        effective_key = api_key or OPENAI_API_KEY
        if not effective_key:
            raise ValueError(
                f"OpenAI API Key required for model {model_id}. "
                "Provide via api_key parameter or OPENAI_API_KEY env var."
            )
        logger.info("Creating OpenAI embeddings with model: %s", model_id)
        return OpenAIEmbeddings(model=model_id, api_key=effective_key)

    # Default to Ollama for local models
    logger.info("Creating Ollama embeddings with model: %s", model_id)
    return OllamaEmbeddings(model=model_id, base_url=OLLAMA_BASE_URL)
