"""
Instruction Receiver Node

Receives and prepares user instructions with context.
"""

import logging
from typing import Optional

from .langgraph_state import OrchestratorState
from .file_processor import process_attached_files

logger = logging.getLogger(__name__)


async def recebe_instrucao(state: OrchestratorState, rag_service=None) -> OrchestratorState:
    """
    Node: Receives the user instruction.

    This is the entry point of the graph.
    - Loads conversation history from memory if enabled
    - Processes attached files based on target_llm
    - Retrieves query-based RAG context if enabled

    Args:
        state: Current orchestrator state
        rag_service: Optional RAG service instance (lazy-loaded)

    Returns:
        Updated state with initialized fields and context
    """
    logger.info("RecebeInstrucao: %s...", state['mensagem'][:50])

    # Log RAG configuration at entry
    logger.info("[RAG] use_rag flag: %s", state.get('use_rag', False))
    logger.info("[RAG] target_llm: %s", state.get('target_llm'))
    logger.info("[RAG] session_id: %s", state.get('session_id'))

    # Initialize state fields if not present
    state = _initialize_state_fields(state)

    # Initialize conversation tracing if enabled
    if state.get("enable_tracing", False):
        state = await _initialize_conversation_tracing(state)

    # Load conversation history from memory if enabled
    if state.get("use_memory", False) and state.get("session_id"):
        state = _load_conversation_memory(state)

    # Process attached files based on target_llm (async operation)
    if state.get("attached_files"):
        logger.info("[RAG] Processing %s attached file(s)", len(state['attached_files']))
        state = await process_attached_files(state)

    # Retrieve query-based RAG context if enabled
    # This should work for ALL models (gemini, openai, ollama) when use_rag=True
    if state.get("use_rag", False):
        if rag_service:
            logger.info("[RAG] RAG is enabled - retrieving context...")
            state = await _retrieve_rag_context(state, rag_service)
        else:
            logger.warning("[RAG] RAG enabled but rag_service is None!")
    else:
        logger.info("[RAG] RAG is disabled for this request")

    return state


def _initialize_state_fields(state: OrchestratorState) -> OrchestratorState:
    """
    Initialize state fields with default values.

    Args:
        state: Current orchestrator state

    Returns:
        State with initialized fields
    """
    # Initialize basic fields
    if "acao_realizada" not in state:
        state["acao_realizada"] = False
    if "resultado_acao" not in state:
        state["resultado_acao"] = None
    if "celula_criada" not in state:
        state["celula_criada"] = None
    if "document_paths" not in state:
        state["document_paths"] = None
    if "enable_function_calling" not in state:
        state["enable_function_calling"] = False
    if "attached_files" not in state:
        state["attached_files"] = None
    if "attached_files_metadata" not in state:
        state["attached_files_metadata"] = None
    if "rag_context" not in state:
        state["rag_context"] = None
    if "use_rag" not in state:
        state["use_rag"] = False
    if "session_id" not in state:
        state["session_id"] = None
    if "use_memory" not in state:
        state["use_memory"] = False
    if "target_llm" not in state:
        state["target_llm"] = None

    # Initialize chat history management fields
    if "current_chat_summary" not in state:
        state["current_chat_summary"] = None
    if "recent_chat_history" not in state:
        state["recent_chat_history"] = []
    if "turns_since_last_summary" not in state:
        state["turns_since_last_summary"] = 0
    if "summary_threshold_turns" not in state:
        from ...utils.conversation_memory import DEFAULT_SUMMARY_THRESHOLD_TURNS

        state["summary_threshold_turns"] = DEFAULT_SUMMARY_THRESHOLD_TURNS
    if "summary_threshold_tokens" not in state:
        from ...utils.conversation_memory import DEFAULT_SUMMARY_THRESHOLD_TOKENS

        state["summary_threshold_tokens"] = DEFAULT_SUMMARY_THRESHOLD_TOKENS

    # Initialize conversation tracing fields
    if "enable_tracing" not in state:
        state["enable_tracing"] = False
    if "conversation_id" not in state:
        state["conversation_id"] = None
    if "trace_cell_id" not in state:
        state["trace_cell_id"] = None

    return state


def _load_conversation_memory(state: OrchestratorState) -> OrchestratorState:
    """
    Load conversation history from memory.

    Args:
        state: Current orchestrator state

    Returns:
        State with loaded conversation history
    """
    try:
        from ...utils.conversation_memory import get_session_memory

        session_id = state["session_id"]
        logger.info("Loading conversation memory for session: %s", session_id)

        memory_manager = get_session_memory(session_id)
        memory_history = memory_manager.get_history_as_dicts()

        # Use memory history if no explicit history provided
        if not state.get("historico"):
            state["historico"] = memory_history
            logger.info("Loaded %s messages from memory", len(memory_history))

    except Exception as e:
        logger.error("Error loading conversation memory: %s", e)
        # Continue without memory on error

    return state


