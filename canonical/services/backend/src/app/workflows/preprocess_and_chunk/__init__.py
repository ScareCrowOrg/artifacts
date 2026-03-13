"""
Preprocess and Chunk Module

This module provides document preprocessing and chunking functionality
for RAG ingestion. It is organized into specialized submodules:

- loader.py: File loading for different file types
- preprocessor.py: Text preprocessing operations
- chunker.py: Intelligent file-type-specific chunking
- output_handler.py: Saving chunks to JSON files
- pipeline.py: PipelineItem execute function
- cli.py: Command-line interface

Public API:
    File Loading:
        generate_document_id: Generate unique document ID
        load_file_content: Load file content based on type

    Preprocessing:
        preprocess_text: Perform basic text preprocessing

    Chunking:
        chunk_text_intelligent: Split text using intelligent strategies

    Output:
        save_chunks_to_separate_json_files: Save chunks to separate JSON files
        save_chunks_to_json: Save chunks to a single JSON file

    Pipeline:
        execute: PipelineItem execute function for workflow integration

    CLI:
        main: Command-line interface entry point
"""

from .chunker import chunk_text_intelligent
from .cli import main
from .loader import generate_document_id, load_file_content
from .output_handler import save_chunks_to_json, save_chunks_to_separate_json_files
from .pipeline import execute
from .preprocessor import preprocess_text

__all__ = [
    # File loading
    "generate_document_id",
    "load_file_content",
    # Preprocessing
    "preprocess_text",
    # Chunking
    "chunk_text_intelligent",
    # Output handling
    "save_chunks_to_separate_json_files",
    "save_chunks_to_json",
    # Pipeline
    "execute",
    # CLI
    "main",
]
