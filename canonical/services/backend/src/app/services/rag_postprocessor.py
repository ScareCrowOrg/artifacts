"""
RAG Post-processor Service - Context Condensation with Local LLM.

This service provides intelligent post-processing of RAG-retrieved chunks using
a local LLM (Phi/Ollama) to condense, filter, and organize context before sending
it to the main LLM.

Features:
- Condenses verbose or redundant chunks
- Filters irrelevant information
- Organizes context logically
- Reduces token usage in main LLM prompts
- Configurable via config.py

Technical naming: All functions and variables in English.
"""

import logging
from typing import List

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


async def condense_context_with_local_llm(
    chunks: List[Document],
    user_query: str,
    model: str,
    prompt_template: str,
    _base_url: str,
    _timeout: int = 30,
) -> str:
    """
    Condense RAG-retrieved chunks using a local LLM (Ollama).

    This function takes raw chunks from RAG retrieval and uses a local LLM
    to create a more concise, relevant, and organized context summary.

    Args:
        chunks: List of Document objects retrieved by RAG
        user_query: The user's original query/question
        model: Ollama model name for post-processing (e.g., "phi3:latest")
        prompt_template: Prompt template with {context} and {query} placeholders
        base_url: Ollama base URL
        timeout: Request timeout in seconds

    Returns:
        Condensed context string ready for the main LLM prompt

    Example:
        >>> chunks = [Document(page_content="...", metadata={}), ...]
        >>> condensed = await condense_context_with_local_llm(
        ...     chunks=chunks,
        ...     user_query="Explain the architecture",
        ...     model="phi3:latest",
        ...     prompt_template=RAG_POSTPROCESS_LLM_PROMPT,
        ...     base_url=OLLAMA_BASE_URL
        ... )
    """
    if not chunks:
        logger.info("No chunks to process for post-processing")
        return ""

    try:
        # Import here to avoid circular dependencies
        from ..ollama_service import chamar_ollama
        from ..utils.input_processor import format_context_for_prompt

        # Format chunks into a structured context string
        raw_context = format_context_for_prompt(chunks)

        logger.info("Post-processing %s chunks (%s chars) with model: %s", len(chunks), len(raw_context), model)

        # Build the prompt for the local LLM
        prompt = prompt_template.format(context=raw_context, query=user_query)

        # Call Ollama to condense the context
        result = await chamar_ollama(prompt=prompt, model=model, stream=False)

        condensed_context = result.get("response", "").strip()

        logger.info(
            "Post-processing complete: Input: %s chars -> Output: %s chars (Reduction: %s%)",
            len(raw_context), len(condensed_context), 100 * (1 - len(condensed_context) / max(len(raw_context), 1))
        )

        return condensed_context

    except Exception as e:
        logger.error("Error during RAG post-processing: %s", e, exc_info=True)
        # Fall back to raw context formatting on error
        logger.warning("Falling back to raw context formatting")
        from ..utils.input_processor import format_context_for_prompt

        return format_context_for_prompt(chunks)


async def postprocess_rag_context(
    chunks: List[Document],
    user_query: str,
    enabled: bool,
    model: str,
    prompt_template: str,
    base_url: str,
    timeout: int = 30,
) -> str:
    """
    Post-process RAG context with optional LLM condensation.

    This is the main entry point for RAG post-processing. It handles
    the conditional logic for enabling/disabling post-processing.

    Args:
        chunks: List of Document objects from RAG retrieval
        user_query: User's original query
        enabled: Whether post-processing is enabled
        model: Ollama model for post-processing
        prompt_template: Prompt template for condensation
        base_url: Ollama base URL
        timeout: Request timeout in seconds

    Returns:
        Formatted context string (condensed if enabled, raw otherwise)

    Example:
        >>> from app.config import (
        ...     RAG_POSTPROCESS_LLM_ENABLED,
        ...     RAG_POSTPROCESS_LLM_MODEL,
        ...     RAG_POSTPROCESS_LLM_PROMPT,
        ...     OLLAMA_BASE_URL,
        ...     OLLAMA_TIMEOUT
        ... )
        >>> context = await postprocess_rag_context(
        ...     chunks=retrieved_chunks,
        ...     user_query="Explain architecture",
        ...     enabled=RAG_POSTPROCESS_LLM_ENABLED,
        ...     model=RAG_POSTPROCESS_LLM_MODEL,
        ...     prompt_template=RAG_POSTPROCESS_LLM_PROMPT,
        ...     base_url=OLLAMA_BASE_URL,
        ...     timeout=OLLAMA_TIMEOUT
        ... )
    """
    if not enabled:
        logger.debug("RAG post-processing disabled, using raw context")
        from ..utils.input_processor import format_context_for_prompt

        return format_context_for_prompt(chunks)

    logger.info("RAG post-processing enabled, condensing context with local LLM")
    return await condense_context_with_local_llm(
        chunks=chunks,
        user_query=user_query,
        model=model,
        prompt_template=prompt_template,
        base_url=base_url,
        timeout=timeout,
    )
