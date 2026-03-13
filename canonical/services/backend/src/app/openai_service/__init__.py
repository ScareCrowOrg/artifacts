"""
OpenAI API Integration Service

This module provides integration with OpenAI's API for generative AI chat.
It is organized into specialized submodules:

- api_client.py: Core API calls and availability checks
- chat_processor.py: Standard chat processing with conversation history
- function_calling.py: Function calling (tool execution loop)
- rag_integration.py: RAG-enhanced chat with vector store context
- assistants.py: OpenAI Assistants API with RAG integration

Public API:
    Core API:
        chamar_openai: Call OpenAI API with payload
        verificar_openai_disponivel: Check if OpenAI API is available

    Chat Processing:
        processar_chat_com_openai: Process chat with conversation history
        processar_com_function_calling: Process chat with function calling
        processar_chat_com_openai_rag: Process chat with RAG integration
        processar_chat_com_openai_assistants: Process chat with Assistants API + RAG
"""

from .api_client import (
    TOOL_RESULT_MAX_LOG_LENGTH,
    chamar_openai,
    verificar_openai_disponivel,
)
from .assistants import processar_chat_com_openai_assistants
from .chat_processor import processar_chat_com_openai
from .function_calling import processar_com_function_calling
from .rag_integration import processar_chat_com_openai_rag

__all__ = [
    # Core API
    "chamar_openai",
    "verificar_openai_disponivel",
    "TOOL_RESULT_MAX_LOG_LENGTH",
    # Chat processing
    "processar_chat_com_openai",
    "processar_com_function_calling",
    "processar_chat_com_openai_rag",
    "processar_chat_com_openai_assistants",
]
