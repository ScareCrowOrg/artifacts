"""
LangGraph Orchestrator State Definition

Defines the state structure used throughout the orchestration graph.
"""

from typing import Any, Dict, List, Optional, TypedDict


class OrchestratorState(TypedDict):
    """State for the orchestrator graph."""

    mensagem: str
    historico: List[Dict[str, str]]
    intencao: Optional[str]
    responsavel_id: str
    modelo: str
    acao_realizada: bool
    resultado_acao: Optional[Dict[str, Any]]
    resposta_final: str
    celula_criada: Optional[Dict[str, Any]]
    document_paths: Optional[List[str]]  # Paths to documents referenced by user
    enable_function_calling: bool  # Whether to use function calling for document access
    attached_files: Optional[
        List[Dict[str, Any]]
    ]  # Files attached from UI (temp storage)
    attached_files_metadata: Optional[
        List[Dict[str, Any]]
    ]  # Processed attachment metadata
    rag_context: Optional[List[Any]]  # RAG context documents
    use_rag: bool  # Whether to use RAG for this request
    session_id: Optional[str]  # Session ID for memory management
    use_memory: bool  # Whether to use conversational memory
    target_llm: Optional[str]  # Target LLM (openai, gemini, ollama)
    # Chat history management fields
    current_chat_summary: Optional[str]  # LLM-generated consolidated summary
    recent_chat_history: List[Dict[str, str]]  # Last N turns (user/agent exchanges)
    turns_since_last_summary: int  # Counter of turns since last summarization
    summary_threshold_turns: int  # Turn limit to trigger summarization
    summary_threshold_tokens: int  # Token limit to trigger summarization
    # Conversation tracing fields
    enable_tracing: bool  # Whether tracing is enabled for this conversation
    conversation_id: Optional[str]  # Unique conversation ID for tracing
    trace_cell_id: Optional[str]  # ID of the trace cell for this conversation
