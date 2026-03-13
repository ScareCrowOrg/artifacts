#!/usr/bin/env python3
"""
Markdown Chunking Strategy

Provides semantic chunking for Markdown documents based on header structure.
Optimized for the documentation collection (scareverse_docs) with Mistral embeddings.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

logger = logging.getLogger(__name__)


def chunk_markdown(
    content: str,
    file_path: Path,
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Dict[str, Any]]:
    """
    Chunk markdown content using header-based semantic splitting.

    This strategy:
    - Splits on headers (H1, H2, H3) to maintain semantic coherence
    - Removes special characters and noise to optimize embeddings
    - Targets the documentation collection (scareverse_docs)

    Args:
        content: Markdown content to chunk
        file_path: Source file path
        document_id: Unique document identifier
        chunk_size: Maximum chunk size
        chunk_overlap: Overlap between chunks

    Returns:
        List of chunk dictionaries with content and metadata
    """
    logger.info("Chunking markdown content with MarkdownHeaderTextSplitter")

    # Define headers to split on
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]

    # Create markdown splitter
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False
    )

    # Split on headers
    md_header_splits = markdown_splitter.split_text(content)

    # Further split large sections with RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    for idx, doc in enumerate(md_header_splits):
        # Clean content: remove excessive special characters and noise
        cleaned_content = _clean_markdown_content(doc.page_content)

        # If section is large, split further
        if len(cleaned_content) > chunk_size:
            sub_chunks = text_splitter.split_text(cleaned_content)
            for sub_idx, sub_chunk in enumerate(sub_chunks):
                chunk_metadata = {
                    "chunk_id": f"{idx}_{sub_idx}",
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "markdown",
                    "chunk_index": len(chunks),
                    "char_count": len(sub_chunk),
                    "embedding_model_id": "mistral",
                    "target_collection": "scareverse_docs",
                    **doc.metadata,
                }
                chunks.append({"text": sub_chunk, "metadata": chunk_metadata})
        else:
            chunk_metadata = {
                "chunk_id": str(idx),
                "document_id": document_id,
                "source": str(file_path),
                "file_type": "markdown",
                "chunk_index": len(chunks),
                "char_count": len(cleaned_content),
                "embedding_model_id": "mistral",
                "target_collection": "scareverse_docs",
                **doc.metadata,
            }
            chunks.append({"text": cleaned_content, "metadata": chunk_metadata})

    logger.info("Created %s markdown chunks", len(chunks))
    return chunks


def _clean_markdown_content(content: str) -> str:
    """
    Clean markdown content by removing noise and special characters.

    This improves embedding quality for Mistral model.

    Args:
        content: Raw markdown content

    Returns:
        Cleaned content
    """
    # Remove excessive newlines (more than 2)
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Remove markdown image syntax but keep alt text
    content = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", content)

    # Clean up excessive whitespace
    content = re.sub(r"[ \t]+", " ", content)

    # Remove trailing/leading whitespace from lines
    lines = [line.strip() for line in content.split("\n")]
    content = "\n".join(lines)

    return content.strip()
