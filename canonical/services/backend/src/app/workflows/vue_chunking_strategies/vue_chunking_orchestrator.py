#!/usr/bin/env python3
"""
Vue.js Ecosystem Chunking Orchestrator

Provides the main entry point for chunking Vue.js ecosystem files.
Dispatches to appropriate chunking strategies based on file type.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .vue_javascript_chunker import chunk_javascript_file
from .vue_sfc_chunker import chunk_vue_sfc

logger = logging.getLogger(__name__)


def chunk_vue_code(
    content: str, file_path: Path, document_id: str, file_type: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Chunk Vue.js ecosystem files using specialized strategies.

    This strategy handles:
    - .vue files (Single File Components): Split into template, script, style blocks
    - .js/.ts files in frontend dirs: Extract composables, Pinia stores, functions
    - JSDoc/comments: Extract for documentation collection

    Returns two lists:
    - code_chunks: For scareverse_code collection (deepseek-coder)
    - doc_chunks: JSDoc/comments for scareverse_docs collection (mistral)

    Args:
        content: Source code content
        file_path: Source file path
        document_id: Unique document identifier
        file_type: File type ('vue', 'js', 'ts')

    Returns:
        Tuple of (code_chunks, doc_chunks)
    """
    logger.info("Chunking Vue.js file: %s (type: %s)", file_path, file_type)

    code_chunks = []
    doc_chunks = []

    if file_type == "vue":
        code_chunks, doc_chunks = chunk_vue_sfc(content, file_path, document_id)
    elif file_type in ["js", "ts"]:
        code_chunks, doc_chunks = chunk_javascript_file(
            content, file_path, document_id, file_type
        )
    else:
        logger.warning("Unsupported Vue.js file type: %s", file_type)
        # Fallback: treat as plain text
        code_chunks.append(
            {
                "text": content,
                "metadata": {
                    "chunk_id": "0",
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": file_type,
                    "chunk_index": 0,
                    "chunk_type": "full_file",
                    "char_count": len(content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

    logger.info("Created %s code chunks and %s doc chunks from Vue.js file", len(code_chunks), len(doc_chunks))
    return code_chunks, doc_chunks
