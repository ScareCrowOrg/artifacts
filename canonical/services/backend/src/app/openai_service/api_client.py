"""
OpenAI API Client Module

This module provides the core API client for calling OpenAI's API.
It handles HTTP requests, authentication, and error handling.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from app.config import (
    OPENAI_API_KEY,
    OPENAI_API_URL,
    OPENAI_DEFAULT_MODEL,
    OPENAI_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Constants for function calling
TOOL_RESULT_MAX_LOG_LENGTH = 200  # Maximum length of tool result to log


async def chamar_openai(
    payload: Dict[str, Any],
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Chama a API da OpenAI para gerar uma resposta.

    Args:
        payload: Payload da requisição (model, messages, temperature, tools, etc.)
        api_key: API Key específica (prioritária sobre config global)
        base_url: URL base da API (prioritária sobre config global)
        timeout: Timeout em segundos (prioritário sobre config global)

    Returns:
        Dict com a resposta da OpenAI

    Raises:
        ValueError: Se a API key não estiver configurada
        RuntimeError: Se houver erro na comunicação com a OpenAI

    Note:
        Supports OpenAI Function Calling via 'tools' and 'tool_choice' in payload.
        Messages can include 'tool' role for tool responses.
    """
    # Use model-specific API key if provided, otherwise fall back to global config
    api_key_to_use = api_key if api_key else OPENAI_API_KEY

    if not api_key_to_use:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    url = f"{base_url or OPENAI_API_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key_to_use}",
    }

    logger.info("Chamando OpenAI - Modelo: %s, Messages: %s", payload.get('model'), len(payload.get('messages', [])))

    try:
        async with httpx.AsyncClient(timeout=timeout or OPENAI_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
            return response.json()

    except httpx.HTTPStatusError as e:
        logger.error("Erro HTTP da OpenAI: %s - %s", e.response.status_code, e.response.text)
        raise RuntimeError(f"Erro na API da OpenAI: {e.response.status_code}") from e
    except httpx.TimeoutException as e:
        logger.error("Timeout ao chamar OpenAI após %ss", timeout or OPENAI_TIMEOUT)
        raise RuntimeError(f"Timeout ao processar OpenAI: {e}") from e
    except httpx.RequestError as e:
        logger.error("Erro de requisição para OpenAI: %s", e)
        raise RuntimeError(f"Falha ao conectar à API da OpenAI: {e}") from e
    except Exception as e:
        logger.error("Erro inesperado ao chamar OpenAI: %s", e)
        raise RuntimeError(f"Erro inesperado ao processar OpenAI: {e}") from e


async def verificar_openai_disponivel(
    api_key: Optional[str] = None, base_url: Optional[str] = None
) -> bool:
    """
    Verifica se a OpenAI API está configurada e acessível.

    Args:
        api_key: API Key específica (prioritária sobre config global)
        base_url: URL base da API (prioritária sobre config global)

    Returns:
        True se a OpenAI está disponível, False caso contrário
    """
    api_key_to_use = api_key if api_key else OPENAI_API_KEY

    if not api_key_to_use:
        logger.warning("OPENAI_API_KEY não configurada para verificação.")
        return False

    # Try a minimal API call to verify the key
    try:
        payload = {
            "model": OPENAI_DEFAULT_MODEL,
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 10,
        }
        await chamar_openai(payload, api_key_to_use, base_url, timeout=10.0)
        return True
    except Exception as e:
        logger.error("Verificação de disponibilidade da OpenAI falhou: %s", e)
        return False
