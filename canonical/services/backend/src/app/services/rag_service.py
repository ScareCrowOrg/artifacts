"""
RAG Service - Backward Compatibility Shim.

This file maintains backward compatibility by re-exporting the modularized
RAG service from the rag/ subdirectory.

DEPRECATED: This file is a compatibility layer. New code should import from:
    from backend.app.services.rag import RAGService, get_rag_service

For details on the modularized structure, see:
    backend/app/services/rag/README.md

Technical naming: All functions and variables in English.
"""

# Import and re-export all public APIs from the modularized rag module
from .rag import (
    AVAILABLE_COLLECTION_NAMES,
    COLLECTION_TO_EMBEDDING_MODEL,
    DEFAULT_RAG_K,
    OPENAI_DEFAULT_EMBEDDING_MODEL,
    RAGService,
    get_embedding_function_for_model_id,
    get_rag_service,
)

# Maintain full backward compatibility
__all__ = [
    "RAGService",
    "get_rag_service",
    "get_embedding_function_for_model_id",
    "DEFAULT_RAG_K",
    "OPENAI_DEFAULT_EMBEDDING_MODEL",
    "COLLECTION_TO_EMBEDDING_MODEL",
    "AVAILABLE_COLLECTION_NAMES",
]
