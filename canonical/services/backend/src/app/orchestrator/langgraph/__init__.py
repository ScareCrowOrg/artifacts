"""
LangGraph Orchestrator Module

Provides chat orchestration using LangGraph state machine.

Public API:
    - ChatOrchestrator: Main orchestrator class
    - get_orchestrator: Get global orchestrator instance
    - OrchestratorState: State type definition

Example:
    >>> from app.orchestrator.langgraph import get_orchestrator
    >>> orchestrator = get_orchestrator()
    >>> result = await orchestrator.process(
    ...     mensagem="Crie uma célula para sistema de login",
    ...     responsavel_id="user123"
    ... )
    >>> print(result["resposta"])
"""

from .langgraph_chat_flow import ChatOrchestrator, get_orchestrator
from .langgraph_state import OrchestratorState

__all__ = ["ChatOrchestrator", "get_orchestrator", "OrchestratorState"]
