#!/usr/bin/env python3
"""
Generate Embeddings and Store Script - Backward Compatibility Facade

This file maintains backward compatibility with the original monolithic module.
All functionality has been modularized into the generate_embeddings_and_store/ package.

For new code, import from the package:
    from app.workflows.generate_embeddings_and_store import execute

This facade will be maintained for legacy code compatibility.
"""

# Re-export all public APIs from the modularized package
from .generate_embeddings_and_store import (
    delete_embeddings_by_document_id,
    execute,
    generate_chunk_id,
    get_collection_name_from_file_type,
    initialize_embedding_model,
    load_chunks_from_json,
    main,
    store_chunks_in_chromadb,
)

__all__ = [
    "execute",
    "delete_embeddings_by_document_id",
    "load_chunks_from_json",
    "initialize_embedding_model",
    "generate_chunk_id",
    "store_chunks_in_chromadb",
    "get_collection_name_from_file_type",
    "main",
]

if __name__ == "__main__":
    main()
