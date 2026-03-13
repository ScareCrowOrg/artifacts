"""
Token Counter Module

Provides accurate token counting for OpenAI API using tiktoken library.
Falls back to approximate counting if tiktoken is not available.

Technical naming: All functions and variables in English.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# OpenAI API token limits (conservative estimates)
DEFAULT_MAX_TOKENS = 8000  # Conservative limit for message content
DEFAULT_MODEL_CONTEXT = 16000  # Default context window
RESPONSE_BUFFER_TOKENS = 2000  # Reserve for response generation


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Count the number of tokens in a text string for a given model.

    Uses tiktoken library for accurate token counting based on OpenAI's tokenization.
    Falls back to approximate counting (chars/4) if tiktoken is not available.

    Args:
        text: Text content to count tokens for
        model: OpenAI model name (default: gpt-3.5-turbo)

    Returns:
        Number of tokens in the text

    Example:
        >>> count_tokens("Hello, world!")
        4
        >>> count_tokens("def hello(): pass", "gpt-4")
        6
    """
    try:
        import tiktoken

        # Get encoding for the model
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base encoding (used by gpt-4, gpt-3.5-turbo)
            logger.warning("Model %s not found, using cl100k_base encoding", model)
            encoding = tiktoken.get_encoding("cl100k_base")

        tokens = encoding.encode(text)
        return len(tokens)

    except (ImportError, Exception) as e:
        # Fallback to approximate counting if tiktoken not available or network error
        if isinstance(e, ImportError):
            logger.warning(
                "tiktoken not available, using approximate token counting (chars/4)"
            )
        else:
            logger.warning("tiktoken error (%s): using approximate token counting (chars/4)", type(e).__name__)
        return len(text) // 4


def estimate_message_tokens(
    messages: List[Dict[str, str]], model: str = "gpt-3.5-turbo"
) -> int:
    """
    Estimate total tokens used by a list of messages.

    Includes overhead for message formatting (role, structure).
    Based on OpenAI's token counting methodology.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: OpenAI model name

    Returns:
        Estimated total tokens including message overhead

    Example:
        >>> messages = [
        ...     {"role": "user", "content": "Hello"},
        ...     {"role": "assistant", "content": "Hi there!"}
        ... ]
        >>> estimate_message_tokens(messages)
        25
    """
    total = 0

    # Add tokens for each message
    for message in messages:
        # Message overhead: ~4 tokens per message (role, delimiters)
        total += 4

        # Count content tokens
        content = message.get("content", "")
        total += count_tokens(content, model)

        # Count role tokens
        role = message.get("role", "")
        total += count_tokens(role, model)

    # Add overhead for message structure (~3 tokens)
    total += 3

    return total


def check_token_limit(
    text: str, max_tokens: int = DEFAULT_MAX_TOKENS, model: str = "gpt-3.5-turbo"
) -> bool:
    """
    Check if text is within token limit.

    Args:
        text: Text to check
        max_tokens: Maximum allowed tokens
        model: OpenAI model name

    Returns:
        True if within limit, False otherwise

    Example:
        >>> check_token_limit("short text", max_tokens=1000)
        True
    """
    tokens = count_tokens(text, model)
    return tokens <= max_tokens


def get_available_tokens(
    conversation_messages: List[Dict[str, str]],
    max_context: int = DEFAULT_MODEL_CONTEXT,
    model: str = "gpt-3.5-turbo",
) -> int:
    """
    Calculate available tokens for file content given conversation history.

    Args:
        conversation_messages: Existing conversation messages
        max_context: Maximum context window for model
        model: OpenAI model name

    Returns:
        Number of tokens available for file content

    Example:
        >>> messages = [{"role": "user", "content": "Hello"}]
        >>> tokens = get_available_tokens(messages, max_context=16000)
        >>> tokens > 0
        True
    """
    used_tokens = estimate_message_tokens(conversation_messages, model)
    available = max_context - used_tokens - RESPONSE_BUFFER_TOKENS

    return max(0, available)  # Ensure non-negative
