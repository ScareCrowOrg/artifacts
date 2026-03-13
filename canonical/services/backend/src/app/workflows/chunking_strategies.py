#!/usr/bin/env python3
"""
Backward compatibility shim for chunking_strategies module.

This file maintains backward compatibility by re-exporting all functions
from the modularized chunking_strategies package.

For new code, prefer importing from the package:
    from app.workflows.chunking_strategies import chunk_markdown
"""

from .chunking_strategies import (
    _clean_markdown_content,
    _extract_code_and_docstring,
    chunk_configuration_file,
    chunk_markdown,
    chunk_python_code,
)

__all__ = [
    "chunk_markdown",
    "_clean_markdown_content",
    "chunk_python_code",
    "_extract_code_and_docstring",
    "chunk_configuration_file",
]
