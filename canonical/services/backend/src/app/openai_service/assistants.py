"""
OpenAI Assistants API Module

This module handles integration with OpenAI Assistants API,
combining thread-based conversations with RAG context enrichment.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import OPENAI_API_KEY, OPENAI_DEFAULT_MODEL

logger = logging.getLogger(__name__)


async def processar_chat_com_openai_assistants(
    nova_intencao: str,
    thread_id: Optional[str] = None,
    assistant_id: Optional[str] = None,
    _historico: Optional[List[Dict[str, str]]] = None,
    api_key: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model_id: Optional[str] = None,
    attached_files: Optional[List[Dict[str, Any]]] = None,
    use_rag: bool = True,
    selected_collections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Process chat with OpenAI using Assistants API with RAG integration.

    This function combines:
    1. Query-based RAG from ChromaDB (explicit vector store)
    2. OpenAI Assistants API native file management
    3. Thread-based conversation continuity

    The RAG context is enriched into the user's message before being sent
    to the Assistants API, providing dual contextualization.

    Args:
        nova_intencao: User's message/intent
        thread_id: Existing thread ID (optional, creates new if not provided)
        assistant_id: Existing assistant ID (optional, creates new if not provided)
        historico: Conversation history (not used with Assistants API, threads manage history)
        api_key: API Key (optional, falls back to config)
        system_prompt: System instructions for assistant (optional)
        model_id: OpenAI model ID (default: OPENAI_DEFAULT_MODEL)
        attached_files: List of attached files (optional)
                       Format: [{"path": "/path/to/file.py", "type": "text/plain"}]
        use_rag: Whether to use RAG (default: True, can disable for testing)
        selected_collections: Optional list of RAG collections to search
                            (e.g., ['scareverse_docs', 'scareverse_code'])

    Returns:
        Dict with:
            - response: Assistant's response text
            - thread_id: Thread ID (for continuation)
            - assistant_id: Assistant ID (for reuse)

    Raises:
        ValueError: If API key not configured
        RuntimeError: For errors during processing

    Example:
        >>> result = await processar_chat_com_openai_assistants(
        ...     nova_intencao="Explain this code",
        ...     attached_files=[{"path": "/path/main.py", "type": "text/plain"}],
        ...     api_key="sk-...",
        ...     use_rag=True,
        ...     selected_collections=["scareverse_docs"]
        ... )
    """
    from app.services.openai_assistant_service import process_with_assistant

    # Validate API key
    effective_api_key = api_key or OPENAI_API_KEY
    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    model = model_id or OPENAI_DEFAULT_MODEL

    logger.info("Processing chat with OpenAI Assistants API + RAG - Model: %s, Thread: %s, Assistant: %s, Anexos: %s, RAG enabled: %s, Selected collections: %s", model, thread_id or 'new', assistant_id or 'new', len(attached_files) if attached_files else 0, use_rag, selected_collections or 'all')

    # Step 1: Retrieve RAG context (MANDATORY unless explicitly disabled)
    rag_context = ""
    if use_rag:
        try:
            from app.services.rag_service import get_rag_service

            rag = get_rag_service()

            # Get context from vector store (with optional collection filtering)
            _processed_message, context_docs, formatted_context = await rag.get_context(
                user_message=nova_intencao,
                k=5,  # Retrieve top 5 relevant chunks per collection
                selected_collections=selected_collections,
            )

            rag_context = formatted_context

            if rag_context:
                logger.info("RAG context retrieved: %s documents, %s chars", len(context_docs), len(rag_context))
            else:
                logger.info("No RAG context retrieved (vector store may be empty)")

        except FileNotFoundError as e:
            logger.warning("Vector store not found, proceeding without RAG: %s", e)
        except Exception as e:
            logger.error("Error retrieving RAG context, proceeding without RAG: %s", e)

    # Step 2: Enrich the message with RAG context using the centralized builder
    # For Assistants API, we build a simple enriched message (not full messages array)
    enhanced_intencao = nova_intencao
    if rag_context:
        # Use a simplified RAG context injection for Assistants API
        enhanced_intencao = (
            "### Contexto Relevante do Repositório ###\n"
            f"{rag_context}\n"
            "### Fim do Contexto ###\n\n"
            "Use as informações do contexto acima como referência para apoiar sua resposta à pergunta do usuário. "
            "Priorize responder diretamente à pergunta com base no que foi solicitado.\n\n"
            f"Pergunta do usuário: {nova_intencao}"
        )

    try:
        # Convert attached files to Path objects
        file_paths = None
        if attached_files:
            file_paths = [
                Path(f.get("path", "")) for f in attached_files if f.get("path")
            ]

        # Process with assistant (with RAG-enriched message)
        response_text, new_thread_id, new_assistant_id = await process_with_assistant(
            user_message=enhanced_intencao,
            thread_id=thread_id,
            assistant_id=assistant_id,
            file_paths=file_paths,
            system_instructions=system_prompt,
            model=model,
            api_key=effective_api_key,
        )

        logger.info("Assistants API + RAG processing completed successfully")

        return {
            "response": response_text,
            "thread_id": new_thread_id,
            "assistant_id": new_assistant_id,
        }

    except Exception as e:
        logger.error("Erro ao processar chat com OpenAI Assistants API + RAG: %s", e)
        raise RuntimeError(f"Erro ao processar chat: {e}") from e
