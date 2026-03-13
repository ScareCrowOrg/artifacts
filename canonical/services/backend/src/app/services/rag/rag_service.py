"""
RAG Service - Advanced Retrieval Augmented Generation with Custom Ensemble Retrieval.

This is the main RAG service module providing:
- CustomEnsembleRetriever for multi-collection search across file types
- Query-based RAG for all LLMs (OpenAI, Gemini, Ollama)
- Query expansion and post-processing capabilities
- Similarity search across collections

Technical naming: All functions and variables in English.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from langchain_core.documents import Document

from ...config import (
    BASE_DIR,
    OLLAMA_BASE_URL,
    OLLAMA_TIMEOUT,
    VECTORSTORE_PATH,
    RAG_POSTPROCESS_LLM_ENABLED,
    RAG_POSTPROCESS_LLM_MODEL,
    RAG_POSTPROCESS_LLM_PROMPT,
    RAG_VECTORSTORE_PATH,
)
from ...utils.input_processor import format_context_for_prompt
from .config import DEFAULT_RAG_K, AVAILABLE_COLLECTION_NAMES
from .retriever_manager import RetrieverManager

logger = logging.getLogger(__name__)


class RAGService:
    """
    Advanced RAG service with CustomEnsembleRetriever support.

    Features:
    - Multi-collection ensemble retrieval across different file types
    - Dynamic embedding model selection per collection
    - Query-based RAG for all LLMs
    - No temporary session-based collections

    Example:
        >>> rag = RAGService(
        ...     collection_names=['scareverse_docs', 'scareverse_code'],
        ...     ensemble_weights=[0.6, 0.4]
        ... )
        >>> context = await rag.get_context(
        ...     user_message="Explain architecture",
        ...     session_id="session_123"
        ... )
    """

    def __init__(
        self,
        collection_names: Optional[List[str]] = None,
        vectorstore_path: Optional[str] = None,
        ensemble_weights: Optional[List[float]] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize RAG service with CustomEnsembleRetriever.

        CRITICAL: RAG should NEVER execute without explicit collection selection.
        This __init__ is only used for service instantiation. The actual collection
        filtering happens in get_context() and RetrieverManager.

        Args:
            collection_names: List of collection names to search (if None, RAG will be disabled unless explicitly provided later)
            vectorstore_path: Path to vector store (default: from config)
            ensemble_weights: Weights for each collection in ensemble (default: equal weights)
            api_key: API key for OpenAI embeddings if needed (optional)
        """
        self.vectorstore_path = vectorstore_path or VECTORSTORE_PATH
        self.api_key = api_key

        # Store available collection names for validation
        # DO NOT default to any collections - RAG must be explicitly requested
        self.available_collection_names = AVAILABLE_COLLECTION_NAMES

        # Instance collections (only used if explicitly provided)
        # If None, RAG will be disabled unless collections are explicitly selected in get_context()
        self.collection_names = collection_names

        # Default to equal weights if not specified
        if ensemble_weights is None and collection_names:
            ensemble_weights = [1.0 / len(collection_names)] * len(collection_names)

        self.ensemble_weights = ensemble_weights

        # Initialize retriever manager
        self.retriever_manager = RetrieverManager(
            api_key=api_key, vectorstore_path=vectorstore_path
        )

        logger.info(
            "RAGService initialized - Collections: %s, Weights: %s",
            self.collection_names or 'none (RAG disabled by default)', self.ensemble_weights
        )

    async def get_context(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        k: int = DEFAULT_RAG_K,
        selected_collections: Optional[List[str]] = None,
        enable_postprocessing: Optional[bool] = None,
        enable_query_expansion: Optional[bool] = True,
    ) -> Tuple[str, List[Document], str]:
        """
        Retrieve RAG context for user message using CustomEnsembleRetriever.

        CRITICAL BEHAVIOR - NO IMPLICIT RAG EXECUTION:
        This is the main entry point for query-based RAG operations.
        RAG is ONLY executed when collections are EXPLICITLY selected by the user.

        Optionally applies query expansion for bilingual support and post-processing
        with a local LLM to condense and filter the context.

        Collection filtering behavior (STRICT):
        - If selected_collections is None (field omitted), RAG is DISABLED - returns empty context
        - If selected_collections is [] (empty list), RAG is DISABLED - returns empty context
        - If selected_collections contains specific collections, ONLY those are used for search
        - Invalid collection names are automatically filtered out and logged
        - If NO valid collections remain after filtering, raises ValueError (upstream should handle)
        - NO FALLBACKS to "all collections" or "default collections" under ANY circumstances

        Query expansion behavior:
        - If enable_query_expansion is True (default), expands query with bilingual terms using Phi-3
        - Improves search relevance for Portuguese/English bilingual project
        - Falls back to original query if expansion fails

        Post-processing behavior:
        - If enable_postprocessing is None, uses RAG_POSTPROCESS_LLM_ENABLED from config
        - If enable_postprocessing is True, condenses context with local LLM
        - If enable_postprocessing is False, uses raw context formatting

        Args:
            user_message: User's message/query
            session_id: Session identifier (for logging/tracking)
            k: Number of documents to retrieve per collection
            selected_collections: List of collection names to filter search (REQUIRED for RAG)
                                (e.g., ['scareverse_docs', 'scareverse_code'])
                                If None or empty [], RAG is DISABLED (returns empty context)
                                Only valid collections will be used for retrieval
            enable_postprocessing: Override config setting for post-processing (optional)
            enable_query_expansion: Enable bilingual query expansion with Phi-3 (default: True)

        Returns:
            Tuple of (processed_message, context_documents, formatted_context)
            - processed_message: Original message (unchanged)
            - context_documents: List of relevant Document objects (empty if RAG disabled)
            - formatted_context: Formatted string ready for LLM prompt (empty if RAG disabled)

        Example:
            >>> # RAG DISABLED (no collections selected - field omitted)
            >>> msg, docs, context = await rag.get_context(
            ...     "Explain the API structure",
            ...     session_id="abc123"
            ... )  # Returns empty docs and context
            >>>
            >>> # RAG ENABLED (explicit collection selection)
            >>> msg, docs, context = await rag.get_context(
            ...     "Explain the API structure",
            ...     selected_collections=["scareverse_docs"],
            ...     enable_query_expansion=True,
            ...     enable_postprocessing=True
            ... )  # Returns relevant documents and formatted context
        """
        try:
            logger.info("Iniciando o método get_context no serviço RAG...")
            logger.info(
                "Parâmetros recebidos: user_message=%s, session_id=%s, k=%s, selected_collections=%s",
                user_message, session_id, k, selected_collections
            )
            logger.info("[RAG DIAGNOSIS] selected_collections type: %s, value: %s, is_none: %s, is_empty_list: %s", type(selected_collections), selected_collections, selected_collections is None, selected_collections is not None and len(selected_collections) == 0)

            # Check if RAG should be disabled (None or empty list)
            # None = field omitted in request payload (no collections selected)
            # [] = explicitly empty list (no collections selected)
            if selected_collections is None or len(selected_collections) == 0:
                logger.info(
                    "RAG desabilitado: %s - nenhuma coleção selecionada pelo usuário",
                    'campo omitido (None)' if selected_collections is None else 'lista de coleções vazia'
                )
                # Return empty context - RAG is explicitly disabled
                return user_message, [], ""

            # Step 1: Expand query with bilingual terms if enabled
            search_query = user_message  # Default to original message
            if enable_query_expansion:
                try:
                    logger.info("Expanding query with bilingual terms using Phi-3...")
                    from ..query_expander_service import generate_expanded_query

                    expanded_query = await generate_expanded_query(user_message)
                    if expanded_query and expanded_query != user_message:
                        search_query = expanded_query
                        logger.info(
                            "Query expanded successfully: '%s...' -> '%s...'",
                            user_message[:50], search_query[:100]
                        )
                    else:
                        logger.info("Query expansion returned original message, using as-is")
                except Exception as e:
                    logger.warning("Query expansion failed: %s. Using original message.", e)
                    # Continue with original message
            else:
                logger.info("Query expansion disabled, using original message")

            # Step 2: Get ensemble retriever (with optional collection filtering)
            ensemble_retriever = self.retriever_manager.get_ensemble_retriever(
                k=k, selected_collections=selected_collections
            )

            # Step 3: Perform retrieval with the search query (expanded or original)
            logger.info("Executando busca com CustomEnsembleRetriever usando query: '%s...'", search_query[:100])
            context_docs = ensemble_retriever.get_relevant_documents(search_query)

            # Log detalhes dos documentos retornados
            logger.info("Documentos retornados pelo CustomEnsembleRetriever: %s", len(context_docs))

            # Determine if post-processing should be applied
            should_postprocess = (
                enable_postprocessing
                if enable_postprocessing is not None
                else RAG_POSTPROCESS_LLM_ENABLED
            )

            # Post-process context if enabled
            if should_postprocess and context_docs:
                logger.info("Applying RAG post-processing with local LLM")
                try:
                    import asyncio
                    from ..rag_postprocessor import postprocess_rag_context

                    try:
                        loop = asyncio.get_running_loop()
                        formatted_context = await postprocess_rag_context(
                            chunks=context_docs,
                            user_query=user_message,
                            enabled=True,
                            model=RAG_POSTPROCESS_LLM_MODEL,
                            prompt_template=RAG_POSTPROCESS_LLM_PROMPT,
                            base_url=OLLAMA_BASE_URL,
                            timeout=OLLAMA_TIMEOUT,
                        )
                    except RuntimeError:
                        # No running loop, safe to use asyncio.run
                        formatted_context = asyncio.run(
                            postprocess_rag_context(
                                chunks=context_docs,
                                user_query=user_message,
                                enabled=True,
                                model=RAG_POSTPROCESS_LLM_MODEL,
                                prompt_template=RAG_POSTPROCESS_LLM_PROMPT,
                                base_url=OLLAMA_BASE_URL,
                                timeout=OLLAMA_TIMEOUT,
                            )
                        )
                except Exception as e:
                    logger.error("Error in post-processing, falling back to raw format: %s", e)
                    formatted_context = format_context_for_prompt(context_docs)
            else:
                # Format context without post-processing
                formatted_context = format_context_for_prompt(context_docs)

            logger.info("RAG context retrieved: %s documentos, %s caracteres no contexto formatado, collections used: %s, query_expansion: %s, post-processing: %s", len(context_docs), len(formatted_context), selected_collections or 'all', enable_query_expansion, should_postprocess)

            return user_message, context_docs, formatted_context

        except Exception as e:
            logger.error("Erro ao recuperar contexto RAG: %s", e)
            # Log adicional para debugging
            logger.debug("Detalhes do erro:", exc_info=True)
            # Retorna contexto vazio em caso de erro
            return user_message, [], ""

    def search_similar(
        self, query: str, k: int = DEFAULT_RAG_K, collection_name: Optional[str] = None
    ) -> List[Document]:
        """
        Perform similarity search in a specific collection or across all collections.

        Args:
            query: Search query
            k: Number of results to return
            collection_name: Specific collection to search (if None, uses ensemble)

        Returns:
            List of relevant Document objects

        Example:
            >>> # Search across all collections
            >>> docs = rag.search_similar("authentication flow", k=5)
            >>>
            >>> # Search in specific collection
            >>> docs = rag.search_similar("database models", collection_name="scareverse_code")
        """
        try:
            if collection_name:
                # Search specific collection
                retriever = self.retriever_manager.get_retriever_for_collection(
                    collection_name, k=k
                )
                results = retriever.get_relevant_documents(query)
            else:
                # Use ensemble retriever
                ensemble_retriever = self.retriever_manager.get_ensemble_retriever(k=k)
                results = ensemble_retriever.get_relevant_documents(query)

            logger.info("Similarity search returned %s results", len(results))
            return results

        except Exception as e:
            logger.error("Error in similarity search: %s", e)
            return []

    def ensure_vectorstore_exists(self) -> bool:
        """
        Ensure vector store is initialized and accessible.

        Returns:
            True if vector store exists and is accessible, False otherwise
        """
        try:
            vectorstore_path = Path(RAG_VECTORSTORE_PATH)
            return vectorstore_path.exists()
        except Exception as e:
            logger.warning("Vector store not accessible: %s", e)
            return False

    def debug_vectorstore(self):
        """
        Debug method to log the number of documents in each collection.
        """
        try:
            vectorstore_path = Path(RAG_VECTORSTORE_PATH)
            logger.info("Debugging vectorstore at: %s", vectorstore_path)

            for collection_name in self.collection_names:
                try:
                    retriever = self.retriever_manager.get_retriever_for_collection(collection_name)
                    count = retriever.vectorstore.count()
                    logger.info("Collection '%s' has %s documents.", collection_name, count)
                except Exception as e:
                    logger.warning("Failed to debug collection '%s': %s", collection_name, e)
        except Exception as e:
            logger.error("Error debugging vectorstore: %s", e)