async def _initialize_conversation_tracing(state: OrchestratorState) -> OrchestratorState:
    """
    Initialize conversation tracing by creating trace cell and recording initial fragment.

    This function is called when enable_tracing=True in the state. It:
    1. Generates a conversation_id if not already present
    2. Creates a trace cell in the conversation-traces-book-v1
    3. Records the initial_prompt fragment

    Args:
        state: Current orchestrator state

    Returns:
        State with tracing initialized (conversation_id and trace_cell_id set)
    """
    try:
        from ...services.conversation_trace_service import get_conversation_trace_service

        trace_service = get_conversation_trace_service()

        # Check if tracing is globally enabled
        if not trace_service.is_tracing_enabled():
            logger.info("[ConversationTrace] Global tracing is disabled, skipping initialization")
            state["enable_tracing"] = False
            return state

        # Generate conversation ID if not present
        if not state.get("conversation_id"):
            state["conversation_id"] = trace_service.generate_conversation_id(
                session_id=state.get("session_id")
            )
            logger.info("[ConversationTrace] Generated conversation ID: %s", state['conversation_id'])

        # Create trace cell
        trace_cell = await trace_service.create_trace_cell(
            conversation_id=state["conversation_id"],
            assignee_id=state["responsavel_id"],
            session_id=state.get("session_id"),
            user_message=state["mensagem"],
            target_llm=state.get("target_llm"),
        )

        if trace_cell:
            state["trace_cell_id"] = trace_cell.id
            logger.info(
                f"[ConversationTrace] Tracing enabled for conversation: {state['conversation_id']}, "
                f"trace cell: {trace_cell.id}"
            )

            # Record initial prompt fragment
            await trace_service.record_fragment(
                trace_cell_id=trace_cell.id,
                stage="initial_prompt",
                data={
                    "user_message": state["mensagem"],
                    "session_id": state.get("session_id"),
                    "target_llm": state.get("target_llm"),
                    "use_rag": state.get("use_rag", False),
                    "use_memory": state.get("use_memory", False),
                },
                conversation_id=state["conversation_id"],
            )
            logger.info("[ConversationTrace] Recorded initial_prompt fragment")
        else:
            logger.warning("[ConversationTrace] Failed to create trace cell, disabling tracing")
            state["enable_tracing"] = False

    except Exception as e:
        logger.error("[ConversationTrace] Error initializing tracing: %s", e, exc_info=True)
        # Disable tracing on error but don't fail the request
        state["enable_tracing"] = False

    return state


