"""
Chat Processing Module

This module handles standard chat processing with OpenAI,
including conversation history management and prompt building.
"""

import logging
from typing import Dict, List, Optional

from app.config import OPENAI_API_KEY, OPENAI_DEFAULT_MODEL

from .api_client import chamar_openai

logger = logging.getLogger(__name__)


async def processar_chat_com_openai(
    nova_intencao: str,
    historico: Optional[List[Dict[str, str]]] = None,
    api_key: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model_id: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    anexos_conteudo: Optional[List[str]] = None,
    current_chat_summary: Optional[str] = None,
    recent_chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Processa uma intenção do usuário usando OpenAI com contexto conversacional.

    Args:
        nova_intencao: Intenção/mensagem atual do usuário
        historico: Histórico da conversa (opcional)
        api_key: API Key específica do modelo (prioritária sobre config global)
        system_prompt: Prompt do sistema (opcional)
        model_id: ID do modelo OpenAI (default: OPENAI_DEFAULT_MODEL)
        temperature: Temperatura para geração (0.0 a 2.0)
        max_tokens: Número máximo de tokens na resposta
        base_url: URL base da API (prioritária sobre config global)
        timeout: Timeout em segundos (prioritário sobre config global)
        anexos_conteudo: Lista de conteúdos de anexos (opcional)
        current_chat_summary: Summary of conversation so far (optional)
        recent_chat_history: Recent chat history from hybrid management (optional)

    Returns:
        String com a resposta gerada pela OpenAI

    Raises:
        ValueError: Se a API key não estiver configurada
        RuntimeError: Para outros erros durante o processamento
    """
    # Verifica se há uma API key disponível (modelo específico ou global)
    effective_api_key = api_key if api_key else OPENAI_API_KEY
    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    # Monta o prompt com contexto conversacional usando o builder centralizado
    historico = historico or []

    logger.info("Processando chat com OpenAI - Modelo: %s, Histórico mensagens: %s, Anexos: %s, Chat summary: %s, Recent history: %s", model_id or OPENAI_DEFAULT_MODEL, len(historico), len(anexos_conteudo) if anexos_conteudo else 0, bool(current_chat_summary), len(recent_chat_history) if recent_chat_history else 0)

    from app.services.prompt_builder import PromptBuilder

    builder = PromptBuilder(
        user_message=nova_intencao,
        conversation_history=historico,
        system_instructions=system_prompt,
        current_chat_summary=current_chat_summary,
        recent_chat_history=recent_chat_history,
    )
    messages = builder.build_for_openai(attachments_content=anexos_conteudo)

    # Build payload
    payload = {
        "model": model_id or OPENAI_DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

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
        logger.error("Erro ao processar chat com OpenAI: %s", e)
        raise
