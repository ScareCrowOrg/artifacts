"""
Command-Line Interface Module

This module provides the CLI entry point for the preprocessing script.
"""

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

from .chunker import chunk_text_intelligent
from .loader import generate_document_id, load_file_content
from .output_handler import save_chunks_to_separate_json_files
from .preprocessor import preprocess_text

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the preprocessing script."""
    parser = argparse.ArgumentParser(
        description="Preprocess and chunk a file for RAG ingestion"
    )

    parser.add_argument(
        "--file-path",
        type=str,
        required=True,
        help="Absolute path to the file to be ingested",
    )

    parser.add_argument(
        "--file-type",
        type=str,
        required=True,
        help="Type of the file (e.g., markdown, python, pdf)",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="/tmp",
        help="Directory to save the chunks JSON files (default: /tmp)",
    )

    parser.add_argument(
        "--document-id",
        type=str,
        default=None,
        help="Unique identifier for the document (default: auto-generated UUID)",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Maximum size of each chunk in characters (default: 1000)",
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Number of characters to overlap between chunks (default: 200)",
    )

    args = parser.parse_args()

    # Convert paths
    file_path = Path(args.file_path).resolve()
    output_dir = Path(args.output_dir).resolve()

    # Generate document ID if not provided
    document_id = args.document_id or generate_document_id()

    logger.info("=" * 60)
    logger.info("Preprocess and Chunk Script")
    logger.info("=" * 60)
    logger.info("File path: %s", file_path)
    logger.info("File type: %s", args.file_type)
    logger.info("Document ID: %s", document_id)
    logger.info("Output directory: %s", output_dir)
    logger.info("Chunk size: %s", args.chunk_size)
    logger.info("Chunk overlap: %s", args.chunk_overlap)
    logger.info("=" * 60)

    try:
        # Step 1: Load file content
        content = load_file_content(file_path, args.file_type)

        # Step 2: Preprocess text
        preprocessed_content = preprocess_text(content)

        # Step 3: Chunk text using intelligent strategies
        doc_chunks, code_chunks = chunk_text_intelligent(
            preprocessed_content,
            file_path,
            args.file_type,
            document_id,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

        # Step 4: Save chunks to separate JSON files
        doc_chunks_path, code_chunks_path = save_chunks_to_separate_json_files(
            doc_chunks, code_chunks, output_dir, document_id
        )

        logger.info("=" * 60)
        logger.info("✅ Processing completed successfully!")
        logger.info("Doc chunks: %s", len(doc_chunks))
        logger.info("Code chunks: %s", len(code_chunks))
        if doc_chunks_path:
            logger.info("Doc chunks saved to: %s", doc_chunks_path)
        if code_chunks_path:
            logger.info("Code chunks saved to: %s", code_chunks_path)
        logger.info("=" * 60)

        # Print output paths to stdout (for workflow capture)
        # Output format: JSON object with doc_chunks_path and code_chunks_path
        # Example: {"doc_chunks_path": "/tmp/doc_chunks.json", "code_chunks_path": "/tmp/code_chunks.json"}
        output_obj = {
            "doc_chunks_path": str(doc_chunks_path) if doc_chunks_path else None,
            "code_chunks_path": str(code_chunks_path) if code_chunks_path else None,
        }
        print(json.dumps(output_obj))

        return 0

    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ Processing failed: %s", e)
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
