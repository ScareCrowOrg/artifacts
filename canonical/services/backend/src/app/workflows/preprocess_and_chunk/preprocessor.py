"""
Text Preprocessing Module

This module handles text preprocessing operations such as
normalizing line endings and removing excessive blank lines.
"""

import logging

logger = logging.getLogger(__name__)


def preprocess_text(content: str) -> str:
    """
    Perform basic text preprocessing.

    Args:
        content: Raw text content

    Returns:
        Preprocessed text
    """
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive blank lines (more than 2 consecutive)
    lines = content.split("\n")
    processed_lines = []
    blank_count = 0

    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                processed_lines.append(line)
        else:
            blank_count = 0
            processed_lines.append(line)

    content = "\n".join(processed_lines)

    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in content.split("\n")]
    content = "\n".join(lines)

    logger.info("Preprocessed content: %s characters", len(content))
    return content
