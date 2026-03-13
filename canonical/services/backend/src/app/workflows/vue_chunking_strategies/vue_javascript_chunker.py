#!/usr/bin/env python3
"""
Vue.js JavaScript/TypeScript Chunking Strategy

Provides specialized chunking for Vue.js ecosystem JavaScript/TypeScript files.
Extracts composables, Pinia stores, functions, and JSDoc documentation.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def chunk_javascript_file(
    content: str, file_path: Path, document_id: str, file_type: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Chunk JavaScript/TypeScript file (composables, Pinia stores, etc.).

    Extracts:
    - Exported functions (composables like useXxx)
    - Pinia store definitions (defineStore)
    - Regular functions and classes
    - JSDoc and comments

    Args:
        content: JavaScript/TypeScript content
        file_path: Source file path
        document_id: Document identifier
        file_type: 'js' or 'ts'

    Returns:
        Tuple of (code_chunks, doc_chunks)
    """
    code_chunks = []
    doc_chunks = []

    # Determine chunk type based on file path
    chunk_type_prefix = infer_js_chunk_type(file_path)

    # Extract code and comments
    code_chunks, doc_chunks = extract_code_and_comments(
        content, file_path, document_id, chunk_type_prefix
    )

    # If no functions/exports found, use full file
    if not code_chunks:
        code_chunks.append(
            {
                "text": content,
                "metadata": {
                    "chunk_id": "0",
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": file_type,
                    "chunk_index": 0,
                    "chunk_type": f"{chunk_type_prefix}_full_file",
                    "char_count": len(content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

    return code_chunks, doc_chunks


def infer_js_chunk_type(file_path: Path) -> str:
    """
    Infer the chunk type based on file path patterns.

    Args:
        file_path: Path to the JavaScript/TypeScript file

    Returns:
        Chunk type prefix (e.g., 'vue_composable', 'vue_pinia_store')
    """
    path_str = str(file_path).lower()

    if "composables" in path_str or "composable" in path_str:
        return "vue_composable"
    elif "stores" in path_str or "store" in path_str:
        return "vue_pinia_store"
    elif "components" in path_str:
        return "vue_component_script"
    else:
        return "vue_javascript"


def extract_code_and_comments(
    content: str, file_path: Path, document_id: str, chunk_type_prefix: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extract code units and documentation comments from JavaScript/TypeScript.

    Uses simple regex-based parsing to extract:
    - Exported functions (export function, export const)
    - JSDoc blocks (/** ... */)
    - Inline comments for context

    Args:
        content: JavaScript/TypeScript content
        file_path: Source file path
        document_id: Document identifier
        chunk_type_prefix: Prefix for chunk_type metadata

    Returns:
        Tuple of (code_chunks, doc_chunks)
    """
    code_chunks = []
    doc_chunks = []

    # Extract all JSDoc blocks and associate with following code
    jsdoc_pattern = r"/\*\*(.+?)\*/"
    jsdoc_matches = list(re.finditer(jsdoc_pattern, content, re.DOTALL))

    # Extract exported functions
    # Patterns: export function name(...) { ... }
    #          export const name = (...) => { ... }
    #          export default function(...) { ... }

    # Pattern 1: export function functionName
    export_func_pattern = r"(export\s+(?:default\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{)"

    # Pattern 2: export const functionName =
    export_const_pattern = (
        r"(export\s+const\s+(\w+)\s*=\s*(?:function\s*\(|\([^)]*\)\s*=>))"
    )

    # Pattern 3: defineStore for Pinia stores
    define_store_pattern = r"(export\s+const\s+(\w+)\s*=\s*defineStore\s*\()"

    # Combine all patterns
    combined_patterns = [
        (export_func_pattern, "function"),
        (export_const_pattern, "function"),
        (define_store_pattern, "pinia_store"),
    ]

    extracted_functions = []

    for pattern, func_type in combined_patterns:
        for match in re.finditer(pattern, content):
            start_pos = match.start()
            func_name = match.group(2)

            # Find the end of the function (matching braces)
            func_content = extract_function_body(content, start_pos)

            if func_content:
                # Find associated JSDoc
                jsdoc_content = find_preceding_jsdoc(content, start_pos, jsdoc_matches)

                # Create code chunk (includes JSDoc for context)
                full_code = (
                    f"{jsdoc_content}\n{func_content}"
                    if jsdoc_content
                    else func_content
                )
                code_chunk_index = len(code_chunks)

                code_chunks.append(
                    {
                        "text": full_code,
                        "metadata": {
                            "chunk_id": str(code_chunk_index),
                            "document_id": document_id,
                            "source": str(file_path),
                            "file_type": "javascript",
                            "chunk_index": code_chunk_index,
                            "chunk_type": f"{chunk_type_prefix}_{func_type}",
                            "function_name": func_name,
                            "char_count": len(full_code),
                            "has_jsdoc": jsdoc_content is not None,
                            "embedding_model_id": "deepseek-coder",
                            "target_collection": "scareverse_code",
                        },
                    }
                )

                # Create separate doc chunk from JSDoc
                if jsdoc_content:
                    doc_chunk_index = len(doc_chunks)
                    doc_chunks.append(
                        {
                            "text": jsdoc_content,
                            "metadata": {
                                "chunk_id": str(doc_chunk_index),
                                "document_id": document_id,
                                "source": str(file_path),
                                "file_type": "javascript_jsdoc",
                                "chunk_index": doc_chunk_index,
                                "chunk_type": f"{chunk_type_prefix}_jsdoc",
                                "function_name": func_name,
                                "embedding_model_id": "mistral",
                                "target_collection": "scareverse_docs",
                            },
                        }
                    )

                extracted_functions.append((start_pos, start_pos + len(func_content)))

    # Extract standalone JSDoc blocks (not associated with functions)
    for jsdoc_match in jsdoc_matches:
        jsdoc_start = jsdoc_match.start()
        jsdoc_content = jsdoc_match.group(0)

        # Check if this JSDoc is already associated with a function
        is_standalone = True
        for func_start, _func_end in extracted_functions:
            if jsdoc_start < func_start and jsdoc_start > func_start - 500:
                is_standalone = False
                break

        if is_standalone and len(jsdoc_content.strip()) > 50:  # Only meaningful docs
            doc_chunk_index = len(doc_chunks)
            doc_chunks.append(
                {
                    "text": jsdoc_content,
                    "metadata": {
                        "chunk_id": str(doc_chunk_index),
                        "document_id": document_id,
                        "source": str(file_path),
                        "file_type": "javascript_jsdoc",
                        "chunk_index": doc_chunk_index,
                        "chunk_type": f"{chunk_type_prefix}_standalone_jsdoc",
                        "embedding_model_id": "mistral",
                        "target_collection": "scareverse_docs",
                    },
                }
            )

    return code_chunks, doc_chunks


def extract_function_body(content: str, start_pos: int) -> Optional[str]:
    """
    Extract the complete function body by matching braces.

    Args:
        content: Full file content
        start_pos: Starting position of the function

    Returns:
        Function body as string, or None if extraction fails
    """
    # Find the first opening brace
    brace_start = content.find("{", start_pos)
    if brace_start == -1:
        return None

    # Count braces to find matching closing brace
    brace_count = 0
    pos = brace_start
    in_string = False
    in_comment = False
    string_char = None

    while pos < len(content):
        char = content[pos]

        # Handle strings
        if char in ['"', "'", "`"] and not in_comment:
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char and content[pos - 1] != "\\":
                in_string = False

        # Handle comments
        if not in_string:
            if char == "/" and pos + 1 < len(content):
                next_char = content[pos + 1]
                if next_char == "/" or next_char == "*":
                    in_comment = True
            elif in_comment and char == "\n":
                in_comment = False

        # Count braces
        if not in_string and not in_comment:
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    # Found matching closing brace
                    return content[start_pos : pos + 1]

        pos += 1

    # Could not find matching brace
    return None


def find_preceding_jsdoc(
    content: str, func_start: int, jsdoc_matches: List
) -> Optional[str]:
    """
    Find JSDoc block immediately preceding a function.

    Args:
        content: Full file content
        func_start: Starting position of the function
        jsdoc_matches: List of JSDoc regex match objects

    Returns:
        JSDoc content as string, or None if not found
    """
    # Look for JSDoc within 500 characters before function
    search_start = max(0, func_start - 500)

    for match in jsdoc_matches:
        jsdoc_end = match.end()

        # Check if this JSDoc is right before the function
        if search_start <= jsdoc_end <= func_start:
            # Verify there's only whitespace between JSDoc and function
            between = content[jsdoc_end:func_start]
            if between.strip() == "":
                return match.group(0)

    return None