def get_rag_service(
    collection_names: Optional[List[str]] = None,
    ensemble_weights: Optional[List[float]] = None,
    api_key: Optional[str] = None,
) -> RAGService:
    """
    Factory function to create RAG service instance.

    CRITICAL: This factory creates a service instance but does NOT enable RAG by default.
    RAG execution requires explicit collection selection in get_context() calls.

    Args:
        collection_names: List of collection names (optional - if None, RAG will be disabled
                         unless explicitly provided later in get_context())
        ensemble_weights: Weights for each collection (default: equal weights)
        api_key: API key for OpenAI embeddings (optional)

    Returns:
        Configured RAGService instance

    Example:
        >>> # Create service without default collections (RAG disabled by default)
        >>> rag = get_rag_service()
        >>> # Must explicitly provide collections when calling get_context()
        >>> context = await rag.get_context(
        ...     "query",
        ...     selected_collections=["scareverse_docs"]
        ... )
        >>>
        >>> # Create service with specific collections (still requires explicit selection in get_context)
        >>> rag = get_rag_service(
        ...     collection_names=['scareverse_docs', 'scareverse_md'],
        ...     ensemble_weights=[0.7, 0.3]
        ... )
    """
    return RAGService(
        collection_names=collection_names, ensemble_weights=ensemble_weights, api_key=api_key
    )
