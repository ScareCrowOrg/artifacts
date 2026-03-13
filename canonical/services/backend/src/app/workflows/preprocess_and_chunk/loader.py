"""
File Loading Module

This module handles loading file content from different file types.
It supports text files, PDFs, and various document formats.
"""

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_document_id() -> str:
    """Generate a unique document ID."""
    return str(uuid.uuid4())


def load_file_content(file_path: Path, file_type: str) -> str:
    """
    Load the content of a file based on its type.

    Args:
        file_path: Path to the file to load
        file_type: Type of the file (e.g., 'markdown', 'python', 'pdf')

    Returns:
        File content as string

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file type is not supported
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_type_lower = file_type.lower()

    # Handle PDF files
    if file_type_lower == "pdf":
        try:
            from pypdf import PdfReader

            logger.info("Loading PDF file: %s", file_path)
            reader = PdfReader(str(file_path))
            text_parts = []
            for _page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            content = "\n".join(text_parts)
            logger.info("Loaded %s pages from PDF", len(reader.pages))
            return content
        except ImportError:
            logger.warning("pypdf not available, attempting text read")
            # Fallback to text read (won't work well for binary PDFs)
            pass

    # Handle text-based files
    try:
        logger.info("Loading text file: %s", file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info("Loaded %s characters from file", len(content))
        return content
    except UnicodeDecodeError:
        logger.error("Failed to decode file as UTF-8: %s", file_path)
        raise ValueError(f"File is not UTF-8 encoded: {file_path}")
