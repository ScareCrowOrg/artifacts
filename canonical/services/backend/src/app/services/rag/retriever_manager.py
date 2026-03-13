"""
Retriever Manager - Manages vector store retrievers and ensemble retrieval.

This module handles:
- Creating retrievers for individual collections
- Building ensemble retrievers from multiple collections
- Collection validation and filtering

Technical naming: All functions and variables in English.
"""

import logging
from pathlib import Path
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStoreRetriever

from ...config import (
    OLLAMA_EMBEDDING_MODEL,
    RAG_VECTORSTORE_PATH,
)
from .config import (
    AVAILABLE_COLLECTION_NAMES,
    COLLECTION_TO_EMBEDDING_MODEL,
    DEFAULT_RAG_K,
)
from .embeddings import get_embedding_function_for_model_id
from .ensemble_retriever import CustomEnsembleRetriever

logger = logging.getLogger(__name__)


class RetrieverManager:
    """
    Manages creation and lifecycle of vector store retrievers.

    Responsibilities:
    - Create retrievers for individual collections with appropriate embedding models
    - Build ensemble retrievers from multiple collections
    - Validate collection names and filter invalid ones
    - Handle errors gracefully with detailed logging

    Note: NO CACHING - Always creates fresh retrievers to ensure proper behavior.
    """

    def __init__(
        self, api_key: Optional[str] = None, vectorstore_path: Optional[str] = None
    ):
        """
        Initialize retriever manager.

        Args:
            api_key: API key for OpenAI embeddings (optional)
            vectorstore_path: Path to vector store (default: from config)
        """
        self.api_key = api_key
        self.vectorstore_path = vectorstore_path or RAG_VECTORSTORE_PATH

    def get_retriever_for_collection(
        self, collection_name: str, k: int = DEFAULT_RAG_K
    ) -> VectorStoreRetriever:
        """
        Get or create a retriever for a specific collection.

        Each collection uses its appropriate embedding model based on
        COLLECTION_TO_EMBEDDING_MODEL mapping.

        NO CACHING: Always creates a fresh retriever to ensure proper behavior.

        Args:
            collection_name: Name of the ChromaDB collection
            k: Number of documents to retrieve

        Returns:
            VectorStoreRetriever for the specified collection

        Raises:
            FileNotFoundError: If vector store directory doesn't exist
            ValueError: If collection doesn't have a mapped embedding model

        Example:
            >>> manager = RetrieverManager()
            >>> retriever = manager.get_retriever_for_collection('scareverse_docs', k=5)
        """
        try:
            # Determine embedding model for this collection
            embedding_model_id = COLLECTION_TO_EMBEDDING_MODEL.get(collection_name)
            if not embedding_model_id:
                logger.warning(
                    "No embedding model mapped for collection '%s'. Defaulting to '%s'",
                    collection_name, OLLAMA_EMBEDDING_MODEL
                )
                embedding_model_id = OLLAMA_EMBEDDING_MODEL

            # Create embedding function
            embeddings = get_embedding_function_for_model_id(
                embedding_model_id, self.api_key
            )

            # Initialize Chroma vector store
            try:
                # Use RAG_VECTORSTORE_PATH directly
                vectorstore_path = Path(self.vectorstore_path)
                if not vectorstore_path.exists():
                    raise FileNotFoundError(
                        f"Vector store not found at {vectorstore_path}. "
                        "Run document ingestion first: python ingest.py"
                    )

                logger.info("Loading collection '%s' with model '%s'", collection_name, embedding_model_id)
                logger.info(
                    "Creating retriever for collection '%s' with model '%s'",
                    collection_name, embedding_model_id
                )

                # Log vectorstore path
                logger.info("Vectorstore path: %s", vectorstore_path)

                # Log number of documents in the collection
                vectorstore = Chroma(
                    collection_name=collection_name,
                    embedding_function=embeddings,
                    persist_directory=str(vectorstore_path),
                )
                try:
                    results = vectorstore.peek(
                        limit=5
                    )  # Recuperar até 5 documentos para depuração
                    count = len(results["ids"])
                    logger.info("Collection '%s' contains %s documents.", collection_name, count)
                except Exception as e:
                    logger.warning("Failed to count documents in collection '%s': %s", collection_name, e)

                # Create retriever (NO CACHING)
                retriever = vectorstore.as_retriever(search_kwargs={"k": k})

                return retriever
            except Exception as e:
                logger.error("Error creating retriever for collection '%s': %s", collection_name, e)
                raise
        except Exception as e:
            logger.error("Error creating retriever for collection '%s': %s", collection_name, e)
            raise

    def get_ensemble_retriever(
        self, k: int = DEFAULT_RAG_K, selected_collections: Optional[List[str]] = None
    ) -> CustomEnsembleRetriever:
        """
        Get or create CustomEnsembleRetriever combining selected collections.

        CRITICAL BEHAVIOR - NO FALLBACKS:
        - If selected_collections is None or empty [], raises ValueError (RAG should be disabled upstream)
        - Only explicitly selected collections are used
        - Invalid collection names are filtered out and logged
        - If NO valid collections remain after filtering, raises ValueError
        - Custom selections are not cached to ensure correct filtering each time

        This method should NEVER be called if selected_collections is None or empty.
        The caller (get_context) must check this condition first and return empty results.

        Args:
            k: Number of documents to retrieve per collection
            selected_collections: List of collection names to filter (REQUIRED - must not be None/empty)
                                Valid collections are: scareverse_docs, scareverse_code, scareverse_config,
                                scareverse_md, scareverse_json, scareverse_yml

        Returns:
            CustomEnsembleRetriever instance configured with the selected collections

        Raises:
            ValueError: If selected_collections is None, empty, or contains no valid collections

        Example:
            >>> # Correct usage - explicit collection selection
            >>> manager = RetrieverManager()
            >>> retriever = manager.get_ensemble_retriever(
            ...     k=5,
            ...     selected_collections=['scareverse_docs']
            ... )
        """
        # Log the selection process
        logger.info("get_ensemble_retriever called with selected_collections=%s, k=%s", selected_collections, k)
        logger.info("Available collections: %s", AVAILABLE_COLLECTION_NAMES)

        # CRITICAL CHECK: selected_collections MUST be provided and non-empty
        if selected_collections is None or len(selected_collections) == 0:
            raise ValueError(
                "selected_collections must be explicitly provided and non-empty. "
                "RAG cannot execute without explicit collection selection."
            )

        # Validate selected collections
        valid_collections = [
            c for c in selected_collections if c in AVAILABLE_COLLECTION_NAMES
        ]

        if not valid_collections:
            invalid = set(selected_collections) - set(AVAILABLE_COLLECTION_NAMES)
            raise ValueError(
                f"None of the selected collections {selected_collections} are valid. "
                f"Invalid collections: {invalid}. "
                f"Valid collections: {AVAILABLE_COLLECTION_NAMES}"
            )

        # Log warnings for any invalid collections
        if len(valid_collections) != len(selected_collections):
            invalid = set(selected_collections) - set(valid_collections)
            logger.warning("Invalid collections filtered out: %s", invalid)

        collections_to_use = valid_collections

        # Log the final collections to use
        logger.info("Collections to use for EnsembleRetriever: %s", collections_to_use)

        # NO CACHING - Always create fresh ensemble to respect explicit selection
        # Create retrievers for each collection
        retrievers = []
        for collection_name in collections_to_use:
            try:
                logger.info("Attempting to load retriever for collection: %s", collection_name)
                retriever = self.get_retriever_for_collection(collection_name, k=k)
                retrievers.append(retriever)
                logger.info("Successfully added retriever for collection '%s'", collection_name)
            except FileNotFoundError as e:
                logger.warning("Collection '%s' not found: %s", collection_name, e)
            except Exception as e:
                logger.warning("Failed to load collection '%s': %s", collection_name, e)
                # Continue with other collections

        if not retrievers:
            raise RuntimeError(
                f"No retrievers available. Ensure vector store exists and collections are valid. "
                f"Checked collections: {collections_to_use}"
            )

        # Calculate weights for the collections being used
        actual_weights = [1.0 / len(retrievers)] * len(retrievers)  # Equal weights

        logger.info(
            "Creating CustomEnsembleRetriever with %s retrievers for collections: %s",
            len(retrievers), collections_to_use
        )
        logger.info("Weights assigned: %s", actual_weights)

        # Create ensemble retriever (NO CACHING)
        ensemble = CustomEnsembleRetriever(
            retrievers=retrievers, weights=actual_weights
        )

        logger.info("Created fresh CustomEnsembleRetriever (no caching) for collections: %s", collections_to_use)

        return ensemble
