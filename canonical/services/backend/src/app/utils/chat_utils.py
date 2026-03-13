"""
Chat History Utility Functions

Stateless utility functions for managing conversation state in dictionaries.
These functions provide manual control over chat history management and
are used by the orchestrator for state-based operations.

Consolidated from legacy chat_history_manager.py module.

Technical naming: All functions and variables in English.
"""

import logging
from typing import Dict, List, Optional, TypedDict

import tiktoken

logger = logging.getLogger(__name__)

# Default configuration constants
DEFAULT_SUMMARY_THRESHOLD_TURNS = 10  # Trigger summary after 10 turns (20 messages)
DEFAULT_SUMMARY_THRESHOLD_TOKENS = (
    3000  # Trigger summary when history exceeds 3000 tokens
)
DEFAULT_MAX_RECENT_HISTORY_TURNS = (
    5  # Keep last 5 turns (10 messages) in recent history
)
DEFAULT_TOKEN_MODEL = "gpt-3.5-turbo"  # Model for token counting


class ChatHistoryState(TypedDict, total=False):
    """
    Type definition for chat history state fields.

    This mirrors the fields added to OrchestratorState for type safety.
    """

    current_chat_summary: Optional[str]
    recent_chat_history: List[Dict[str, str]]
    turns_since_last_summary: int
    summary_threshold_turns: int
    summary_threshold_tokens: int


