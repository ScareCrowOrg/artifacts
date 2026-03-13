"""
OpenAI Assistants API Integration Service (Backward Compatibility Shim)

This module maintains backward compatibility with code that imports from
openai_assistant_service.py. The actual implementation has been modularized
into the openai_assistant/ subdirectory.

For new code, import directly from the module:
    from app.services.openai_assistant import process_with_assistant

This file is a shim that re-exports all functions from the modularized structure.

Technical naming: All functions and variables in English.
Compliance: Adheres to RULESET.md Rule 1.1 (File Size < 500 lines),
            Rule 4.3 (Technical Naming Convention)
"""

# Re-export all public API from the modularized openai_assistant module
from .openai_assistant import (
    DEFAULT_MAX_POLL_TIME,
    DEFAULT_POLL_INTERVAL,
    add_message_to_thread,
    create_or_get_assistant,
    create_thread,
    get_run_messages,
    get_thread,
    process_with_assistant,
    run_assistant,
)

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
