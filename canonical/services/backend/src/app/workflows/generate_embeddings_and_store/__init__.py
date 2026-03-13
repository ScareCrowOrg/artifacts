#!/usr/bin/env python3
"""
Generate Embeddings and Store Script for Document Ingestion

This module generates embeddings for preprocessed chunks and stores them
in ChromaDB vector stores. It is designed to be called by the ingestion-issue
cell type workflow as the second step after preprocessing and chunking.

Usage:
    CLI: python -m app.workflows.generate_embeddings_and_store.embeddings_cli --chunks-json-path <path> ...
    Python: from app.workflows.generate_embeddings_and_store import execute; result_item = execute(pipeline_item)

Public API:
    - execute: PipelineItem-compatible execution function
    - delete_embeddings_by_document_id: Remove embeddings for a document
    - load_chunks_from_json: Load chunks from JSON file
    - initialize_embedding_model: Initialize Ollama embeddings
    - store_chunks_in_chromadb: Store chunks in vector store
    - get_collection_name_from_file_type: Map file type to collection name
"""

# Public API exports for backward compatibility
from .collection_mapper import (
    get_collection_name_from_file_type,
    get_embedding_model_for_collection,
)
from .embeddings_chromadb_store import (
    delete_embeddings_by_document_id,
    store_chunks_in_chromadb,
)
from .embeddings_chunk_loader import load_chunks_from_json

# For CLI execution
from .embeddings_cli import main
from .embeddings_model_manager import generate_chunk_id, initialize_embedding_model
from .embeddings_pipeline import execute

__all__ = [
    # Main execution
    "execute",
    "main",
    # Core functions
    "load_chunks_from_json",
    "initialize_embedding_model",
    "generate_chunk_id",
    "store_chunks_in_chromadb",
    "delete_embeddings_by_document_id",
    # Helpers
    "get_collection_name_from_file_type",
    "get_embedding_model_for_collection",
]
