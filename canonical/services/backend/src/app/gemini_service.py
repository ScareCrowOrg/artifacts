"""
Gemini API Integration Service

This module provides integration with Google's Gemini API for generative AI chat.
It handles API calls to Gemini and provides utilities for managing conversational context.

Updated with explicit chat history usage instructions:
- Clarifies that conversation history is for reference only
- Instructs LLMs to focus responses on the current user question
- Prevents question repetition and confusion about user intent
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Import configuration from centralized config module
from .config import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_DEFAULT_MODEL, GEMINI_TIMEOUT


async def upload_arquivo_gemini(
    file_content: str,
    file_name: str,
    mime_type: str = "text/plain",
    api_key: Optional[str] = None,
) -> str:
    """
    Upload a file to Gemini Files API.

    Args:
        file_content: Content of the file as string
        file_name: Name of the file
        mime_type: MIME type of the file (default: text/plain)
        api_key: API Key específica (prioritária sobre config global)

    Returns:
        str: File URI from Gemini response (e.g., 'https://generativelanguage.googleapis.com/v1beta/files/abc123')

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with Gemini Files API

    Example:
        >>> file_uri = await upload_arquivo_gemini(
        ...     file_content="def hello(): print('Hello')",
        ...     file_name="script.py",
        ...     mime_type="text/x-python"
        ... )
    """
    effective_api_key = api_key or GEMINI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "Gemini API Key não configurada. Configure GEMINI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    # Gemini Files API upload endpoint
    upload_url = "https://generativelanguage.googleapis.com/upload/v1beta/files"

    # Prepare multipart form data
    files = {"file": (file_name, file_content.encode("utf-8"), mime_type)}

    headers = {"X-Goog-Api-Key": effective_api_key}

    logger.info("Enviando arquivo '%s' para Gemini Files API", file_name)

    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
            response = await client.post(upload_url, files=files, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Extract file URI from response
            if "file" not in data or "uri" not in data["file"]:
                logger.error("Resposta inválida do Files API: %s", data)
                raise ValueError("Resposta inválida do Gemini Files API")

            file_uri = data["file"]["uri"]
            logger.info("Arquivo '%s' enviado com sucesso: %s", file_name, file_uri)

            return file_uri

    except httpx.TimeoutException:
        logger.error("Timeout ao enviar arquivo para Gemini Files API após %ss", GEMINI_TIMEOUT)
        raise
    except httpx.HTTPError as e:
        logger.error("Erro HTTP ao enviar arquivo para Gemini Files API: %s", e)
        raise
    except Exception as e:
        logger.error("Erro inesperado ao enviar arquivo para Gemini Files API: %s", e)
        raise


async def delete_file_from_gemini_api(
    file_uri: str, api_key: Optional[str] = None
) -> bool:
    """
    Delete a file from Gemini Files API.

    Note: Gemini Files API may not support deletion in all versions.
    This function attempts deletion but returns False if not supported.

    Args:
        file_uri: File URI to delete (e.g., 'https://.../.../files/abc123')
        api_key: API Key específica (prioritária sobre config global)

    Returns:
        True if deletion was successful, False otherwise

    Example:
        >>> success = await delete_file_from_gemini_api(
        ...     "https://generativelanguage.googleapis.com/v1beta/files/abc123"
        ... )
    """
    effective_api_key = api_key or GEMINI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "Gemini API Key não configurada. Configure GEMINI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Attempting to delete file from Gemini Files API: %s", file_uri)

    try:
        # Extract file ID from URI if needed
        # URI format: https://generativelanguage.googleapis.com/v1beta/files/{fileId}
        if "/" in file_uri:
            file_id = file_uri.split("/")[-1]
        else:
            file_id = file_uri

        delete_url = f"https://generativelanguage.googleapis.com/v1beta/files/{file_id}"

        headers = {"X-Goog-Api-Key": effective_api_key}

        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
            response = await client.delete(delete_url, headers=headers)

            # Gemini may return 404 if deletion is not supported or file doesn't exist
            if response.status_code == 404:
                logger.warning("File not found or deletion not supported: %s", file_uri)
                return False

            response.raise_for_status()
            logger.info("File deleted successfully: %s", file_uri)
            return True

    except httpx.HTTPError as e:
        logger.warning("HTTP error deleting file from Gemini Files API: %s", e)
        return False
    except Exception as e:
        logger.warning("Error deleting file from Gemini Files API: %s", e)
        return False


async def verificar_gemini_disponivel() -> bool:
    """
    Verifica se o Gemini API está configurado e acessível.

    Returns:
        True se o Gemini está disponível, False caso contrário
    """
    if not GEMINI_API_KEY:
        logger.warning("Gemini API Key não configurada")
        return False

    try:
        # Test API connectivity with a simple request
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Use models list endpoint to verify API key
            url = f"{GEMINI_API_URL}/models"
            params = {"key": GEMINI_API_KEY}
            response = await client.get(url, params=params)
            return response.status_code == 200
    except Exception as e:
        logger.warning("Gemini não está disponível: %s", e)
        return False


async def chamar_gemini(
    prompt: List[Dict[str, Any]], model: str = None, api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Chama a API do Gemini para gerar uma resposta.

    Args:
        prompt: Lista de mensagens formatadas para Gemini
        model: Nome do modelo a usar (default: GEMINI_DEFAULT_MODEL)
        api_key: API Key específica do modelo (prioritária sobre config global)

    Returns:
        Dict com a resposta do Gemini contendo:
        - 'response': texto gerado pelo modelo
        - 'model': nome do modelo usado

    Raises:
        httpx.HTTPError: Se houver erro na comunicação com o Gemini
        ValueError: Se a resposta do Gemini for inválida ou API key não configurada
    """
    # Use model-specific API key if provided, otherwise fall back to global config
    effective_api_key = api_key or GEMINI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "Gemini API Key não configurada. Configure GEMINI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    # Use default model if not specified
    if not model:
        model = GEMINI_DEFAULT_MODEL

    url = f"{GEMINI_API_URL}/models/{model}:generateContent"

    payload = {
        "contents": prompt,
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 4096,
        },
    }

    headers = {"x-goog-api-key": effective_api_key, "Content-Type": "application/json"}

    logger.info("Chamando Gemini - Modelo: %s, Messages: %s", model, len(prompt))

    try:
        async with httpx.AsyncClient(timeout=GEMINI_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Extract text from Gemini response format
            if not data.get("candidates"):
                logger.warning("Gemini retornou resposta vazia")
                raise ValueError("Resposta vazia do Gemini")

            candidate = data["candidates"][0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            if not parts:
                logger.warning("Gemini retornou sem parts")
                raise ValueError("Resposta sem conteúdo do Gemini")

            response_text = "".join([part.get("text", "") for part in parts])

            logger.info("Gemini respondeu com sucesso - Response length: %s chars", len(response_text))

            return {"response": response_text, "model": model}

    except httpx.TimeoutException:
        logger.error("Timeout ao chamar Gemini após %ss", GEMINI_TIMEOUT)
        raise
    except httpx.HTTPError as e:
        logger.error("Erro HTTP ao chamar Gemini: %s", e)
        raise
    except Exception as e:
        logger.error("Erro inesperado ao chamar Gemini: %s", e)
        raise


async def processar_chat_com_gemini(
    intencao: str,
    historico: Optional[List[Dict[str, str]]] = None,
    api_key: Optional[str] = None,
    file_uris: Optional[List[str]] = None,
    current_chat_summary: Optional[str] = None,
    recent_chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Processa uma intenção do usuário usando Gemini com contexto conversacional.

    Args:
        intencao: Intenção/mensagem atual do usuário
        historico: Histórico da conversa (opcional)
        api_key: API Key específica do modelo (prioritária sobre config global)
        file_uris: Lista opcional de URIs de arquivos do Gemini Files API
        current_chat_summary: Summary of conversation so far (optional)
        recent_chat_history: Recent chat history from hybrid management (optional)

    Returns:
        String com a resposta gerada pelo Gemini

    Raises:
        ConnectionError: Se o Gemini não estiver disponível
        Exception: Para outros erros durante o processamento
    """
    # Verifica se há uma API key disponível (modelo específico ou global)
    effective_api_key = api_key or GEMINI_API_KEY
    if not effective_api_key:
        raise ConnectionError(
            "Gemini API Key não configurada. Configure GEMINI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    # Monta o prompt com contexto conversacional usando o builder centralizado
    historico = historico or []

    logger.info("Processando chat com Gemini - Intenção: %s, Histórico mensagens: %s, Files: %s, Chat summary: %s, Recent history: %s", intencao, len(historico), len(file_uris) if file_uris else 0, bool(current_chat_summary), len(recent_chat_history) if recent_chat_history else 0)

    from .services.prompt_builder import PromptBuilder

    builder = PromptBuilder(
        user_message=intencao,
        conversation_history=historico,
        current_chat_summary=current_chat_summary,
        recent_chat_history=recent_chat_history,
    )
    prompt = builder.build_for_gemini(file_uris=file_uris)

    # Chama o Gemini com a API key específica
    resultado = await chamar_gemini(prompt, api_key=effective_api_key)

    return resultado.get("response", "")


async def processar_chat_com_gemini_rag(
    nova_intencao: str,
    historico: Optional[List[Dict[str, str]]] = None,
    api_key: Optional[str] = None,
    file_uris: Optional[List[str]] = None,
    use_rag: bool = True,
    current_chat_summary: Optional[str] = None,
    recent_chat_history: Optional[List[Dict[str, str]]] = None,
    selected_collections: Optional[List[str]] = None,
) -> str:
    """
    Process chat with Gemini using mandatory RAG integration.

    This function combines:
    1. Query-based RAG: Retrieves relevant context from vector store
    2. File attachments via Gemini Files API (file_uris)
    3. Conversation history

    RAG context is enriched into the user's message before being sent to Gemini.

    Args:
        nova_intencao: User's message/intent
        historico: Conversation history (optional)
        api_key: API Key (optional, falls back to config)
        file_uris: List of file URIs from Gemini Files API (optional)
        use_rag: Whether to use RAG (default: True, can disable for testing)
        current_chat_summary: Summary of conversation so far (optional)
        recent_chat_history: Recent chat history from hybrid management (optional)
        selected_collections: Optional list of RAG collections to search
                            (e.g., ['scareverse_docs', 'scareverse_code'])

    Returns:
        String with the response from Gemini

    Raises:
        ValueError: If API key not configured
        ConnectionError: If Gemini API is not available

    Example:
        >>> response = await processar_chat_com_gemini_rag(
        ...     nova_intencao="Explain the architecture",
        ...     api_key="...",
        ...     selected_collections=["scareverse_docs"]
        ... )
    """
    # Validate API key
    effective_api_key = api_key or GEMINI_API_KEY
    if not effective_api_key:
        raise ValueError(
            "Gemini API Key não configurada. Configure GEMINI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    historico = historico or []

    logger.info("Processing chat with Gemini + RAG - Histórico mensagens: %s, Files: %s, RAG enabled: %s, Selected collections: %s", len(historico), len(file_uris) if file_uris else 0, use_rag, selected_collections or 'all')

    # Step 1: Retrieve RAG context (MANDATORY unless explicitly disabled)
    rag_context = ""
    if use_rag:
        try:
            from .services.rag_service import get_rag_service

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
    from .services.prompt_builder import PromptBuilder

    builder = PromptBuilder(
        user_message=nova_intencao,
        conversation_history=historico,
        rag_context=rag_context,
        current_chat_summary=current_chat_summary,
        recent_chat_history=recent_chat_history,
    )
    prompt = builder.build_for_gemini(file_uris=file_uris)

    # Call Gemini
    resultado = await chamar_gemini(prompt, api_key=effective_api_key)

    return resultado.get("response", "")
