#!/usr/bin/env python3
"""
Intelligent Chunking Strategies for Document Ingestion

This module provides specialized chunking strategies for different file types:
- Markdown: Semantic chunking based on headers (H1, H2, H3)
- Python: AST-based chunking with docstring extraction
- Configuration: Structured chunking for YAML/JSON files

Each strategy produces chunks optimized for their target embedding model and collection.
"""

from .config_chunker import chunk_configuration_file
from .markdown_chunker import _clean_markdown_content, chunk_markdown
from .python_chunker import _extract_code_and_docstring, chunk_python_code

__all__ = [
    "chunk_markdown",
    "_clean_markdown_content",
    "chunk_python_code",
    "_extract_code_and_docstring",
    "chunk_configuration_file",
]
