"""
Orchestrator State Definitions

This module defines the state structure used by the LangGraph orchestrator.

Technical naming: All fields in English.
"""

from typing import Any, Dict, List, Optional, TypedDict


class OrchestratorState(TypedDict):
    """
    State for the orchestrator graph.

    This state is passed between nodes in the LangGraph workflow and tracks
    all necessary information for processing a chat interaction.
    """

    # Core message data
    mensagem: str  # User's message
    historico: List[Dict[str, str]]  # Conversation history
    intencao: Optional[str]  # Classified intention
    responsavel_id: str  # User/agent responsible for the interaction
    modelo: str  # LLM model to use

    # Action tracking
    acao_realizada: bool  # Whether an action was performed
    resultado_acao: Optional[Dict[str, Any]]  # Result of action execution
    resposta_final: str  # Final response to return
    celula_criada: Optional[Dict[str, Any]]  # Created cell (if any)

    # Document and file handling
    document_paths: Optional[List[str]]  # Paths to documents referenced by user
    enable_function_calling: bool  # Whether to use function calling for document access
    attached_files: Optional[
        List[Dict[str, Any]]
    ]  # Files attached from UI (temp storage)
    attached_files_metadata: Optional[
        List[Dict[str, Any]]
    ]  # Processed attachment metadata

    # RAG and contextualization
    rag_context: Optional[List[Any]]  # RAG context documents
    use_rag: bool  # Whether to use RAG for this request

    # Session management
    session_id: Optional[str]  # Session ID for memory management
    use_memory: bool  # Whether to use conversational memory

    # LLM targeting
    target_llm: Optional[str]  # Target LLM (openai, gemini, ollama)

    # Conversation tracing fields
    enable_tracing: bool  # Whether tracing is enabled for this conversation
    conversation_id: Optional[str]  # Unique conversation ID for tracing
    trace_cell_id: Optional[str]  # ID of the trace cell for this conversation
