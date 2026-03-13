#!/usr/bin/env python3
"""
Backward compatibility shim for vue_chunking_strategies module.

This file maintains backward compatibility by re-exporting all functions
from the modularized vue_chunking_strategies package.

For new code, prefer importing from the package:
    from app.workflows.vue_chunking_strategies import chunk_vue_code
"""

from .vue_chunking_strategies import (
    chunk_javascript_file,
    chunk_vue_code,
    chunk_vue_sfc,
    extract_code_and_comments,
    extract_function_body,
    extract_vue_blocks,
    find_preceding_jsdoc,
    infer_js_chunk_type,
)

# Private functions that were exposed (backward compatibility)
_chunk_vue_sfc = chunk_vue_sfc
_extract_vue_blocks = extract_vue_blocks
_chunk_javascript_file = chunk_javascript_file
_infer_js_chunk_type = infer_js_chunk_type
_extract_code_and_comments = extract_code_and_comments
_extract_function_body = extract_function_body
_find_preceding_jsdoc = find_preceding_jsdoc

__all__ = [
    "chunk_vue_code",
    "_chunk_vue_sfc",
    "_extract_vue_blocks",
    "_chunk_javascript_file",
    "_infer_js_chunk_type",
    "_extract_code_and_comments",
    "_extract_function_body",
    "_find_preceding_jsdoc",
]
