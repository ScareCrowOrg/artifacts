"""
Utility modules for ScareVerse backend.

This package contains utility modules for:
- Document ingestion and RAG (document_ingestion.py)
- Input processing with RAG context (input_processor.py)
- Conversational memory management (conversation_memory.py - LangChain-based)
- Chat history utilities (chat_utils.py - stateless helpers)
"""

# Import only modules without problematic dependencies
# Import chat history utility functions from chat_utils module
from .chat_utils import (
    DEFAULT_MAX_RECENT_HISTORY_TURNS,
    DEFAULT_SUMMARY_THRESHOLD_TOKENS,
    DEFAULT_SUMMARY_THRESHOLD_TURNS,
    DEFAULT_TOKEN_MODEL,
    build_summarization_prompt,
    count_tokens,
    format_context_for_prompt,
    initialize_chat_history_state,
    reset_after_summarization,
    should_summarize,
    update_history,
)

# Import code metadata utilities (no external dependencies)
from .code_metadata import CodeMetadataManager, get_unprocessed_files, mark_as_processed
from .document_ingestion import (
    get_or_create_vectorstore,
    ingest_documents_to_vectorstore,
)
from .input_processor import process_user_input


# Lazy imports for conversation_memory (due to langchain dependency)
def get_session_memory(*args, **kwargs):
    """Lazy import wrapper for get_session_memory."""
    from .conversation_memory import get_session_memory as _get_session_memory

    return _get_session_memory(*args, **kwargs)


def get_session_store():
    """Lazy import wrapper for get_session_store."""
    from .conversation_memory import get_session_store as _get_session_store

    return _get_session_store()


__all__ = [
    "ingest_documents_to_vectorstore",
    "get_or_create_vectorstore",
    "process_user_input",
    "get_session_memory",
    "get_session_store",
    # Chat history utilities (from chat_utils)
    "count_tokens",
    "update_history",
    "should_summarize",
    "build_summarization_prompt",
    "reset_after_summarization",
    "initialize_chat_history_state",
    "format_context_for_prompt",
    "DEFAULT_SUMMARY_THRESHOLD_TURNS",
    "DEFAULT_SUMMARY_THRESHOLD_TOKENS",
    "DEFAULT_MAX_RECENT_HISTORY_TURNS",
    "DEFAULT_TOKEN_MODEL",
    # Code metadata utilities (standalone, no external dependencies)
    "CodeMetadataManager",
    "mark_as_processed",
    "get_unprocessed_files",
]
