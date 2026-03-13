"""
Response Generator Node

Generates final responses based on intention and action results.
"""

import logging

from ...intention_classifier import IntentionType
from ...utils.input_processor import format_context_for_prompt
from .langgraph_state import OrchestratorState

logger = logging.getLogger(__name__)


async def retorna_resposta(state: OrchestratorState) -> OrchestratorState:
    """
    Node: Generates the final response to the user.

    Builds a contextual response based on the intention and action result.
    Includes RAG context if available.

    Args:
        state: Current orchestrator state

    Returns:
        Updated state with final response
    """
    intencao = state.get("intencao", IntentionType.CONVERSAR.value)
    resultado_acao = state.get("resultado_acao")
    mensagem = state["mensagem"]
    rag_context = state.get("rag_context", [])

    logger.info("RetornaResposta: Gerando resposta final")
    logger.info("[RAG] RAG context available: %s documents", len(rag_context) if rag_context else 0)

    # Validate and preprocess RAG context
    if rag_context:
        formatted_context = format_context_for_prompt(rag_context)
        if not formatted_context.strip():
            logger.warning("[RAG] Formatted context is empty after processing.")
            formatted_context = "No relevant context available."
    else:
        formatted_context = "No context provided."

    # Record context_assembled fragment if tracing is enabled
    if state.get("enable_tracing") and state.get("trace_cell_id"):
        await _record_context_assembled_fragment(state, rag_context, formatted_context)

    # Generate response based on intention
    if intencao == IntentionType.CONVERSAR.value:
        resposta = await _gerar_resposta_conversa(state, mensagem, formatted_context)

    elif intencao == IntentionType.CRIAR.value:
        resposta = _gerar_resposta_criar(resultado_acao)

    elif intencao == IntentionType.EXECUTAR.value:
        resposta = _gerar_resposta_executar(resultado_acao)

    elif intencao == IntentionType.REFLETIR.value:
        resposta = _gerar_resposta_reflexao(mensagem)

    elif intencao == IntentionType.DEPURAR.value:
        resposta = _gerar_resposta_depuracao(mensagem)

    else:
        resposta = "Intenção não reconhecida."

    state["resposta"] = resposta

    # Save conversation to memory if enabled
    if state.get("use_memory", False) and state.get("session_id"):
        _save_to_memory(state, mensagem, resposta)

    return state


async def _gerar_resposta_conversa(
    state: OrchestratorState, mensagem: str, formatted_rag_context: str = ""
) -> str:
    """
    Generate an intelligent response for free conversation using LLM with RAG context.

    This function synthesizes a response based on the user message and RAG context
    by calling the appropriate LLM service (Gemini, OpenAI, or Ollama).

    Args:
        state: Current orchestrator state (contains llm_model, historico, etc.)
        mensagem: User's message
        formatted_rag_context: Already formatted RAG context string

    Returns:
        Generated response from LLM
    """
    import time

    llm_model = state.get("target_llm", state.get("modelo", "ollama")).lower()
    historico = state.get("historico", [])

    logger.info("[CONVERSAR] Generating response with %s, RAG context: %s chars", llm_model, len(formatted_rag_context))

    # Build system prompt with RAG context
    system_prompt = (
        "Você é o assistente do ScareVerse, um sistema colaborativo de desenvolvimento de software.\n"
        "Sua função é ajudar os usuários respondendo perguntas de forma concisa e útil.\n"
    )

    if formatted_rag_context:
        system_prompt += (
            "\n### Contexto Relevante ###\n"
            f"{formatted_rag_context}\n"
            "### Fim do Contexto ###\n\n"
            "IMPORTANTE: Use APENAS as informações do contexto acima para responder. "
            "Se a informação não estiver no contexto, diga que não tem essa informação disponível."
        )

    # Record final_llm_call fragment if tracing is enabled
    if state.get("enable_tracing") and state.get("trace_cell_id"):
        await _record_final_llm_call_fragment(state, system_prompt, mensagem, llm_model)

    start_time = time.time()

    try:
        # Call the appropriate LLM service
        if llm_model in ["gemini", "google"]:
            from ...gemini_service import processar_chat_com_gemini

            # For Gemini, we'll add system prompt as first user message
            enriched_historico = historico.copy()
            if system_prompt:
                enriched_historico.insert(0, {"role": "user", "content": system_prompt})
                enriched_historico.insert(
                    1,
                    {
                        "role": "assistant",
                        "content": "Entendido. Vou usar apenas o contexto fornecido para responder.",
                    },
                )

            resposta = await processar_chat_com_gemini(
                intencao=mensagem,
                historico=enriched_historico,
                current_chat_summary=state.get("current_chat_summary"),
                recent_chat_history=state.get("recent_chat_history"),
            )

        elif llm_model in ["openai", "gpt"]:
            from ...openai_service import processar_chat_com_openai

            resposta = await processar_chat_com_openai(
                nova_intencao=mensagem,
                historico=historico,
                system_prompt=system_prompt,
                current_chat_summary=state.get("current_chat_summary"),
                recent_chat_history=state.get("recent_chat_history"),
            )

        elif llm_model in ["ollama", "local"]:
            from ...ollama_service import processar_chat_com_ollama

            # For Ollama, prepend system prompt to the user message
            enriched_message = f"{system_prompt}\n\nUsuário: {mensagem}"

            resposta = await processar_chat_com_ollama(
                intencao=enriched_message,
                historico=historico,
                current_chat_summary=state.get("current_chat_summary"),
                recent_chat_history=state.get("recent_chat_history"),
            )

        else:
            logger.warning("Unknown LLM model: %s, falling back to static response", llm_model)
            resposta = _generate_fallback_response(mensagem, formatted_rag_context)

        response_time_ms = int((time.time() - start_time) * 1000)

        logger.info("[CONVERSAR] Generated response: %s chars", len(resposta))

        # Record llm_response fragment if tracing is enabled
        if state.get("enable_tracing") and state.get("trace_cell_id"):
            await _record_llm_response_fragment(state, resposta, response_time_ms)

        return resposta

    except Exception as e:
        logger.error("[CONVERSAR] Error generating LLM response: %s", e, exc_info=True)
        # Fallback to static response on error
        return _generate_fallback_response(mensagem, formatted_rag_context)


