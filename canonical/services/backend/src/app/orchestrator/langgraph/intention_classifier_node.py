"""
Intention Classifier Node

Classifies user intentions for orchestration routing.
"""

import logging

from ...intention_classifier import IntentionClassifier
from .langgraph_state import OrchestratorState

logger = logging.getLogger(__name__)


def classifica_intencao(
    state: OrchestratorState, classifier: IntentionClassifier
) -> OrchestratorState:
    """
    Node: Classifies the user's intention.

    Uses the IntentionClassifier to determine what the user wants to do.

    Args:
        state: Current orchestrator state
        classifier: Intention classifier instance

    Returns:
        Updated state with classified intention
    """
    mensagem = state["mensagem"]
    historico = state.get("historico", [])

    # Classify intention
    intencao = classifier.classify(mensagem, historico)
    state["intencao"] = intencao.value

    logger.info("ClassificaIntencao: %s", intencao.value)
    logger.info("Explicação: %s", classifier.get_explanation(intencao, mensagem))

    return state
