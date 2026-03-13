#!/usr/bin/env python3
"""
Vue.js Intelligent Chunking Strategies for Document Ingestion

This module provides specialized chunking strategies for Vue.js ecosystem files:
- Vue SFCs: Parse <template>, <script>, <style> blocks
- JavaScript/TypeScript: Extract composables, Pinia stores, functions
- JSDoc/Comments: Extract documentation for dual collection ingestion

Each strategy produces chunks optimized for deepseek-coder (code) and mistral (docs).
"""

from .vue_chunking_orchestrator import chunk_vue_code
from .vue_javascript_chunker import (
    chunk_javascript_file,
    extract_code_and_comments,
    extract_function_body,
    find_preceding_jsdoc,
    infer_js_chunk_type,
)
from .vue_sfc_chunker import chunk_vue_sfc, extract_vue_blocks

__all__ = [
    "chunk_vue_code",
    "chunk_vue_sfc",
    "extract_vue_blocks",
    "chunk_javascript_file",
    "infer_js_chunk_type",
    "extract_code_and_comments",
    "extract_function_body",
    "find_preceding_jsdoc",
]
