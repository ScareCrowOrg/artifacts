"""
Action Executor Node

Executes actions based on classified intentions.
"""

import logging
from typing import Any, Dict

from ...intention_classifier import IntentionType
from ...langchain_tools import CellTools
from .langgraph_state import OrchestratorState

logger = logging.getLogger(__name__)


def executa_acao(state: OrchestratorState) -> OrchestratorState:
    """
    Node: Executes action based on intention.

    Calls LangChain tools to create or execute cells if needed.

    Args:
        state: Current orchestrator state

    Returns:
        Updated state with action results
    """
    intencao = state.get("intencao", IntentionType.CONVERSAR.value)
    mensagem = state["mensagem"]
    responsavel_id = state["responsavel_id"]

    logger.info("ExecutaAcao: Processando intenção %s", intencao)

    resultado = None
    celula_criada = None

    if intencao == IntentionType.CRIAR.value:
        resultado, celula_criada = _executar_criacao_celula(responsavel_id, mensagem)

    elif intencao == IntentionType.EXECUTAR.value:
        resultado = _executar_celula(mensagem)

    state["acao_realizada"] = resultado is not None
    state["resultado_acao"] = resultado
    state["celula_criada"] = celula_criada

    return state


def _executar_criacao_celula(responsavel_id: str, mensagem: str) -> tuple:
    """
    Execute cell creation action.

    Args:
        responsavel_id: ID of the user responsible
        mensagem: User's message with cell instructions

    Returns:
        Tuple of (result dictionary, cell created dictionary)
    """
    logger.info("Criando célula...")

    resultado = CellTools.criar_celula_impl(
        responsavel_id=responsavel_id,
        tipo_celula_id=None,  # Use first available type
        dados_iniciais={"instrucao": mensagem},
    )

    celula_criada = None
    if resultado.get("success"):
        celula_criada = {
            "id": resultado["celula_id"],
            "tipo": resultado["tipo_celula_id"],
            "estado": resultado["estado"],
        }

    return resultado, celula_criada


def _executar_celula(_mensagem: str) -> Dict[str, Any]:
    """
    Execute cell execution action.

    Args:
        mensagem: User's message (may contain cell ID)

    Returns:
        Result dictionary

    Note:
        TODO: Implement sophisticated cell ID extraction using regex or LLM
    """
    logger.info("Execução de célula solicitada")

    # For now, we just note that execution was requested
    # Future enhancement: Use regex or LLM to extract cell ID from natural language
    return {
        "success": True,
        "message": "Para executar uma célula, por favor forneça o ID da célula.",
    }
