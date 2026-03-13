"""
Ollama Integration Service

This module provides integration with a local Ollama instance for generative AI chat.
It handles API calls to Ollama and provides utilities for managing conversational context.

Updated with RAG integration:
- processar_chat_com_ollama_rag: Mandatory RAG-enabled chat (used by chat_router)
- processar_chat_com_ollama: Legacy non-RAG chat (kept for backward compatibility)
- RAG context retrieval prioritizes attached files and vector store search
- Conversation history is maintained with minification for older messages

Updated with explicit chat history usage instructions:
- Clarifies that conversation history is for reference only
- Instructs LLMs to focus responses on the current user question
- Prevents question repetition and confusion about user intent
- Clear section markers separate history from current question
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

# Importa o rate limiter para uso global
from app.utils.rate_limiter import create_embedding_rate_limiter

logger = logging.getLogger(__name__)

# Import configuration from centralized config module
from .config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

# Content truncation length for minified messages (kept for reference)
MINIFIED_CONTENT_MAX_LENGTH = 50

# Health check timeout in seconds
HEALTH_CHECK_TIMEOUT = 5.0


async def verificar_ollama_disponivel() -> bool:
    """
    Verifica se o Ollama está rodando e acessível.

    Returns:
        True se o Ollama está disponível, False caso contrário
    """
    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return response.status_code == 200
    except Exception as e:
        logger.warning("Ollama não está disponível: %s", e)
        return False


_embedding_rate_limiter = create_embedding_rate_limiter()


async def chamar_ollama(
    prompt: str, model: str = OLLAMA_MODEL, stream: bool = False
) -> Dict[str, Any]:
    """
    Chama a API do Ollama para gerar uma resposta.

    Args:
        prompt: O prompt completo para enviar ao modelo
        model: Nome do modelo a usar (default: configurado via env var)
        stream: Se deve usar streaming (default: False)

    Returns:
        Dict com a resposta do Ollama contendo:
        - 'response': texto gerado pelo modelo
        - 'model': nome do modelo usado
        - 'done': se a geração está completa

    Raises:
        httpx.HTTPError: Se houver erro na comunicação com o Ollama
        ValueError: Se a resposta do Ollama for inválida
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {"model": model, "prompt": prompt, "stream": stream}

    logger.info("Chamando Ollama - Modelo: %s, Prompt length: %s chars", model, len(prompt))

    try:
        # Chamada direta sem rate limiter
        return await _chamar_ollama_http_call(url, payload)
    except Exception as e:
        logger.error("Erro inesperado ao chamar Ollama: %s", e)
        raise


# Função auxiliar para chamada HTTP, separada para uso no rate limiter
async def _chamar_ollama_http_call(url, payload):
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("response"):
            logger.warning("Ollama retornou resposta vazia")
            raise ValueError("Resposta vazia do Ollama")
        logger.info("Ollama respondeu com sucesso - Response length: %s chars", len(data.get('response', '')))
        return data


