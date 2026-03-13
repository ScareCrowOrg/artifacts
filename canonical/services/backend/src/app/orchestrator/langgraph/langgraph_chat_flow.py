"""
LangGraph Flow

Main orchestration flow using LangGraph state machine.
"""

import logging
import traceback
from typing import Any, Dict, List, Literal, Optional

from langgraph.graph import END, StateGraph

from ...intention_classifier import IntentionClassifier, IntentionType
from .action_executor import executa_acao
from .function_calling import process_with_function_calling
from .history_manager import manage_chat_history
from .instruction_receiver import recebe_instrucao
from .intention_classifier_node import classifica_intencao
from .langgraph_state import OrchestratorState
from .response_generator import retorna_resposta

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """
    Orchestrates chat interactions using LangGraph.

    The graph follows this flow:
    1. RecebeInstrucao -> ClassificaIntencao
    2. ClassificaIntencao -> ExecutaAcao (if action needed) or RetornaResposta (if just conversation)
    3. ExecutaAcao -> RetornaResposta
    4. RetornaResposta -> ManageChatHistory
    5. ManageChatHistory -> END
    """

    def __init__(self):
        """Initialize the orchestrator with classifier and graph."""
        self.classifier = IntentionClassifier()
        self.graph = self._build_graph()
        self._rag_service = None  # Lazy-loaded RAG service

    def _get_rag_service(self):
        """Get or create the RAG service (lazy loading)."""
        if self._rag_service is None:
            try:
                logger.info("Initializing RAG service with CustomEnsembleRetriever...")
                from ...services.rag_service import get_rag_service

                self._rag_service = get_rag_service()
                logger.info("RAG service initialized successfully")

                # Debug vectorstore after initializing RAG service
                logger.info(
                    "Calling debug_vectorstore to verify collections and document counts..."
                )
                self._rag_service.debug_vectorstore()
                logger.info("debug_vectorstore completed.")
            except Exception as e:
                logger.error("Error initializing RAG service: %s", e)
                logger.error("Full traceback:\n%s", traceback.format_exc())
        return self._rag_service

    async def _recebe_instrucao_wrapper(
        self, state: OrchestratorState
    ) -> OrchestratorState:
        """Wrapper for instruction receiver with RAG service."""
        return await recebe_instrucao(state, self._get_rag_service())

    def _classifica_intencao_wrapper(
        self, state: OrchestratorState
    ) -> OrchestratorState:
        """Wrapper for intention classifier with classifier instance."""
        return classifica_intencao(state, self.classifier)

    def _decide_proxima_etapa(
        self, state: OrchestratorState
    ) -> Literal["executa_acao", "retornar_resposta"]:
        """
        Conditional edge: Decides whether to execute action or return response.

        Args:
            state: Current orchestrator state

        Returns:
            Next node name
        """
        intencao = state.get("intencao", IntentionType.CONVERSAR.value)

        # Only execute actions for CRIAR and EXECUTAR intentions
        if intencao in [IntentionType.CRIAR.value, IntentionType.EXECUTAR.value]:
            return "executa_acao"

        return "retornar_resposta"

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state graph for orchestration.

        Returns:
            Compiled StateGraph
        """
        # Create the graph
        workflow = StateGraph(OrchestratorState)

        # Add nodes
        workflow.add_node("recebe_instrucao", self._recebe_instrucao_wrapper)
        workflow.add_node("classifica_intencao", self._classifica_intencao_wrapper)
        workflow.add_node("executa_acao", executa_acao)
        workflow.add_node("retorna_resposta", retorna_resposta)
        workflow.add_node("manage_chat_history", manage_chat_history)

        # Set entry point
        workflow.set_entry_point("recebe_instrucao")

        # Add edges
        workflow.add_edge("recebe_instrucao", "classifica_intencao")

        # Add conditional edge from classifica_intencao
        workflow.add_conditional_edges(
            "classifica_intencao",
            self._decide_proxima_etapa,
            {"executa_acao": "executa_acao", "retornar_resposta": "retorna_resposta"},
        )

        # Add edge from executa_acao to retorna_resposta
        workflow.add_edge("executa_acao", "retorna_resposta")

        # Add edge from retorna_resposta to manage_chat_history
        workflow.add_edge("retorna_resposta", "manage_chat_history")

        # Add edge from manage_chat_history to END
        workflow.add_edge("manage_chat_history", END)

        # Compile the graph
        return workflow.compile()

    async def process(
        self,
        mensagem: str,
        responsavel_id: str,
        modelo: str = "mistral",
        historico: Optional[List[Dict[str, str]]] = None,
        enable_function_calling: bool = False,
        attached_files: Optional[List[Dict[str, Any]]] = None,
        use_rag: bool = False,
        session_id: Optional[str] = None,
        use_memory: bool = False,
        target_llm: Optional[str] = None,
        enable_tracing: bool = False,
    ) -> Dict[str, Any]:
        """
        Process a user message through the orchestration graph (async).

        Args:
            mensagem: User's message
            responsavel_id: User ID
            modelo: AI model to use
            historico: Conversation history (explicit, overrides memory)
            enable_function_calling: Enable function calling for document access
            attached_files: Files attached from UI (for RAG Priority 1)
            use_rag: Enable RAG context retrieval
            session_id: Session ID for memory management
            use_memory: Enable conversational memory (requires session_id)
            target_llm: Target LLM provider (openai, gemini, ollama)
            enable_tracing: Enable detailed conversation tracing for observability

        Returns:
            Dictionary with response and optional cell data
        """
        # Initialize state
        initial_state: OrchestratorState = {
            "mensagem": mensagem,
            "historico": historico or [],
            "intencao": None,
            "responsavel_id": responsavel_id,
            "modelo": modelo,
            "acao_realizada": False,
            "resultado_acao": None,
            "resposta_final": "",
            "celula_criada": None,
            "document_paths": None,
            "enable_function_calling": enable_function_calling,
            "attached_files": attached_files,
            "attached_files_metadata": None,
            "rag_context": None,
            "use_rag": use_rag,
            "session_id": session_id,
            "use_memory": use_memory,
            "target_llm": target_llm,
            "enable_tracing": enable_tracing,
            "conversation_id": None,
            "trace_cell_id": None,
            "current_chat_summary": None,
            "recent_chat_history": [],
            "turns_since_last_summary": 0,
            "summary_threshold_turns": 10,
            "summary_threshold_tokens": 4000,
        }

        # Adicionando log para verificar o estado inicial do orquestrador
        logger.info("Estado inicial do orquestrador: %s", initial_state)

        # Adicionando log antes de invocar o grafo
        logger.info("Invocando o grafo LangGraph com o estado inicial...")

        # Adicionando log para verificar o valor de use_rag
        logger.info("Valor de use_rag recebido: %s", use_rag)

        # Run the graph asynchronously
        logger.info("Iniciando processamento com LangGraph (async)")
        final_state = await self.graph.ainvoke(initial_state)

        logger.info("Processamento concluído. Intenção: %s", final_state.get('intencao'))

        return {
            "resposta": final_state["resposta_final"],
            "intencao": final_state.get("intencao"),
            "celula": final_state.get("celula_criada"),
            "acao_realizada": final_state.get("acao_realizada", False),
            "conversation_id": final_state.get("conversation_id"),
        }

    async def process_async(
        self,
        mensagem: str,
        responsavel_id: str,
        modelo: str = "gpt-4o",
        historico: Optional[List[Dict[str, str]]] = None,
        enable_function_calling: bool = True,
        attached_files: Optional[List[Dict[str, Any]]] = None,
        use_rag: bool = False,
        session_id: Optional[str] = None,
        use_memory: bool = False,
    ) -> Dict[str, Any]:
        """
        Async version of process with function calling support.

        This method enables the LLM to request document content on-demand
        via function calling instead of sending large documents inline.

        Args:
            mensagem: User's message
            responsavel_id: User ID
            modelo: AI model to use (OpenAI model for function calling)
            historico: Conversation history (explicit, overrides memory)
            enable_function_calling: Enable function calling for document access
            attached_files: Files attached from UI (for RAG Priority 1)
            use_rag: Enable RAG context retrieval
            session_id: Session ID for memory management
            use_memory: Enable conversational memory (requires session_id)

        Returns:
            Dictionary with response and optional cell data
        """
        logger.info("Iniciando processamento async com function calling - Modelo: %s", modelo)

        # Check if function calling should be used (only for OpenAI models)
        is_openai_model = any(modelo.startswith(prefix) for prefix in ["gpt-", "o1-"])

        if enable_function_calling and is_openai_model:
            # Use function calling for OpenAI models
            try:
                resposta = await process_with_function_calling(
                    mensagem=mensagem, historico=historico or [], modelo=modelo
                )

                return {
                    "resposta": resposta,
                    "intencao": IntentionType.CONVERSAR.value,
                    "celula": None,
                    "acao_realizada": False,
                }

            except Exception as e:
                logger.error("Error in async processing with function calling: %s", e)
                logger.error("Full traceback:\n%s", traceback.format_exc())
                return {
                    "resposta": f"Desculpe, ocorreu um erro: {str(e)}",
                    "intencao": None,
                    "celula": None,
                    "acao_realizada": False,
                }
        else:
            # Fall back to async process (now that process is async)
            logger.info(
                "Function calling not enabled or not OpenAI model, using async process"
            )
            return await self.process(
                mensagem=mensagem,
                responsavel_id=responsavel_id,
                modelo=modelo,
                historico=historico,
                enable_function_calling=False,
                attached_files=attached_files,
                use_rag=use_rag,
                session_id=session_id,
                use_memory=use_memory,
            )


# Global orchestrator instance
_orchestrator = None


def get_orchestrator() -> ChatOrchestrator:
    """
    Get or create the global orchestrator instance.

    Returns:
        ChatOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ChatOrchestrator()
    return _orchestrator
