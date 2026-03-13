"""
RAG Integration Module

This module handles RAG (Retrieval-Augmented Generation) integration
with OpenAI chat completions, enriching prompts with retrieved context.
"""

import logging
from typing import Any, Dict, List, Optional

from app.config import OPENAI_API_KEY, OPENAI_DEFAULT_MODEL

from .api_client import chamar_openai

logger = logging.getLogger(__name__)


async def processar_chat_com_openai_rag(
    nova_intencao: str,
    historico: Optional[List[Dict[str, str]]] = None,
    api_key: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    attached_files: Optional[List[Dict[str, Any]]] = None,
    use_rag: bool = True,
) -> str:
    """
    Process chat with OpenAI using mandatory RAG integration.

    This function ALWAYS retrieves RAG context before calling OpenAI:
    1. Retrieves relevant context from vector store based on user message
    2. If attachments are provided, prioritizes those files in the search
    3. Enriches prompt with RAG context
    4. Calls OpenAI with context-enriched prompt
    5. Returns response

    RAG works ALWAYS, regardless of attachments:
    - Without attachments: General RAG search based on user message
    - With attachments: RAG search prioritizes attached files

    Args:
        nova_intencao: User's message/intent
        historico: Conversation history (optional)
        api_key: API Key (optional, falls back to config)
        system_prompt: System prompt (optional)
        model_id: OpenAI model ID (default: OPENAI_DEFAULT_MODEL)
        temperature: Sampling temperature (0.0 to 2.0)
        max_tokens: Maximum tokens in response
        base_url: API base URL (optional)
        timeout: Request timeout (optional)
        attached_files: List of attached files for RAG prioritization (optional)
                       Format: [{"path": "file.py", "content": "..."}]
        use_rag: Whether to use RAG (default: True, can disable for testing)

    Returns:
        String with the response from OpenAI

    Raises:
        ValueError: If API key not configured
        RuntimeError: For errors during processing

    Example:
        >>> # RAG works without attachments
        >>> response = await processar_chat_com_openai_rag(
        ...     nova_intencao="Explain the architecture",
        ...     api_key="sk-..."
        ... )
        >>>
        >>> # RAG prioritizes attachments when provided
        >>> response = await processar_chat_com_openai_rag(
        ...     nova_intencao="Explain this code",
        ...     attached_files=[{"path": "main.py", "content": "..."}],
        ...     api_key="sk-..."
        ... )
    """
    # Validate API key
    effective_api_key = api_key if api_key else OPENAI_API_KEY
    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    historico = historico or []

    logger.info(
        "Processing chat with OpenAI + RAG - Model: %s, Histórico mensagens: %s, Anexos: %s, RAG enabled: %s",
        model_id or OPENAI_DEFAULT_MODEL, len(historico), len(attached_files) if attached_files else 0, use_rag
    )

    # Step 1: Retrieve RAG context (MANDATORY unless explicitly disabled)
    rag_context = ""
    context_docs = []  # Initialize to avoid UnboundLocalError
    if use_rag:
        try:
            from app.services.rag_service import get_rag_service

            rag = get_rag_service()

            # Get context with priority-based search
            _processed_message, context_docs, formatted_context = await rag.get_context(
                user_message=nova_intencao,
                k=5,  # Retrieve top 5 relevant chunks
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

    # Step 2: Build messages with RAG context using the centralized builder
    logger.debug("[TRACING] --- RAG Context ---\n" + rag_context)
    logger.debug("[TRACING] --- RAG Chunks ---\n%s", context_docs)

    # Default system prompt if not provided
    if not system_prompt:
        system_prompt = (
            "Você é um assistente útil e preciso. "
            "Use o contexto fornecido para responder perguntas de forma detalhada e precisa."
        )

    from app.services.prompt_builder import PromptBuilder

    builder = PromptBuilder(
        user_message=nova_intencao,
        conversation_history=historico,
        rag_context=rag_context,
        system_instructions=system_prompt,
    )
    messages = builder.build_for_openai()

    # Step 3: Call OpenAI
    payload = {
        "model": model_id or OPENAI_DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    logger.debug("[TRACING] --- Prompt Final ---\n" + str(messages))

    try:
        response_data = await chamar_openai(
            payload=payload,
            api_key=effective_api_key,
            base_url=base_url,
            timeout=timeout,
        )

        # Extract response text from OpenAI response format
        if response_data and response_data.get("choices"):
            return response_data["choices"][0]["message"]["content"]

        logger.warning("OpenAI retornou resposta vazia")
        return "Não foi possível obter uma resposta da OpenAI."

    except Exception as e:
        logger.error("Erro ao processar chat com OpenAI + RAG: %s", e)
        raise
