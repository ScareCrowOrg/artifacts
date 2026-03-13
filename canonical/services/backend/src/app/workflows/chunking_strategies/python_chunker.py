#!/usr/bin/env python3
"""
Python Code Chunking Strategy

Provides AST-based chunking for Python source code files.
Extracts functions, classes, and docstrings for dual collection ingestion.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def chunk_python_code(
    content: str, file_path: Path, document_id: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Chunk Python code using AST (Abstract Syntax Tree) analysis.

    This strategy:
    - Parses Python code into an AST
    - Extracts functions, classes, and methods as complete units
    - Includes docstrings with code chunks for context
    - Separately extracts docstrings for documentation collection

    Returns two lists:
    - code_chunks: For scareverse_code collection (deepseek-coder)
    - doc_chunks: Docstrings for scareverse_docs collection (mistral)

    Args:
        content: Python source code
        file_path: Source file path
        document_id: Unique document identifier

    Returns:
        Tuple of (code_chunks, doc_chunks)
    """
    logger.info("Chunking Python code with AST-based strategy")

    code_chunks = []
    doc_chunks = []

    try:
        # Parse the Python code into an AST
        tree = ast.parse(content)

        # Extract module-level docstring
        module_docstring = ast.get_docstring(tree)
        if module_docstring:
            doc_chunks.append(
                {
                    "text": module_docstring,
                    "metadata": {
                        "chunk_id": "0",
                        "document_id": document_id,
                        "source": str(file_path),
                        "file_type": "python_docstring",
                        "chunk_index": 0,
                        "chunk_type": "module_docstring",
                        "embedding_model_id": "mistral",
                        "target_collection": "scareverse_docs",
                    },
                }
            )

        # Extract classes and functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                _extract_code_and_docstring(
                    node, content, file_path, document_id, code_chunks, doc_chunks
                )

        # If no functions/classes found, chunk as whole file
        if not code_chunks:
            logger.info("No functions/classes found, creating single code chunk")
            code_chunks.append(
                {
                    "text": content,
                    "metadata": {
                        "chunk_id": "0",
                        "document_id": document_id,
                        "source": str(file_path),
                        "file_type": "python",
                        "chunk_index": 0,
                        "chunk_type": "full_file",
                        "char_count": len(content),
                        "embedding_model_id": "deepseek-coder",
                        "target_collection": "scareverse_code",
                    },
                }
            )

    except SyntaxError as e:
        logger.warning("Failed to parse Python file %s: %s", file_path, e)
        logger.info("Falling back to simple chunking")
        # Fallback: treat as plain text with simple chunking
        code_chunks.append(
            {
                "text": content,
                "metadata": {
                    "chunk_id": "0",
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "python",
                    "chunk_index": 0,
                    "chunk_type": "unparseable",
                    "char_count": len(content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                    "parse_error": str(e),
                },
            }
        )

    logger.info("Created %s code chunks and %s doc chunks from Python file", len(code_chunks), len(doc_chunks))
    return code_chunks, doc_chunks


def _extract_code_and_docstring(
    node: ast.AST,
    full_content: str,
    file_path: Path,
    document_id: str,
    code_chunks: List[Dict[str, Any]],
    doc_chunks: List[Dict[str, Any]],
) -> None:
    """
    Extract code and docstring from an AST node (function, class, method).

    Args:
        node: AST node (FunctionDef, AsyncFunctionDef, or ClassDef)
        full_content: Full source code content
        file_path: Source file path
        document_id: Document identifier
        code_chunks: List to append code chunks to
        doc_chunks: List to append doc chunks to
    """
    # Get the source code for this node
    try:
        # Get line numbers
        start_line = node.lineno - 1  # 0-indexed
        end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line + 1

        # Extract source lines
        lines = full_content.split("\n")
        source_lines = lines[start_line:end_line]
        source_code = "\n".join(source_lines)

        # Get node name
        node_name = node.name if hasattr(node, "name") else "unknown"
        node_type = type(node).__name__.replace("Def", "").lower()

        # Extract docstring
        docstring = ast.get_docstring(node)

        # Add code chunk (with docstring included for context)
        code_chunk_index = len(code_chunks)
        code_chunks.append(
            {
                "text": source_code,
                "metadata": {
                    "chunk_id": str(code_chunk_index),
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "python",
                    "chunk_index": code_chunk_index,
                    "chunk_type": node_type,
                    "node_name": node_name,
                    "start_line": start_line + 1,
                    "end_line": end_line,
                    "char_count": len(source_code),
                    "has_docstring": docstring is not None,
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

        # Add docstring as separate doc chunk
        if docstring:
            doc_chunk_index = len(doc_chunks)
            doc_chunks.append(
                {
                    "text": docstring,
                    "metadata": {
                        "chunk_id": str(doc_chunk_index),
                        "document_id": document_id,
                        "source": str(file_path),
                        "file_type": "python_docstring",
                        "chunk_index": doc_chunk_index,
                        "chunk_type": f"{node_type}_docstring",
                        "node_name": node_name,
                        "embedding_model_id": "mistral",
                        "target_collection": "scareverse_docs",
                    },
                }
            )

    except Exception as e:
        logger.warning("Failed to extract code from node %s: %s", type(node).__name__, e)