def _generate_fallback_response(_mensagem: str, formatted_context: str = "") -> str:
    """
    Generate a fallback response when LLM is unavailable.

    Args:
        mensagem: User's message
        formatted_context: Already formatted RAG context string

    Returns:
        Static fallback response
    """
    base_response = (
        "Olá! Sou o assistente do ScareVerse. 👋\n\n"
        "Posso ajudá-lo a:\n"
        "- **Criar células** de trabalho para seus projetos\n"
        "- **Executar células** existentes\n"
        "- **Revisar** resultados e sugerir melhorias\n"
        "- **Depurar** problemas e erros\n"
    )

    # Add RAG context information if available
    if formatted_context:
        base_response += (
            f"\n\n📚 **Contexto dos Documentos:**\n"
            f"Contexto disponível:\n\n"
            f"{formatted_context[:500]}...\n\n"  # Show preview
        )

    base_response += "\nO que você gostaria de fazer?"

    return base_response


def _gerar_resposta_criar(resultado_acao: dict) -> str:
    """
    Generate response for cell creation.

    Args:
        resultado_acao: Action result dictionary

    Returns:
        Generated response
    """
    if resultado_acao and resultado_acao.get("success"):
        celula_id = resultado_acao["celula_id"]
        return (
            f"✅ Célula criada com sucesso!\n\n"
            f"**ID da Célula:** `{celula_id}`\n\n"
            f"A célula foi criada com base na sua instrução. "
            f"Você pode executá-la ou fazer modificações conforme necessário."
        )
    else:
        erro = (
            resultado_acao.get("error", "Erro desconhecido")
            if resultado_acao
            else "Erro ao criar célula"
        )
        return f"❌ Não foi possível criar a célula: {erro}"


def _gerar_resposta_executar(resultado_acao: dict) -> str:
    """
    Generate response for cell execution.

    Args:
        resultado_acao: Action result dictionary

    Returns:
        Generated response
    """
    if resultado_acao and resultado_acao.get("success"):
        return resultado_acao.get("message", "Célula executada com sucesso")
    else:
        return (
            "Para executar uma célula, por favor forneça o ID da célula que deseja executar.\n\n"
            "Exemplo: 'Execute a célula abc-123'"
        )


def _gerar_resposta_reflexao(_mensagem: str) -> str:
    """
    Generate a response for reflection/review.

    Args:
        mensagem: User's message

    Returns:
        Generated response
    """
    return (
        "Para revisar resultados, eu preciso saber qual célula ou artefato você quer analisar.\n\n"
        "Você pode:\n"
        "- Me fornecer o ID da célula\n"
        "- Descrever o que foi feito para que eu encontre\n"
        "- Criar uma nova célula para análise"
    )


