"""
OpenAI Assistant Module - Integration with OpenAI's Assistants API

This module provides integration with OpenAI's Assistants API for holistic
conversation management with file contextualization.

Public API (backward compatible):
- create_or_get_assistant: Create or retrieve an assistant
- create_thread: Create a new conversation thread
- get_thread: Retrieve an existing thread
- add_message_to_thread: Add a message with optional file attachments
- run_assistant: Execute a run and wait for completion
- get_run_messages: Retrieve messages from a completed run
- process_with_assistant: High-level function for complete conversation flow

All exports maintain backward compatibility with the original openai_assistant_service.py.

Technical naming: All functions and variables in English.
Compliance: Adheres to RULESET.md Rule 1.1 (File Size < 500 lines),
            Rule 4.3 (Technical Naming Convention)
"""

from .assistant_manager import create_or_get_assistant
from .message_manager import add_message_to_thread, get_run_messages
from .orchestrator import process_with_assistant
from .run_manager import DEFAULT_MAX_POLL_TIME, DEFAULT_POLL_INTERVAL, run_assistant
from .thread_manager import create_thread, get_thread

__all__ = [
    "create_or_get_assistant",
    "create_thread",
    "get_thread",
    "add_message_to_thread",
    "run_assistant",
    "get_run_messages",
    "process_with_assistant",
    "DEFAULT_POLL_INTERVAL",
    "DEFAULT_MAX_POLL_TIME",
]
