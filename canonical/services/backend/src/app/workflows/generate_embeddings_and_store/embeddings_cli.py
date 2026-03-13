#!/usr/bin/env python3
"""
Command-line Interface for Embedding Generation

Provides CLI access to the embedding generation and storage functionality.
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the root directory to PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

from app.config import OLLAMA_BASE_URL, VECTORSTORE_PATH

from .collection_mapper import get_collection_name_from_file_type
from .embeddings_chromadb_store import store_chunks_in_chromadb
from .embeddings_chunk_loader import load_chunks_from_json
from .embeddings_model_manager import initialize_embedding_model

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate embeddings and store chunks in ChromaDB"
    )

    parser.add_argument(
        "--chunks-json-path",
        required=True,
        help="Path to JSON file containing preprocessed chunks",
    )

    parser.add_argument(
        "--embedding-model-id",
        required=True,
        help="Ollama model ID for embeddings (e.g., mistral, deepseek-coder)",
    )

    parser.add_argument(
        "--file-type",
        required=True,
        help="Type of the source file (e.g., markdown, python, pdf)",
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
        chunks = load_chunks_from_json(args.chunks_json_path)

        # Determine collection name based on file type
        collection_name = get_collection_name_from_file_type(args.file_type)
        logger.info("Target collection: %s", collection_name)

        # Initialize embedding model
        embeddings = initialize_embedding_model(
            args.embedding_model_id, args.ollama_base_url
        )

        # Store chunks in ChromaDB
        result = store_chunks_in_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            collection_name=collection_name,
            document_id=args.document_id,
            file_type=args.file_type,
            vectorstore_path=args.vectorstore_path,
        )

        # Print success status to stdout
        status_message = (
            f"Ingestion successful: {result['new_chunks_ingested']} new chunks "
            f"stored in '{result['collection_name']}' collection "
            f"(total: {result['total_chunks']}, skipped: {result['skipped_chunks']})"
        )
        print(status_message)

        logger.info("Embedding generation and storage completed successfully")
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