def count_tokens(
    messages: List[Dict[str, str]], model: str = DEFAULT_TOKEN_MODEL
) -> int:
    """
    Count tokens in a list of messages using tiktoken.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        model: Model name for token encoding (default: gpt-3.5-turbo)

    Returns:
        Total number of tokens in the messages
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("Model %s not found, using cl100k_base encoding", model)
        encoding = tiktoken.get_encoding("cl100k_base")

    total_tokens = 0

    for message in messages:
        # Count tokens for each message
        # Format: role + content + message formatting overhead
        total_tokens += len(encoding.encode(message.get("role", "")))
        total_tokens += len(encoding.encode(message.get("content", "")))
        total_tokens += 4  # Overhead per message (role delimiters, etc.)

    total_tokens += 2  # Overhead for message list

    return total_tokens


def update_history(
    state: Dict,
    user_msg: str,
    agent_response: str,
    max_recent_turns: int = DEFAULT_MAX_RECENT_HISTORY_TURNS,
) -> Dict:
    """
    Update conversation history with a new user-agent exchange.

    This function:
    1. Adds the new exchange to recent_chat_history
    2. Manages the size of recent_chat_history (keeps last N turns)
    3. Increments turns_since_last_summary counter

    Args:
        state: State dict containing chat history fields
        user_msg: User's message
        agent_response: Agent's response
        max_recent_turns: Maximum number of turns to keep in recent history

    Returns:
        Updated state dict

    Note:
        A "turn" consists of one user message and one agent response (2 messages).
    """
    # Initialize fields if not present
    if "recent_chat_history" not in state:
        state["recent_chat_history"] = []
    if "turns_since_last_summary" not in state:
        state["turns_since_last_summary"] = 0

    # Add new exchange to recent history
    state["recent_chat_history"].append({"role": "user", "content": user_msg})
    state["recent_chat_history"].append(
        {"role": "assistant", "content": agent_response}
    )

    # Manage history size - keep only last N turns (2N messages)
    max_messages = max_recent_turns * 2
    if len(state["recent_chat_history"]) > max_messages:
        # Remove oldest messages (FIFO)
        state["recent_chat_history"] = state["recent_chat_history"][-max_messages:]

    # Increment turn counter
    state["turns_since_last_summary"] += 1

    logger.debug(
        "History updated: %s messages, %s turns since last summary",
        len(state['recent_chat_history']), state['turns_since_last_summary']
    )

    return state


def should_summarize(
    state: Dict,
    threshold_turns: int = DEFAULT_SUMMARY_THRESHOLD_TURNS,
    threshold_tokens: int = DEFAULT_SUMMARY_THRESHOLD_TOKENS,
) -> bool:
    """
    Check if conversation should be summarized.

    Summarization is triggered when EITHER condition is met:
    - Turn count exceeds threshold_turns
    - Token count in recent_chat_history exceeds threshold_tokens

    Args:
        state: State dict containing chat history fields
        threshold_turns: Turn threshold for summarization
        threshold_tokens: Token threshold for summarization

    Returns:
        True if summarization should occur, False otherwise
    """
    # Get turn count
    turns = state.get("turns_since_last_summary", 0)

    # Check turn threshold
    if turns >= threshold_turns:
        logger.info("Summarization triggered: turn threshold reached (%s >= %s)", turns, threshold_turns)
        return True

    # Check token threshold
    recent_history = state.get("recent_chat_history", [])
    if recent_history:
        token_count = count_tokens(recent_history)
        if token_count >= threshold_tokens:
            logger.info("Summarization triggered: token threshold reached (%s >= %s)", token_count, threshold_tokens)
            return True

    return False


def build_summarization_prompt(
    current_summary: Optional[str], recent_history: List[Dict[str, str]]
) -> str:
    """
    Build prompt for LLM to generate conversation summary.

    Combines existing summary (if any) with recent history to create
    a consolidated summary.

    Args:
        current_summary: Existing summary (None if first summarization)
        recent_history: Recent conversation history to summarize

    Returns:
        Prompt string for LLM summarization
    """
    prompt_parts = [
        "You are a conversation summarizer. Your task is to create a concise, "
        "factual summary of the conversation that preserves key information.\n\n"
    ]

    if current_summary:
        prompt_parts.append(f"### Previous Summary ###\n{current_summary}\n\n")

    prompt_parts.append("### Recent Conversation ###\n")
    for msg in recent_history:
        role = msg["role"].capitalize()
        content = msg["content"]
        prompt_parts.append(f"{role}: {content}\n")

    prompt_parts.append(
        "\n### Task ###\n"
        "Create a concise summary that:\n"
        "1. Combines the previous summary (if any) with the recent conversation\n"
        "2. Captures key topics, decisions, and action items\n"
        "3. Preserves important technical details\n"
        "4. Is factual and objective (no interpretation)\n"
        "5. Is written in a narrative format\n\n"
        "Summary:"
    )

    return "".join(prompt_parts)


def reset_after_summarization(state: Dict) -> Dict:
    """
    Reset state fields after summarization is complete.

    Clears recent_chat_history and resets turns_since_last_summary counter.
    The current_chat_summary should be updated separately with the new summary.

    Args:
        state: State dict containing chat history fields

    Returns:
        Updated state dict with reset fields
    """
    state["recent_chat_history"] = []
    state["turns_since_last_summary"] = 0

    logger.info("Chat history reset after summarization")

    return state


def initialize_chat_history_state(
    summary_threshold_turns: int = DEFAULT_SUMMARY_THRESHOLD_TURNS,
    summary_threshold_tokens: int = DEFAULT_SUMMARY_THRESHOLD_TOKENS,
) -> ChatHistoryState:
    """
    Initialize chat history state with default values.

    Args:
        summary_threshold_turns: Turn threshold for summarization
        summary_threshold_tokens: Token threshold for summarization

    Returns:
        Initialized ChatHistoryState dict
    """
    return {
        "current_chat_summary": None,
        "recent_chat_history": [],
        "turns_since_last_summary": 0,
        "summary_threshold_turns": summary_threshold_turns,
        "summary_threshold_tokens": summary_threshold_tokens,
    }


def format_context_for_prompt(
    current_summary: Optional[str], recent_history: List[Dict[str, str]]
) -> str:
    """
    Format chat history context for inclusion in LLM prompts.

    Combines summary and recent history into a formatted string that can be
    prepended to the system prompt or included in the conversation context.

    Args:
        current_summary: Current consolidated summary (None if no summary yet)
        recent_history: Recent conversation history

    Returns:
        Formatted context string ready for prompt inclusion
    """
    parts = []

    if current_summary:
        parts.append(f"### Conversation Summary ###\n{current_summary}\n")

    if recent_history:
        parts.append("\n### Recent Exchange ###\n")
        for msg in recent_history:
            role = msg["role"].capitalize()
            content = msg["content"]
            parts.append(f"{role}: {content}\n")

    if parts:
        return "\n".join(parts) + "\n"

    return ""
