"""
Query Expander Service - Bilingual Query Expansion for RAG Vector Search.

This service enhances RAG vector search by generating expanded queries with bilingual
terms, synonyms, and related keywords using a local LLM (Phi-3 via Ollama).

The expanded query improves search relevance by:
- Including Portuguese and English equivalents of terms
- Adding relevant synonyms and related concepts
- Covering semantic variations that embeddings might miss

Technical naming: All functions and variables in English.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default configuration for query expansion
DEFAULT_EXPANSION_MODEL = "phi3:latest"
MAX_EXPANDED_TERMS = 10

# Prompt template for Phi-3 query expansion
QUERY_EXPANSION_PROMPT_TEMPLATE = """You are a query expansion assistant specialized in bilingual (Portuguese/English) term generation.

Your task: Given a user's question, generate 5-10 relevant search terms including:
1. Key concepts from the original question
2. Synonyms and related terms
3. Portuguese and English equivalents for all terms
4. Technical terms if applicable

Guidelines:
- Keep terms concise (1-3 words each)
- Include both languages (PT and EN)
- Focus on searchable keywords, not full sentences
- Separate terms with commas
- Prioritize technical accuracy over creativity

User Question: "{user_message}"

Example Output Format:
scareverse, universo do medo, horror, terror, fear universe, game, jogo, desenvolvimento, development, architecture, arquitetura

Expanded Search Terms:"""


async def generate_expanded_query(
    user_message: str, model: str = DEFAULT_EXPANSION_MODEL, max_terms: int = MAX_EXPANDED_TERMS
) -> str:
    """
    Generate expanded query with bilingual terms for improved vector search.

    Uses local Phi-3 LLM to analyze the user's message and generate relevant
    search terms in both Portuguese and English. The expanded query helps the
    vector search find more relevant documents across languages.

    Args:
        user_message: Original user question/message
        model: Ollama model to use for expansion (default: phi3:latest)
        max_terms: Maximum number of terms to generate (default: 10)

    Returns:
        Expanded query string with bilingual terms, or original message if expansion fails

    Example:
        >>> expanded = await generate_expanded_query("Como criar uma célula?")
        >>> print(expanded)
        'célula, cell, criar, create, novo, new, item, notebook, estrutura, structure'

        >>> # Use with RAG
        >>> docs = retriever.get_relevant_documents(expanded)
    """
    try:
        logger.info("Generating expanded query for: '%s...'", user_message[:50])

        # Import here to avoid circular dependencies
        from ..ollama_service import chamar_ollama

        # Build the prompt for Phi-3
        prompt = QUERY_EXPANSION_PROMPT_TEMPLATE.format(user_message=user_message)

        # Call Phi-3 via Ollama
        logger.debug("Calling Phi-3 with model: %s", model)
        response = await chamar_ollama(prompt=prompt, model=model, stream=False)

        # Extract the expanded query from response
        expanded_query = response.get("response", "").strip()

        if not expanded_query:
            logger.warning("Phi-3 returned empty response, using original message")
            return user_message

        # Clean and validate the expanded query
        # Remove extra whitespace and ensure it's not too long
        expanded_query = " ".join(expanded_query.split())

        # Limit the number of terms if needed
        terms = [term.strip() for term in expanded_query.split(",")]
        if len(terms) > max_terms:
            logger.info("Truncating expanded query from %s to %s terms", len(terms), max_terms)
            terms = terms[:max_terms]
            expanded_query = ", ".join(terms)

        logger.info("Query expansion successful: %s terms generated (%s chars)", len(terms), len(expanded_query))
        logger.debug("Expanded query: %s", expanded_query)

        return expanded_query

    except Exception as e:
        logger.error("Error generating expanded query: %s", e)
        logger.warning("Falling back to original user message")
        return user_message


async def generate_expanded_query_with_context(
    user_message: str,
    _conversation_history: Optional[list] = None,
    model: str = DEFAULT_EXPANSION_MODEL,
) -> str:
    """
    Generate expanded query considering conversation context.

    Enhanced version that considers recent conversation history to better
    understand the user's intent and generate more relevant terms.

    Args:
        user_message: Current user question/message
        conversation_history: Recent conversation history (optional)
        model: Ollama model to use for expansion (default: phi3:latest)

    Returns:
        Expanded query string with context-aware bilingual terms

    Note:
        This is an advanced feature for future implementation.
        Currently uses the basic expansion without context.
    """
    # For now, use basic expansion
    # Future enhancement: incorporate conversation context into the prompt
    logger.debug("Context-aware expansion not yet implemented, using basic expansion")
    return await generate_expanded_query(user_message, model=model)
