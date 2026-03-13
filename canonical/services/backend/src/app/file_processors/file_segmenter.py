"""
File Segmenter Module

Segments large files into smaller chunks based on token limits.
Handles Python (.py) and YAML (.yml, .yaml) files with structure-aware segmentation.

Technical naming: All functions and variables in English.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List

from .content_minimizer import (
    remove_python_comments_and_docstrings,
    remove_yaml_comments,
    should_minimize_file,
)
from .token_counter import DEFAULT_MAX_TOKENS, count_tokens

logger = logging.getLogger(__name__)


def segment_python_file(
    code: str, max_tokens: int = DEFAULT_MAX_TOKENS, model: str = "gpt-3.5-turbo"
) -> List[Dict[str, Any]]:
    """
    Segment Python code into logical chunks based on token limits.

    Splits by functions, classes, and top-level statements to maintain code structure.
    Each segment includes metadata for context preservation.

    Args:
        code: Python source code
        max_tokens: Maximum tokens per segment
        model: OpenAI model name for token counting

    Returns:
        List of segment dicts with 'content', 'type', 'name', and 'tokens' keys

    Example:
        >>> code = '''
        ... def func1():
        ...     pass
        ...
        ... def func2():
        ...     pass
        ... '''
        >>> segments = segment_python_file(code, max_tokens=50)
        >>> len(segments) >= 1
        True
        >>> segments[0]['type'] in ['function', 'class', 'module']
        True
    """
    segments = []

    try:
        # Parse the code into an AST
        tree = ast.parse(code)

        # Extract top-level definitions
        for node in tree.body:
            segment_content = ast.get_source_segment(code, node)

            if segment_content:
                tokens = count_tokens(segment_content, model)

                # Determine segment type and name
                if isinstance(node, ast.FunctionDef):
                    seg_type = "function"
                    seg_name = node.name
                elif isinstance(node, ast.AsyncFunctionDef):
                    seg_type = "async_function"
                    seg_name = node.name
                elif isinstance(node, ast.ClassDef):
                    seg_type = "class"
                    seg_name = node.name
                else:
                    seg_type = "statement"
                    seg_name = f"line_{node.lineno}"

                # Warn if segment exceeds max_tokens
                if tokens > max_tokens:
                    logger.warning(
                        f"Segment {seg_name} ({tokens} tokens) exceeds limit. "
                        "Consider manual splitting or increasing max_tokens."
                    )

                segments.append(
                    {
                        "content": segment_content,
                        "type": seg_type,
                        "name": seg_name,
                        "tokens": tokens,
                        "line_start": node.lineno,
                        "line_end": node.end_lineno,
                    }
                )

        # If no segments created, return full code as one segment
        if not segments:
            segments.append(
                {
                    "content": code,
                    "type": "module",
                    "name": "full_file",
                    "tokens": count_tokens(code, model),
                    "line_start": 1,
                    "line_end": len(code.split("\n")),
                }
            )

    except SyntaxError as e:
        logger.error("Failed to parse Python code: %s", e)
        # Return full code as single segment if parsing fails
        segments.append(
            {
                "content": code,
                "type": "unparseable",
                "name": "full_file",
                "tokens": count_tokens(code, model),
                "line_start": 1,
                "line_end": len(code.split("\n")),
            }
        )

    return segments


def segment_yaml_file(
    yaml_content: str,
    _max_tokens: int = DEFAULT_MAX_TOKENS,
    model: str = "gpt-3.5-turbo",
) -> List[Dict[str, Any]]:
    """
    Segment YAML content into logical sections based on token limits.

    Splits by top-level keys to maintain YAML structure.
    Each segment includes metadata for context preservation.

    Args:
        yaml_content: YAML source content
        max_tokens: Maximum tokens per segment
        model: OpenAI model name for token counting

    Returns:
        List of segment dicts with 'content', 'key', and 'tokens'

    Example:
        >>> yaml = '''
        ... section1:
        ...   key: value
        ... section2:
        ...   key: value
        ... '''
        >>> segments = segment_yaml_file(yaml, max_tokens=50)
        >>> len(segments) >= 1
        True
    """
    segments = []

    try:
        import yaml

        # Parse YAML to understand structure
        data = yaml.safe_load(yaml_content)

        if isinstance(data, dict):
            # Split by top-level keys
            lines = yaml_content.split("\n")
            current_section = []
            current_key = None
            _current_indent = 0

            for line in lines:
                # Detect top-level key (no indentation or minimal indentation)
                stripped = line.lstrip()
                indent = len(line) - len(stripped)

                if (
                    stripped
                    and ":" in stripped
                    and (indent == 0 or (current_key is None))
                ):
                    # This is a new top-level key
                    if current_section and current_key:
                        # Save previous section
                        section_content = "\n".join(current_section)
                        tokens = count_tokens(section_content, model)

                        segments.append(
                            {
                                "content": section_content,
                                "key": current_key,
                                "tokens": tokens,
                                "type": "section",
                            }
                        )

                    # Start new section
                    current_key = stripped.split(":")[0].strip()
                    current_section = [line]
                    current_indent = indent
                else:
                    # Continue current section
                    current_section.append(line)

            # Save last section
            if current_section and current_key:
                section_content = "\n".join(current_section)
                tokens = count_tokens(section_content, model)

                segments.append(
                    {
                        "content": section_content,
                        "key": current_key,
                        "tokens": tokens,
                        "type": "section",
                    }
                )

        # If no segments created, return full content
        if not segments:
            segments.append(
                {
                    "content": yaml_content,
                    "key": "full_file",
                    "tokens": count_tokens(yaml_content, model),
                    "type": "full",
                }
            )

    except ImportError:
        logger.warning("PyYAML not available, using simple segmentation")
        segments.append(
            {
                "content": yaml_content,
                "key": "full_file",
                "tokens": count_tokens(yaml_content, model),
                "type": "full",
            }
        )
    except Exception as e:
        logger.error("Failed to parse YAML: %s", e)
        segments.append(
            {
                "content": yaml_content,
                "key": "full_file",
                "tokens": count_tokens(yaml_content, model),
                "type": "full",
            }
        )

    return segments


def _simple_segment(content: str, max_tokens: int, model: str) -> List[Dict[str, Any]]:
    """
    Simple line-based segmentation for generic files.

    Splits content by lines, keeping segments under token limit.

    Args:
        content: File content
        max_tokens: Maximum tokens per segment
        model: Model name for token counting

    Returns:
        List of segment dicts
    """
    segments = []
    lines = content.split("\n")
    current_chunk = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line + "\n", model)

        if current_tokens + line_tokens > max_tokens and current_chunk:
            # Save current chunk
            chunk_content = "\n".join(current_chunk)
            segments.append(
                {
                    "content": chunk_content,
                    "type": "chunk",
                    "name": f"chunk_{len(segments)}",
                    "tokens": current_tokens,
                }
            )

            # Start new chunk
            current_chunk = [line]
            current_tokens = line_tokens
        else:
            current_chunk.append(line)
            current_tokens += line_tokens

    # Save last chunk
    if current_chunk:
        chunk_content = "\n".join(current_chunk)
        segments.append(
            {
                "content": chunk_content,
                "type": "chunk",
                "name": f"chunk_{len(segments)}",
                "tokens": current_tokens,
            }
        )

    return segments


def process_file_for_openai(
    file_content: str,
    file_name: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    minimize_docs: bool = True,
    model: str = "gpt-3.5-turbo",
) -> List[Dict[str, Any]]:
    """
    Process file content for optimal OpenAI API transmission.

    Main entry point for file processing. Steps:
    1. Detect file type from extension
    2. Optionally minimize documentation/comments
    3. Segment large files if needed
    4. Return list of content parts ready for API transmission

    Args:
        file_content: Raw file content
        file_name: File name (used to detect type)
        max_tokens: Maximum tokens per segment
        minimize_docs: Whether to remove comments/docstrings
        model: OpenAI model name

    Returns:
        List of content segments, each with 'content', 'metadata', and 'tokens'

    Raises:
        ValueError: If file content is empty or invalid

    Example:
        >>> python_code = '''
        ... def hello():
        ...     \"\"\"Greet\"\"\"
        ...     print("hi")
        ... '''
        >>> segments = process_file_for_openai(python_code, "test.py")
        >>> len(segments) >= 1
        True
        >>> segments[0]['metadata']['file_type'] == 'py'
        True
    """
    if not file_content or not file_content.strip():
        raise ValueError("File content is empty")

    # Detect file type
    file_path = Path(file_name)
    file_ext = file_path.suffix.lower()

    # Apply documentation minimization if requested
    processed_content = file_content

    if minimize_docs and should_minimize_file(file_name):
        if file_ext == ".py":
            logger.info("Minimizing documentation for Python file: %s", file_name)
            processed_content = remove_python_comments_and_docstrings(file_content)
        elif file_ext in [".yml", ".yaml"]:
            logger.info("Minimizing comments for YAML file: %s", file_name)
            processed_content = remove_yaml_comments(file_content)

    # Check if segmentation is needed
    total_tokens = count_tokens(processed_content, model)

    logger.info(
        "Processing file %s: %s chars, %s tokens (limit: %s)",
        file_name, len(file_content), total_tokens, max_tokens
    )

    # If content fits within limit, return as single segment
    if total_tokens <= max_tokens:
        return [
            {
                "content": processed_content,
                "metadata": {
                    "file_name": file_name,
                    "file_type": file_ext.lstrip("."),
                    "segment_index": 0,
                    "total_segments": 1,
                    "is_minimized": minimize_docs,
                },
                "tokens": total_tokens,
            }
        ]

    # Content exceeds limit - segment it
    logger.info("File exceeds token limit, segmenting: %s > %s", total_tokens, max_tokens)

    if file_ext == ".py":
        segments = segment_python_file(processed_content, max_tokens, model)
    elif file_ext in [".yml", ".yaml"]:
        segments = segment_yaml_file(processed_content, max_tokens, model)
    else:
        # For other file types, use simple chunking
        segments = _simple_segment(processed_content, max_tokens, model)

    # Add metadata to each segment
    total_segments = len(segments)
    result = []

    for idx, segment in enumerate(segments):
        result.append(
            {
                "content": segment["content"],
                "metadata": {
                    "file_name": file_name,
                    "file_type": file_ext.lstrip("."),
                    "segment_index": idx,
                    "total_segments": total_segments,
                    "segment_type": segment.get("type", "chunk"),
                    "segment_name": segment.get("name")
                    or segment.get("key", f"part_{idx}"),
                    "is_minimized": minimize_docs,
                },
                "tokens": segment["tokens"],
            }
        )

    return result
