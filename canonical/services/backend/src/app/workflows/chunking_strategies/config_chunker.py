#!/usr/bin/env python3
"""
Configuration File Chunking Strategy

Provides structured chunking for configuration files (YAML, JSON, .env).
Splits content by logical sections to maintain configuration context.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def chunk_configuration_file(
    content: str, file_path: Path, document_id: str, file_type: str
) -> List[Dict[str, Any]]:
    """
    Chunk configuration files (YAML, JSON, .env) in a structured way.

    This strategy:
    - For YAML: Splits by top-level keys
    - For JSON: Splits by top-level keys
    - For .env: Groups related environment variables

    Args:
        content: Configuration file content
        file_path: Source file path
        document_id: Unique document identifier
        file_type: Type of configuration file (yaml, json, env)

    Returns:
        List of chunk dictionaries
    """
    logger.info("Chunking %s configuration file", file_type)

    chunks = []

    if file_type in ["yaml", "yml"]:
        chunks = _chunk_yaml_content(content, file_path, document_id)
    elif file_type == "json":
        chunks = _chunk_json_content(content, file_path, document_id)
    elif file_type == "env":
        chunks = _chunk_env_content(content, file_path, document_id)
    else:
        # Fallback: treat as plain text
        chunks.append(
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

    logger.info("Created %s configuration chunks", len(chunks))
    return chunks


def _chunk_yaml_content(
    content: str, file_path: Path, document_id: str
) -> List[Dict[str, Any]]:
    """Chunk YAML content by top-level blocks."""
    chunks = []

    try:
        import yaml

        data = yaml.safe_load(content)

        if isinstance(data, dict):
            for key, value in data.items():
                chunk_content = yaml.dump({key: value}, default_flow_style=False)
                chunk_index = len(chunks)
                chunks.append(
                    {
                        "text": chunk_content,
                        "metadata": {
                            "chunk_id": str(chunk_index),
                            "document_id": document_id,
                            "source": str(file_path),
                            "file_type": "yaml",
                            "chunk_index": chunk_index,
                            "chunk_type": "yaml_block",
                            "yaml_key": key,
                            "char_count": len(chunk_content),
                            "embedding_model_id": "deepseek-coder",
                            "target_collection": "scareverse_code",
                        },
                    }
                )
        else:
            # Not a dict, use whole content
            chunks.append(
                {
                    "text": content,
                    "metadata": {
                        "chunk_id": "0",
                        "document_id": document_id,
                        "source": str(file_path),
                        "file_type": "yaml",
                        "chunk_index": 0,
                        "chunk_type": "full_file",
                        "char_count": len(content),
                        "embedding_model_id": "deepseek-coder",
                        "target_collection": "scareverse_code",
                    },
                }
            )
    except Exception as e:
        logger.warning("Failed to parse YAML: %s, using full content", e)
        chunks.append(
            {
                "text": content,
                "metadata": {
                    "chunk_id": "0",
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "yaml",
                    "chunk_index": 0,
                    "chunk_type": "unparseable",
                    "char_count": len(content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

    return chunks


def _chunk_json_content(
    content: str, file_path: Path, document_id: str
) -> List[Dict[str, Any]]:
    """Chunk JSON content by top-level keys."""
    chunks = []

    try:
        data = json.loads(content)

        if isinstance(data, dict):
            for key, value in data.items():
                chunk_content = json.dumps({key: value}, indent=2, ensure_ascii=False)
                chunk_index = len(chunks)
                chunks.append(
                    {
                        "text": chunk_content,
                        "metadata": {
                            "chunk_id": str(chunk_index),
                            "document_id": document_id,
                            "source": str(file_path),
                            "file_type": "json",
                            "chunk_index": chunk_index,
                            "chunk_type": "json_block",
                            "json_key": key,
                            "char_count": len(chunk_content),
                            "embedding_model_id": "deepseek-coder",
                            "target_collection": "scareverse_code",
                        },
                    }
                )
        else:
            # Not a dict, use whole content
            chunks.append(
                {
                    "text": content,
                    "metadata": {
                        "chunk_id": "0",
                        "document_id": document_id,
                        "source": str(file_path),
                        "file_type": "json",
                        "chunk_index": 0,
                        "chunk_type": "full_file",
                        "char_count": len(content),
                        "embedding_model_id": "deepseek-coder",
                        "target_collection": "scareverse_code",
                    },
                }
            )
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse JSON: %s, using full content", e)
        chunks.append(
            {
                "text": content,
                "metadata": {
                    "chunk_id": "0",
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "json",
                    "chunk_index": 0,
                    "chunk_type": "unparseable",
                    "char_count": len(content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

    return chunks


def _chunk_env_content(
    content: str, file_path: Path, document_id: str
) -> List[Dict[str, Any]]:
    """Chunk .env content by grouping related variables."""
    chunks = []

    lines = content.split("\n")
    current_chunk_lines = []
    current_group = None

    for line in lines:
        line = line.strip()

        # Skip empty lines and comments at the start
        if not line or line.startswith("#"):
            if current_chunk_lines:
                current_chunk_lines.append(line)
            continue

        # Detect variable name
        if "=" in line:
            var_name = line.split("=")[0].strip()
            # Extract prefix (group)
            prefix = var_name.split("_")[0] if "_" in var_name else "general"

            # Start new chunk if group changes
            if current_group and prefix != current_group and current_chunk_lines:
                chunk_content = "\n".join(current_chunk_lines)
                chunk_index = len(chunks)
                chunks.append(
                    {
                        "text": chunk_content,
                        "metadata": {
                            "chunk_id": str(chunk_index),
                            "document_id": document_id,
                            "source": str(file_path),
                            "file_type": "env",
                            "chunk_index": chunk_index,
                            "chunk_type": "env_group",
                            "env_group": current_group,
                            "char_count": len(chunk_content),
                            "embedding_model_id": "deepseek-coder",
                            "target_collection": "scareverse_code",
                        },
                    }
                )
                current_chunk_lines = []

            current_group = prefix

        current_chunk_lines.append(line)

    # Add final chunk
    if current_chunk_lines:
        chunk_content = "\n".join(current_chunk_lines)
        chunk_index = len(chunks)
        chunks.append(
            {
                "text": chunk_content,
                "metadata": {
                    "chunk_id": str(chunk_index),
                    "document_id": document_id,
                    "source": str(file_path),
                    "file_type": "env",
                    "chunk_index": chunk_index,
                    "chunk_type": "env_group",
                    "env_group": current_group or "general",
                    "char_count": len(chunk_content),
                    "embedding_model_id": "deepseek-coder",
                    "target_collection": "scareverse_code",
                },
            }
        )

    return chunks
