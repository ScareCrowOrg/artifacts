#!/usr/bin/env python3
"""
Vue.js Single File Component (SFC) Chunking Strategy

Provides specialized chunking for Vue.js .vue files (Single File Components).
Extracts and processes <template>, <script>, and <style> blocks separately.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def chunk_vue_sfc(
    content: str, file_path: Path, document_id: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parse and chunk a Vue Single File Component.

    Extracts:
    - <template> block: HTML template with Tailwind CSS
    - <script> or <script setup> block: Component logic
    - <style> block: Component styles

    Args:
        content: Vue SFC content
        file_path: Source file path
        document_id: Document identifier

    Returns:
        Tuple of (code_chunks, doc_chunks)
    """
    # Import here to avoid circular dependency
    from .vue_javascript_chunker import extract_code_and_comments

    code_chunks = []
    doc_chunks = []

    # Extract blocks using regex
    blocks = extract_vue_blocks(content)

    # Process template block
    if blocks.get("template"):
        template_content = blocks["template"]
        chunk_index = len(code_chunks)
        code_chunks.append(
            {
                "text": template_content,
                "metadata": {
                    "chunk_id": str(chunk_index),
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "vue",
                    "chunk_index": chunk_index,
                    "chunk_type": "vue_template",
                    "char_count": len(template_content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

    # Process script block
    if blocks.get("script"):
        script_content = blocks["script"]
        script_lang = blocks.get("script_lang", "js")

        # Extract JSDoc and comments from script
        script_code_chunks, script_doc_chunks = extract_code_and_comments(
            script_content, file_path, document_id, f"vue_script_{script_lang}"
        )

        # Add main script chunk if not already chunked by function extraction
        if not script_code_chunks:
            chunk_index = len(code_chunks)
            code_chunks.append(
                {
                    "text": script_content,
                    "metadata": {
                        "chunk_id": str(chunk_index),
                        "document_id": document_id,
                        "source": str(file_path),
                        "file_type": "vue",
                        "chunk_index": chunk_index,
                        "chunk_type": f"vue_script_{script_lang}",
                        "char_count": len(script_content),
                        "embedding_model_id": "deepseek-coder",
                        "target_collection": "scareverse_code",
                    },
                }
            )
        else:
            # Re-index script_code_chunks before adding to code_chunks
            for chunk in script_code_chunks:
                chunk_index = len(code_chunks)
                chunk["metadata"]["chunk_id"] = str(chunk_index)
                chunk["metadata"]["chunk_index"] = chunk_index
                code_chunks.append(chunk)

        # Re-index doc_chunks from script before adding to main doc_chunks
        for chunk in script_doc_chunks:
            doc_chunk_index = len(doc_chunks)
            chunk["metadata"]["chunk_id"] = str(doc_chunk_index)
            chunk["metadata"]["chunk_index"] = doc_chunk_index
            doc_chunks.append(chunk)

    # Process style block
    if blocks.get("style"):
        style_content = blocks["style"]
        style_lang = blocks.get("style_lang", "css")
        chunk_index = len(code_chunks)
        code_chunks.append(
            {
                "text": style_content,
                "metadata": {
                    "chunk_id": str(chunk_index),
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "vue",
                    "chunk_index": chunk_index,
                    "chunk_type": f"vue_style_{style_lang}",
                    "char_count": len(style_content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

    # If no blocks found, use full file as single chunk
    if not code_chunks:
        logger.warning("No Vue blocks found in %s, using full file", file_path)
        code_chunks.append(
            {
                "text": content,
                "metadata": {
                    "chunk_id": "0",
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "vue",
                    "chunk_index": 0,
                    "chunk_type": "vue_full_file",
                    "char_count": len(content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

    return code_chunks, doc_chunks


def extract_vue_blocks(content: str) -> Dict[str, Any]:
    """
    Extract <template>, <script>, and <style> blocks from Vue SFC.

    Args:
        content: Vue SFC content

    Returns:
        Dictionary with extracted blocks and their attributes
    """
    blocks = {}

    # Extract template block
    template_match = re.search(
        r"<template(?:\s+[^>]*)?>(.+?)</template>", content, re.DOTALL | re.IGNORECASE
    )
    if template_match:
        blocks["template"] = template_match.group(1).strip()

    # Extract script block (including <script setup>)
    script_match = re.search(
        r"<script(?:\s+([^>]*))?>(.+?)</script>", content, re.DOTALL | re.IGNORECASE
    )
    if script_match:
        script_attrs = script_match.group(1) or ""
        blocks["script"] = script_match.group(2).strip()

        # Detect script language (lang="ts" or lang="js")
        lang_match = re.search(r'lang=["\'](\w+)["\']', script_attrs)
        if lang_match:
            blocks["script_lang"] = lang_match.group(1)
        else:
            blocks["script_lang"] = "js"

        # Detect setup attribute
        blocks["script_setup"] = "setup" in script_attrs

    # Extract style block
    style_match = re.search(
        r"<style(?:\s+([^>]*))?>(.+?)</style>", content, re.DOTALL | re.IGNORECASE
    )
    if style_match:
        style_attrs = style_match.group(1) or ""
        blocks["style"] = style_match.group(2).strip()

        # Detect style language (lang="scss", lang="css", etc.)
        lang_match = re.search(r'lang=["\'](\w+)["\']', style_attrs)
        if lang_match:
            blocks["style_lang"] = lang_match.group(1)
        else:
            blocks["style_lang"] = "css"

    return blocks
