"""
Output Handler Module

This module handles saving chunks to JSON files.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def save_chunks_to_separate_json_files(
    doc_chunks: List[Dict[str, Any]],
    code_chunks: List[Dict[str, Any]],
    output_dir: Path,
    document_id: str,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Save doc and code chunks to separate JSON files.

    Args:
        doc_chunks: List of documentation chunk dictionaries
        code_chunks: List of code chunk dictionaries
        output_dir: Directory to save the JSON files
        document_id: Document ID to use in filenames

    Returns:
        Tuple of (doc_chunks_path, code_chunks_path), either can be None if no chunks
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    doc_chunks_path = None
    code_chunks_path = None

    if doc_chunks:
        doc_chunks_path = output_dir / f"{document_id}_doc_chunks.json"
        with open(doc_chunks_path, "w", encoding="utf-8") as f:
            json.dump(doc_chunks, f, indent=2, ensure_ascii=False)
        logger.info("Saved %s doc chunks to %s", len(doc_chunks), doc_chunks_path)

    if code_chunks:
        code_chunks_path = output_dir / f"{document_id}_code_chunks.json"
        with open(code_chunks_path, "w", encoding="utf-8") as f:
            json.dump(code_chunks, f, indent=2, ensure_ascii=False)
        logger.info("Saved %s code chunks to %s", len(code_chunks), code_chunks_path)

    return doc_chunks_path, code_chunks_path


def save_chunks_to_json(
    chunks: List[Dict[str, Any]], output_dir: Path, document_id: str
) -> Path:
    """
    Save chunks to a JSON file.

    Args:
        chunks: List of chunk dictionaries with 'text' and 'metadata'
        output_dir: Directory to save the JSON file
        document_id: Document ID to use in filename

    Returns:
        Path to the saved JSON file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{document_id}_chunks.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    logger.info("Saved %s chunks to %s", len(chunks), output_file)
    return output_file
