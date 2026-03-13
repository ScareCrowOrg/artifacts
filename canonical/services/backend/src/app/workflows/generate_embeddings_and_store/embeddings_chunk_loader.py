"""
Chunk Loading and Validation

Loads preprocessed chunks from JSON files with Pydantic validation.
Uses the Chunk schema to ensure type safety and validate chunk structure.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from pydantic import ValidationError

from ..models import Chunk

logger = logging.getLogger(__name__)


def load_chunks_from_json(chunks_json_path: str) -> List[Dict[str, Any]]:
    """
    Load preprocessed chunks from JSON file with Pydantic validation.

    This function loads chunks from JSON and validates them against the Chunk schema,
    ensuring type safety and catching malformed chunks early with clear error messages.

    Args:
        chunks_json_path: Path to the JSON file containing chunks

    Returns:
        List of chunk dictionaries with 'text' and 'metadata' keys

    Raises:
        FileNotFoundError: If chunks file doesn't exist
        ValueError: If JSON format is invalid or chunks don't conform to schema
    """
    chunks_path = Path(chunks_json_path)

    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_json_path}")

    logger.info("Loading chunks from: %s", chunks_json_path)

    # Load JSON data
    try:
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in chunks file: {e}") from e

    # Validate chunks format
    if not isinstance(chunks_data, list):
        raise ValueError("Chunks JSON must be a list of chunk objects")

    # Validate each chunk against Pydantic schema
    validated_chunks = []
    for i, chunk_dict in enumerate(chunks_data):
        if not isinstance(chunk_dict, dict):
            raise ValueError(f"Chunk {i} must be a dictionary")

        try:
            # Validate chunk using Pydantic model
            chunk = Chunk.from_dict(chunk_dict)
            # Convert back to dict for downstream compatibility
            validated_chunks.append(chunk.to_dict())
        except ValidationError as e:
            # Provide detailed error message with chunk index
            error_details = []
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                message = error["msg"]
                error_details.append(f"{field}: {message}")

            error_message = f"Chunk {i} validation failed:\n  " + "\n  ".join(
                error_details
            )
            raise ValueError(error_message) from e

    logger.info("Loaded and validated %s chunks successfully", len(validated_chunks))
    return validated_chunks
