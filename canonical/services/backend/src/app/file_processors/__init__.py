"""
File Processors Module for OpenAI Integration

This module provides utilities for processing file content before sending to OpenAI API.
Handles token counting, segmentation, documentation minimization, and context management.

Modules:
- token_counter: Token counting utilities using tiktoken
- content_minimizer: Remove comments/docstrings from code files
- file_segmenter: Segment large files into smaller chunks
- message_builder: Build OpenAI message lists with file content

Usage:
    from app.file_processors import process_file_for_openai

    segments = process_file_for_openai(
        file_content=code,
        file_name="example.py",
        max_tokens=8000
    )
"""

from .content_minimizer import (
    remove_python_comments_and_docstrings,
    remove_yaml_comments,
    should_minimize_file,
)
from .file_segmenter import (
    process_file_for_openai,
    segment_python_file,
    segment_yaml_file,
)
from .message_builder import build_segmented_messages
from .token_counter import count_tokens, estimate_message_tokens

__all__ = [
    "count_tokens",
    "estimate_message_tokens",
    "remove_python_comments_and_docstrings",
    "remove_yaml_comments",
    "should_minimize_file",
    "segment_python_file",
    "segment_yaml_file",
    "process_file_for_openai",
    "build_segmented_messages",
]