async def processar_chat_com_ollama(
    intencao: str,
    historico: Optional[List[Dict[str, str]]] = None,
    current_chat_summary: Optional[str] = None,
    recent_chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Processa uma intenção do usuário usando Ollama com contexto conversacional.

    Args:
        intencao: Intenção/mensagem atual do usuário
        historico: Histórico da conversa (opcional)
        current_chat_summary: Summary of conversation so far (optional)
        recent_chat_history: Recent chat history from hybrid management (optional)

    Returns:
        String com a resposta gerada pelo Ollama

    Raises:
        ConnectionError: Se o Ollama não estiver disponível
        Exception: Para outros erros durante o processamento
    """
    # Verifica se Ollama está disponível
    if not await verificar_ollama_disponivel():
        raise ConnectionError(
            "Ollama não está disponível. Certifique-se de que o serviço está rodando em "
            f"{OLLAMA_BASE_URL}"
        )

    # Monta o prompt com contexto conversacional usando o builder centralizado
    historico = historico or []

    logger.info(
        "Processing chat with Ollama - Model: %s, Histórico mensagens: %s, Chat summary: %s, Recent history: %s",
        OLLAMA_MODEL, len(historico), bool(current_chat_summary), len(recent_chat_history) if recent_chat_history else 0
    )

    from .services.prompt_builder import PromptBuilder

    builder = PromptBuilder(
        user_message=intencao,
        conversation_history=historico,
        current_chat_summary=current_chat_summary,
        recent_chat_history=recent_chat_history,
    )
    prompt = builder.build_for_ollama()

    # Chama o Ollama
    resultado = await chamar_ollama(prompt)

    return resultado.get("response", "")


async def processar_chat_com_ollama_rag(
    nova_intencao: str,
    historico: Optional[List[Dict[str, str]]] = None,
    _attached_files: Optional[List[Dict[str, Any]]] = None,
    segmented_content: Optional[List[str]] = None,
    rag_context: Optional[str] = None,
    use_rag: bool = True,
    selected_collections: Optional[List[str]] = None,
) -> str:
    """
    Process chat with Ollama using RAG integration and/or segmented file content.

    This function supports multiple contextualization strategies:
    1. Query-based RAG: Retrieves context from persistent vector stores (if rag_context not provided)
    2. Segmented file content: Directly includes file segments in prompt (for attachments)
    3. Combination: Both RAG and segmented content can be used together

    Args:
        nova_intencao: User's message/intent
        historico: Conversation history (optional)
        attached_files: List of attached files (DEPRECATED - use segmented_content instead)
        segmented_content: Pre-segmented file content for direct prompt inclusion
        rag_context: Pre-retrieved RAG context (from orchestrator)
        use_rag: Whether to retrieve RAG context if not provided (default: True)
        selected_collections: Optional list of RAG collections to search
                            (e.g., ['scareverse_docs', 'scareverse_code'])

    Returns:
        String with the response from Ollama

    Raises:
        ConnectionError: If Ollama is not available
        Exception: For other errors during processing

    Example:
        >>> # With orchestrator-provided RAG context
        >>> response = await processar_chat_com_ollama_rag(
        ...     nova_intencao="Explain architecture",
        ...     rag_context="Context from docs..."
        ... )
        >>>
        >>> # With selected collections
        >>> response = await processar_chat_com_ollama_rag(
        ...     nova_intencao="Explain this code",
        ...     selected_collections=["scareverse_code"]
        ... )
    """
    # Verify Ollama is available
    if not await verificar_ollama_disponivel():
        raise ConnectionError(
            "Ollama não está disponível. Certifique-se de que o serviço está rodando em "
            f"{OLLAMA_BASE_URL}"
        )

    historico = historico or []

    # Step 1: Get RAG context if not provided and use_rag is True
    if not rag_context and use_rag:
        try:
            from .services.rag_service import get_rag_service

            rag = get_rag_service()
            logger.debug(
                "[RAG] Chamando CustomEnsembleRetriever com user_message: %s, selected_collections: %s",
                nova_intencao, selected_collections or 'all'
            )
            _chunks, _metadatas, rag_context = await rag.get_context(
                user_message=nova_intencao,
                k=5,  # Retrieve top 5 relevant chunks per collection
                selected_collections=selected_collections,
            )
        except Exception as e:
            logger.warning("Error retrieving RAG context: %s", e)
            rag_context = ""

    # Step 2: Build segmented file context if provided
    if segmented_content:
        logger.info("Including %s file segment(s) in prompt", len(segmented_content))

    # Step 3: Build enhanced prompt using the centralized builder
    from .services.prompt_builder import PromptBuilder

    builder = PromptBuilder(
        user_message=nova_intencao,
        conversation_history=historico,
        rag_context=rag_context,
        attached_content=segmented_content,
    )
    prompt = builder.build_for_ollama()

    logger.debug("[RAG] Prompt final enviado para Ollama:\n%s", prompt)

    # Step 4: Call Ollama
    try:
        resultado = await chamar_ollama(prompt, model=OLLAMA_MODEL)
        logger.debug("[RAG] Resposta Ollama: %s", resultado.get('response', ''))
        return resultado.get("response", "")
    except Exception as e:
        logger.error("Erro ao processar chat com Ollama + RAG: %s", e)
        raise
