"""
Chat History Management Module

Handles chat history summarization and management to maintain context efficiently.
"""

import asyncio
import logging
from typing import Optional

from .langgraph_state import OrchestratorState

logger = logging.getLogger(__name__)


def manage_chat_history(state: OrchestratorState) -> OrchestratorState:
    """
    Manages chat history and triggers summarization if needed.

    This function:
    1. Updates recent_chat_history with the latest exchange
    2. Checks if summarization threshold is reached
    3. If threshold reached, invokes LLM to generate summary
    4. Updates current_chat_summary and resets counters

    Args:
        state: Current orchestrator state

    Returns:
        Updated state with managed history
    """
    from ...utils.conversation_memory import (
        build_summarization_prompt,
        reset_after_summarization,
        should_summarize,
        update_history,
    )

    mensagem = state["mensagem"]
    resposta_final = state["resposta_final"]

    logger.info("ManageChatHistory: Managing conversation history")

    # Update history with the latest exchange
    state = update_history(
        state=state,
        user_msg=mensagem,
        agent_response=resposta_final,
        max_recent_turns=5,  # Keep last 5 turns in recent history
    )

    # Check if summarization should be triggered
    threshold_turns = state.get("summary_threshold_turns", 10)
    threshold_tokens = state.get("summary_threshold_tokens", 3000)

    if should_summarize(state, threshold_turns, threshold_tokens):
        logger.info("Summarization threshold reached, generating summary...")

        try:
            # Build summarization prompt
            current_summary = state.get("current_chat_summary")
            recent_history = state.get("recent_chat_history", [])

            summary_prompt = build_summarization_prompt(
                current_summary=current_summary, recent_history=recent_history
            )

            # Use Ollama/Mistral for cost-efficient local summarization
            new_summary = _generate_summary(summary_prompt)

            if new_summary:
                # Update state with new summary
                state["current_chat_summary"] = new_summary
                logger.info("Summary generated: %s chars", len(new_summary))

                # Reset history after summarization
                state = reset_after_summarization(state)

        except Exception as e:
            logger.error("Error during summarization: %s", e)
            # Continue without summarization on error

    return state


def _generate_summary(summary_prompt: str) -> Optional[str]:
    """
    Generate summary using local Ollama/Mistral model.

    Uses Ollama for cost-efficient local summarization instead of external APIs.

    Args:
        summary_prompt: Prompt for summarization

    Returns:
        Generated summary or None if failed
    """
    from ...config import OLLAMA_MODEL
    from ...ollama_service import processar_chat_com_ollama

    try:
        # Use Ollama/Mistral for cost-efficient local summarization
        logger.info("Generating summary with Ollama model: %s", OLLAMA_MODEL)
        loop = asyncio.get_event_loop()
        summary = loop.run_until_complete(
            processar_chat_com_ollama(intencao=summary_prompt, historico=[])
        )
        return summary

    except Exception as e:
        logger.error("Error generating summary with Ollama: %s", e)
        return None
