"""
RAG Module - Advanced Retrieval Augmented Generation.

This module provides RAG functionality with ensemble retrieval across multiple
collections and embedding models.

Public API (backward compatible):
- RAGService: Main service class
- get_rag_service: Factory function to create service instances
- get_embedding_function_for_model_id: Get embedding function for a model

All exports maintain backward compatibility with the original rag_service.py.

NOTE on cyclic imports (R0401):
  The following intentional lazy-import cycles exist and are handled at runtime
  via deferred imports inside function bodies (not at module load time):

  Cycle A: ollama_service → rag_service → rag → rag.rag_service
           → query_expander_service → ollama_service
  Cycle B: ollama_service → rag_service → rag → rag.rag_service
           → rag_postprocessor → ollama_service

  Both cycles are fully deferred: each cross-module call is wrapped in a
  local `from X import Y` statement, so Python never hits a partially-
  initialised module.  Suppressing the static R0401 warning here is safe.
"""
# pylint: disable=cyclic-import

from .config import (
    AVAILABLE_COLLECTION_NAMES,
    COLLECTION_TO_EMBEDDING_MODEL,
    DEFAULT_RAG_K,
    OPENAI_DEFAULT_EMBEDDING_MODEL,
)
from .embeddings import get_embedding_function_for_model_id
from .rag_service import RAGService, get_rag_service

__all__ = [
    "RAGService",
    "get_rag_service",
    "get_embedding_function_for_model_id",
    "DEFAULT_RAG_K",
    "OPENAI_DEFAULT_EMBEDDING_MODEL",
    "COLLECTION_TO_EMBEDDING_MODEL",
    "AVAILABLE_COLLECTION_NAMES",
]