def _gerar_resposta_depuracao(_mensagem: str) -> str:
    """
    Generate a response for debugging.

    Args:
        mensagem: User's message

    Returns:
        Generated response
    """
    return (
        "Vou ajudá-lo a depurar o problema. 🔍\n\n"
        "Por favor, me forneça:\n"
        "- O ID da célula com erro\n"
        "- A descrição do erro ou comportamento inesperado\n"
        "- Os logs ou mensagens de erro, se houver"
    )


def _save_to_memory(state: OrchestratorState, mensagem: str, resposta: str) -> None:
    """
    Save conversation to memory.

    Args:
        state: Current orchestrator state
        mensagem: User message
        resposta: Agent response
    """
    try:
        from ...utils.conversation_memory import get_session_memory

        session_id = state["session_id"]
        logger.info("Saving conversation to memory for session: %s", session_id)

        memory_manager = get_session_memory(session_id)
        memory_manager.add_exchange(mensagem, resposta)

        logger.info("Conversation saved to memory")

    except Exception as e:
        logger.error("Error saving to conversation memory: %s", e)
        # Continue on error, don't break the response


async def _record_context_assembled_fragment(
    state: OrchestratorState, rag_context: list, formatted_context: str
) -> None:
    """
    Record context_assembled trace fragment.

    Args:
        state: Current orchestrator state
        rag_context: RAG context documents
        formatted_context: Formatted context string
    """
    try:
        from ...services.conversation_trace_service import (
            get_conversation_trace_service,
        )

        trace_service = get_conversation_trace_service()

        await trace_service.record_fragment(
            trace_cell_id=state["trace_cell_id"],
            stage="context_assembled",
            data={
                "rag_context_length": len(rag_context) if rag_context else 0,
                "formatted_context_length": len(formatted_context),
                "history_length": len(state.get("historico", [])),
                "has_attached_files": bool(state.get("attached_files_metadata")),
                "intention": state.get("intencao", "unknown"),
            },
            conversation_id=state["conversation_id"],
        )
        logger.info("[ConversationTrace] Recorded context_assembled fragment")

    except Exception as e:
        logger.error("[ConversationTrace] Error recording context_assembled fragment: %s", e)
        # Don't fail the workflow on tracing errors


async def _record_final_llm_call_fragment(
    state: OrchestratorState, system_prompt: str, user_message: str, llm_model: str
) -> None:
    """
    Record final_llm_call trace fragment.

    Args:
        state: Current orchestrator state
        system_prompt: System prompt with context
        user_message: User message
        llm_model: LLM model being used
    """
    try:
        from ...services.conversation_trace_service import (
            get_conversation_trace_service,
        )

        trace_service = get_conversation_trace_service()

        # Estimate tokens (rough approximation: 1 token ~= 4 chars)
        prompt_length = len(system_prompt) + len(user_message)
        estimated_tokens = prompt_length // 4

        await trace_service.record_fragment(
            trace_cell_id=state["trace_cell_id"],
            stage="final_llm_call",
            data={
                "llm_model": llm_model,
                "system_prompt_length": len(system_prompt),
                "user_message_length": len(user_message),
                "estimated_tokens": estimated_tokens,
                "has_rag_context": "Contexto Relevante" in system_prompt,
            },
            conversation_id=state["conversation_id"],
        )
        logger.info("[ConversationTrace] Recorded final_llm_call fragment for %s", llm_model)

    except Exception as e:
        logger.error("[ConversationTrace] Error recording final_llm_call fragment: %s", e)
        # Don't fail the workflow on tracing errors


async def _record_llm_response_fragment(
    state: OrchestratorState, response_text: str, response_time_ms: int
) -> None:
    """
    Record llm_response trace fragment.

    Args:
        state: Current orchestrator state
        response_text: LLM response text
        response_time_ms: Response time in milliseconds
    """
    try:
        from ...services.conversation_trace_service import (
            get_conversation_trace_service,
        )

        trace_service = get_conversation_trace_service()

        await trace_service.record_fragment(
            trace_cell_id=state["trace_cell_id"],
            stage="llm_response",
            data={
                "response_length": len(response_text),
                "response_time_ms": response_time_ms,
                "response_preview": response_text[:200] if response_text else "",
            },
            conversation_id=state["conversation_id"],
        )
        logger.info("[ConversationTrace] Recorded llm_response fragment (%sms)", response_time_ms)

    except Exception as e:
        logger.error("[ConversationTrace] Error recording llm_response fragment: %s", e)
        # Don't fail the workflow on tracing errors
