"""
Custom Ensemble Retriever - LangChain 1.0+ Compatible Replacement

This module provides a custom implementation of EnsembleRetriever functionality
that is compatible with LangChain 1.0+ after the deprecation of the original
EnsembleRetriever from langchain.retrievers.

The implementation uses Reciprocal Rank Fusion (RRF) to combine results from
multiple retrievers, which is the same algorithm used by the original
EnsembleRetriever.

Technical naming: All functions and variables in English.
"""

import logging
from typing import List, Optional
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from pydantic import Field

logger = logging.getLogger(__name__)


class CustomEnsembleRetriever(BaseRetriever):
    """
    Custom Ensemble Retriever combining multiple retrievers with weighted results.

    This retriever combines results from multiple retrievers using Reciprocal Rank
    Fusion (RRF) algorithm. RRF is a method that combines rankings from different
    sources by computing a score based on the reciprocal of the rank position.

    The RRF score for a document is calculated as:
        score = sum(weight_i / (k + rank_i))
    where:
        - weight_i is the weight for retriever i
        - rank_i is the rank position of the document in retriever i (1-indexed)
        - k is a constant (default: 60) to prevent division by very small numbers

    This approach is particularly effective for combining results from different
    retrieval methods (e.g., dense vs sparse, different embedding models).

    Attributes:
        retrievers: List of retrievers to combine
        weights: Weight for each retriever (must sum to 1.0 or will be normalized)
        c: Constant for RRF algorithm (default: 60)

    Example:
        >>> retriever1 = vectorstore1.as_retriever(search_kwargs={"k": 5})
        >>> retriever2 = vectorstore2.as_retriever(search_kwargs={"k": 5})
        >>> ensemble = CustomEnsembleRetriever(
        ...     retrievers=[retriever1, retriever2],
        ...     weights=[0.6, 0.4]
        ... )
        >>> docs = ensemble.get_relevant_documents("query")
    """

    retrievers: List[BaseRetriever] = Field(description="List of retrievers to ensemble")
    weights: List[float] = Field(description="Weights for each retriever")
    c: int = Field(default=60, description="Constant for RRF algorithm")

    def __init__(
        self,
        retrievers: List[BaseRetriever],
        weights: Optional[List[float]] = None,
        c: int = 60,
        **kwargs,
    ):
        """
        Initialize the ensemble retriever.

        Args:
            retrievers: List of retrievers to combine
            weights: Optional weights for each retriever (default: equal weights)
            c: Constant for RRF algorithm (default: 60)
            **kwargs: Additional arguments passed to BaseRetriever

        Raises:
            ValueError: If retrievers list is empty or weights length doesn't match
        """
        if not retrievers:
            raise ValueError("At least one retriever must be provided")

        if weights is None:
            weights = [1.0 / len(retrievers)] * len(retrievers)

        if len(weights) != len(retrievers):
            raise ValueError(
                f"Number of weights ({len(weights)}) must match number of "
                f"retrievers ({len(retrievers)})"
            )

        # Normalize weights to sum to 1.0
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        else:
            raise ValueError("Sum of weights must be greater than 0")

        super().__init__(retrievers=retrievers, weights=weights, c=c, **kwargs)

        logger.info(
            "CustomEnsembleRetriever initialized with %s retrievers, weights=%s, c=%s",
            len(retrievers), weights, c
        )

    def _get_relevant_documents(
        self, query: str, *, _run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """
        Retrieve relevant documents from all retrievers and combine using RRF.

        This is the synchronous implementation required by BaseRetriever.

        Args:
            query: The query string
            run_manager: Optional callback manager for retriever run

        Returns:
            List of combined and ranked documents
        """
        # Retrieve documents from each retriever
        retriever_docs = []
        for i, retriever in enumerate(self.retrievers):
            try:
                # Use invoke() for LangChain 1.0+ compatibility
                docs = retriever.invoke(query)
                retriever_docs.append(docs)
                logger.debug("Retriever %s returned %s documents for query: %s...", i, len(docs), query[:50])
            except Exception as e:
                logger.warning("Retriever %s failed: %s", i, e)
                retriever_docs.append([])

        # Combine using Reciprocal Rank Fusion
        combined_docs = self._reciprocal_rank_fusion(retriever_docs)

        logger.info("CustomEnsembleRetriever combined results: %s documents", len(combined_docs))

        return combined_docs

    async def _aget_relevant_documents(
        self, query: str, *, _run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        """
        Async retrieve relevant documents from all retrievers and combine using RRF.

        This is the async implementation that can be used for better performance.

        Args:
            query: The query string
            run_manager: Optional callback manager for retriever run

        Returns:
            List of combined and ranked documents
        """
        # Retrieve documents from each retriever asynchronously
        retriever_docs = []
        for i, retriever in enumerate(self.retrievers):
            try:
                # Use ainvoke() for LangChain 1.0+ compatibility
                docs = await retriever.ainvoke(query)
                retriever_docs.append(docs)
                logger.debug("Retriever %s returned %s documents for query: %s...", i, len(docs), query[:50])
            except Exception as e:
                logger.warning("Async retriever %s failed: %s", i, e)
                retriever_docs.append([])

        # Combine using Reciprocal Rank Fusion
        combined_docs = self._reciprocal_rank_fusion(retriever_docs)

        logger.info("CustomEnsembleRetriever async combined results: %s documents", len(combined_docs))

        return combined_docs

    def _reciprocal_rank_fusion(self, retriever_docs: List[List[Document]]) -> List[Document]:
        """
        Combine documents from multiple retrievers using Reciprocal Rank Fusion.

        RRF algorithm:
        1. For each document, compute RRF score from each retriever where it appears
        2. RRF score = weight / (c + rank), where rank is 1-indexed position
        3. Sum RRF scores across all retrievers for each document
        4. Sort documents by total RRF score in descending order

        Args:
            retriever_docs: List of document lists from each retriever

        Returns:
            Combined and ranked list of documents
        """
        # Map document content to RRF scores
        doc_scores = {}
        doc_map = {}  # Map content to Document object (keep first occurrence)

        for retriever_idx, docs in enumerate(retriever_docs):
            weight = self.weights[retriever_idx]

            for rank, doc in enumerate(docs, start=1):
                # Use page_content as the unique identifier for documents
                doc_id = doc.page_content

                # Calculate RRF score: weight / (c + rank)
                rrf_score = weight / (self.c + rank)

                # Accumulate scores for the same document from different retrievers
                if doc_id in doc_scores:
                    doc_scores[doc_id] += rrf_score
                else:
                    doc_scores[doc_id] = rrf_score
                    doc_map[doc_id] = doc  # Keep the first occurrence

        # Sort documents by RRF score (descending)
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        # Return documents in ranked order
        result = [doc_map[doc_id] for doc_id, score in sorted_docs]

        logger.debug(
            "RRF fusion combined %s retriever results into %s unique documents",
            len(retriever_docs), len(result)
        )

        return result

    def get_relevant_documents(self, query: str) -> List[Document]:
        """
        Compatibility method for backward compatibility with LangChain < 1.0.

        In LangChain 1.0+, this method is replaced by invoke().
        This wrapper ensures backward compatibility with existing code.

        Args:
            query: The query string

        Returns:
            List of relevant documents
        """
        return self.invoke(query)

    async def aget_relevant_documents(self, query: str) -> List[Document]:
        """
        Async compatibility method for backward compatibility with LangChain < 1.0.

        In LangChain 1.0+, this method is replaced by ainvoke().
        This wrapper ensures backward compatibility with existing code.

        Args:
            query: The query string

        Returns:
            List of relevant documents
        """
        return await self.ainvoke(query)
