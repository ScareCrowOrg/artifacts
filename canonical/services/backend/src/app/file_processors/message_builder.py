"""
Message Builder Module

Builds OpenAI message lists with segmented file content while maintaining
conversation context and respecting token limits.

Technical naming: All functions and variables in English.
"""

import logging
from typing import Any, Dict, List

from .token_counter import (
    DEFAULT_MODEL_CONTEXT,
    RESPONSE_BUFFER_TOKENS,
    count_tokens,
    estimate_message_tokens,
)

logger = logging.getLogger(__name__)


def build_segmented_messages(
    base_messages: List[Dict[str, str]],
    file_segments: List[Dict[str, Any]],
    user_message: str,
    max_context_tokens: int = DEFAULT_MODEL_CONTEXT,
    model: str = "gpt-3.5-turbo",
) -> List[List[Dict[str, str]]]:
    """
    Build multiple message lists for segmented file content.

    Creates separate message lists for each file segment, maintaining conversation
    context. Ensures total tokens stay within model limits.

    When file is split into multiple segments, this creates multiple API calls,
    each with the conversation history + a segment of the file.

    Args:
        base_messages: Existing conversation history
        file_segments: File segments from process_file_for_openai
        user_message: User's current message
        max_context_tokens: Maximum context tokens for model
        model: OpenAI model name for token counting

    Returns:
        List of message lists, one per segment or group of segments

    Example:
        >>> history = [{"role": "user", "content": "Hello"}]
        >>> segments = [{"content": "code", "tokens": 100, "metadata": {"segment_index": 0}}]
        >>> message_groups = build_segmented_messages(history, segments, "Analyze this")
        >>> len(message_groups) >= 1
        True
    """
    message_groups = []

    # Calculate tokens already used by conversation history and user message
    base_tokens = estimate_message_tokens(base_messages, model)
    user_msg_tokens = count_tokens(user_message, model)
    reserved_tokens = base_tokens + user_msg_tokens + RESPONSE_BUFFER_TOKENS

    available_tokens = max_context_tokens - reserved_tokens

    if available_tokens < 1000:
        logger.warning(
            f"Very limited tokens available for file content: {available_tokens}. "
            "Consider reducing conversation history."
        )

    # Group segments to fit within available tokens
    current_group = []
    current_group_tokens = 0

    for segment in file_segments:
        segment_tokens = segment["tokens"]

        # Check if adding this segment would exceed limit
        if current_group and current_group_tokens + segment_tokens > available_tokens:
            # Create message list for current group
            messages = _create_message_list_for_segments(
                base_messages, current_group, user_message
            )
            message_groups.append(messages)

            # Start new group
            current_group = [segment]
            current_group_tokens = segment_tokens
        else:
            current_group.append(segment)
            current_group_tokens += segment_tokens

    # Add last group
    if current_group:
        messages = _create_message_list_for_segments(
            base_messages, current_group, user_message
        )
        message_groups.append(messages)

    logger.info("Created %s message groups for API calls", len(message_groups))

    return message_groups


def _create_message_list_for_segments(
    base_messages: List[Dict[str, str]],
    segments: List[Dict[str, Any]],
    user_message: str,
) -> List[Dict[str, str]]:
    """
    Create a message list including conversation history and file segments.

    Formats file segments with clear headers and metadata for context.

    Args:
        base_messages: Conversation history
        segments: File segments to include
        user_message: User's message

    Returns:
        Complete message list for API call
    """
    messages = base_messages.copy()

    # Build segment content string with metadata
    segment_content_parts = []

    for segment in segments:
        metadata = segment["metadata"]
        content = segment["content"]

        # Add segment header with context
        if metadata["total_segments"] > 1:
            header = (
                f"\n--- File: {metadata['file_name']} "
                f"(Part {metadata['segment_index'] + 1}/{metadata['total_segments']}) ---\n"
            )
            if metadata.get("segment_name"):
                header += f"Section: {metadata['segment_name']}\n"
        else:
            header = f"\n--- File: {metadata['file_name']} ---\n"

        segment_content_parts.append(header + content)

    # Combine user message with file content
    full_content = user_message + "\n\n" + "\n".join(segment_content_parts)

    messages.append({"role": "user", "content": full_content})

    return messages


def format_file_reference(
    file_name: str,
    segment_index: int = 0,
    total_segments: int = 1,
    segment_name: str = None,
) -> str:
    """
    Format a file reference header for inclusion in messages.

    Creates a consistent format for referencing files and their segments
    in conversation with the LLM.

    Args:
        file_name: Name of the file
        segment_index: Index of current segment (0-based)
        total_segments: Total number of segments
        segment_name: Optional name of the segment (function/class name)

    Returns:
        Formatted file reference string

    Example:
        >>> format_file_reference("test.py", 0, 1)
        '--- File: test.py ---'
        >>> format_file_reference("test.py", 0, 3, "my_function")
        '--- File: test.py (Part 1/3) ---\\nSection: my_function'
    """
    if total_segments > 1:
        header = (
            f"--- File: {file_name} (Part {segment_index + 1}/{total_segments}) ---"
        )
        if segment_name:
            header += f"\nSection: {segment_name}"
    else:
        header = f"--- File: {file_name} ---"

    return header


def merge_segment_responses(responses: List[str]) -> str:
    """
    Merge multiple LLM responses from different file segments.

    When a file is split and processed in multiple API calls, this combines
    the responses into a coherent final response.

    Args:
        responses: List of response strings from each segment

    Returns:
        Combined response string

    Example:
        >>> responses = ["Part 1 analysis", "Part 2 analysis"]
        >>> merged = merge_segment_responses(responses)
        >>> "Part 1" in merged and "Part 2" in merged
        True
    """
    if not responses:
        return "No responses to merge."

    if len(responses) == 1:
        return responses[0]

    # Combine responses with clear separation
    merged = "Combined analysis from multiple file segments:\n\n"

    for idx, response in enumerate(responses, 1):
        merged += f"=== Segment {idx} ===\n{response}\n\n"

    return merged.strip()