async def _retrieve_rag_context(state: OrchestratorState, rag_service) -> OrchestratorState:
    """
    Retrieve RAG context with prioritization for attached/referenced files.

    This function orchestrates RAG context retrieval in a prioritized manner:
    1. Priority 1: Process attached files (already handled in process_attached_files)
    2. Priority 2: Process file references from message (#file/path syntax)
    3. Priority 3: General RAG search across all collections

    The final rag_context combines prioritized context with general search results,
    with the most relevant context appearing first.

    This function is called for ALL models (gemini, openai, ollama)
    when use_rag=True, ensuring consistent RAG activation.

    Args:
        state: Current orchestrator state
        rag_service: RAG service instance

    Returns:
        State with RAG context
    """
    logger.info("[RAG] Starting _retrieve_rag_context method with prioritization")
    logger.info("[RAG] User message: %s...", state.get('mensagem')[:100])
    logger.info("[RAG] Session ID: %s", state.get('session_id'))
    logger.info("[RAG] Target LLM: %s", state.get('target_llm'))

    try:
        from ...utils.input_processor import (
            extract_file_references,
            process_file_references,
            remove_file_references,
        )

        user_message = state["mensagem"]
        prioritized_documents = []

        # Priority 2: Extract and process file references from message
        file_references = extract_file_references(user_message)
        if file_references:
            logger.info("[RAG Priority 2] Processing %s file reference(s) from message", len(file_references))

            # Get the vectorstore from rag_service if available
            try:
                # Access the first collection's vectorstore for file reference search
                if hasattr(rag_service, "_retrievers") and rag_service._retrievers:
                    # Get any retriever to access its vectorstore
                    first_retriever = next(iter(rag_service._retrievers.values()))
                    vectorstore = (
                        first_retriever.vectorstore
                        if hasattr(first_retriever, "vectorstore")
                        else None
                    )
                else:
                    vectorstore = None

                ref_docs = process_file_references(
                    file_paths=file_references,
                    user_message=user_message,
                    vectorstore=vectorstore,
                    k=3,  # Get top 3 chunks per referenced file
                )

                if ref_docs:
                    logger.info("[RAG Priority 2] Retrieved %s document(s) from file references", len(ref_docs))
                    prioritized_documents.extend(ref_docs)

                    # Remove file references from message for general search
                    user_message = remove_file_references(user_message).strip()
                    logger.info("[RAG Priority 2] Cleaned message: %s...", user_message[:100])

            except Exception as e:
                logger.warning("[RAG Priority 2] Error processing file references: %s", e)

        # Priority 3: General RAG search across all collections
        # Only do general search if we don't have enough prioritized context
        # or if we want to supplement prioritized context with general context
        if (
            len(prioritized_documents) < 3
        ):  # Threshold: if we have fewer than 3 docs, do general search
            logger.info("[RAG Priority 3] Performing general RAG search...")

            # Enrich search query with context from prioritized documents if available
            search_query = user_message
            if prioritized_documents:
                # Extract key terms from prioritized documents to guide general search
                from ...utils.input_processor import format_context_for_prompt

                priority_context_preview = format_context_for_prompt(prioritized_documents[:2])[
                    :200
                ]
                logger.info("[RAG Priority 3] Enriching search with priority context: %s...", priority_context_preview)

            # Perform general RAG search
            _, general_docs, _ = rag_service.get_context(
                user_message=search_query,
                session_id=state.get("session_id"),
                k=5,  # Retrieve top 5 documents per collection
            )

            if general_docs:
                logger.info("[RAG Priority 3] Retrieved %s document(s) from general search", len(general_docs))

                # Add general docs that aren't already in prioritized docs
                # (simple deduplication based on content preview)
                existing_content = {doc.page_content[:100] for doc in prioritized_documents}
                for doc in general_docs:
                    if doc.page_content[:100] not in existing_content:
                        prioritized_documents.append(doc)
        else:
            logger.info(
                "[RAG Priority 3] Skipping general search - sufficient prioritized context (%s docs)",
                len(prioritized_documents)
            )

        # Store combined context in state with priority preserved
        state["rag_context"] = prioritized_documents

        logger.info(
            "[RAG] Context successfully retrieved: %s total documents (prioritized)",
            len(prioritized_documents)
        )

        # Log a sample of the context for debugging
        if prioritized_documents:
            first_doc = prioritized_documents[0]
            if hasattr(first_doc, "page_content"):
                logger.info("[RAG] First document preview: %s...", first_doc.page_content[:150])
                logger.info("[RAG] First document source: %s", first_doc.metadata.get('source', 'unknown'))
            elif isinstance(first_doc, dict):
                logger.info("[RAG] First document preview: %s...", str(first_doc)[:150])

        # Record trace fragment if tracing is enabled
        if state.get("enable_tracing") and state.get("trace_cell_id"):
            await _record_rag_retrieval_fragment(state, prioritized_documents, user_message)

    except Exception as e:
        logger.error("[RAG] Error retrieving RAG context: %s", e, exc_info=True)
        # Continue without RAG on error - set empty context
        state["rag_context"] = []

    logger.info("[RAG] Finished _retrieve_rag_context method")

    return state


async def _record_rag_retrieval_fragment(
    state: OrchestratorState, documents: list, query: str
) -> None:
    """
    Record RAG retrieval trace fragment.

    Args:
        state: Current orchestrator state
        documents: Retrieved documents
        query: Search query used
    """
    try:
        from ...services.conversation_trace_service import get_conversation_trace_service

        trace_service = get_conversation_trace_service()

        # Extract document metadata
        chunks_data = []
        for doc in documents[:5]:  # Limit to first 5 for fragment size
            if hasattr(doc, "page_content"):
                chunks_data.append(
                    {
                        "content_preview": doc.page_content[:200],
                        "source": doc.metadata.get("source", "unknown"),
                        "score": doc.metadata.get("score", "N/A"),
                    }
                )
            elif isinstance(doc, dict):
                chunks_data.append(
                    {"content_preview": str(doc)[:200], "source": "dict", "score": "N/A"}
                )

        # Record fragment
        success = await trace_service.record_fragment(
            trace_cell_id=state["trace_cell_id"],
            stage="rag_retrieval",
            data={
                "query_used": query[:200],
                "chunks_retrieved": len(documents),
                "chunks_preview": chunks_data,
                "use_rag": state.get("use_rag", False),
            },
            conversation_id=state["conversation_id"],
        )

        if success:
            logger.info("[ConversationTrace] Recorded rag_retrieval fragment for %s chunk(s)", len(documents))
        else:
            logger.warning("[ConversationTrace] Failed to record rag_retrieval fragment")

    except Exception as e:
        logger.error("[ConversationTrace] Error recording rag_retrieval fragment: %s", e, exc_info=True)
        # Don't fail the workflow on tracing errors
