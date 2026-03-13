"""
Ollama Provider Implementation

Concrete implementation of BaseLLMProvider for Ollama local LLM service.
Handles segmented content from attached files by including them directly in prompts.
"""

import logging
from typing import List, Dict, Any, Optional

from ..llm_provider_interface import BaseLLMProvider, LLMProviderError
from ...config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """
    Ollama LLM Provider implementation.

    This provider integrates with a local Ollama instance for generative AI chat.
    It handles attached content by extracting segmented_content from metadata
    and including it directly in the prompt via the centralized prompt_builder.

    Args:
        model_id: Ollama model identifier (default: from config)
        base_url: Ollama API base URL (default: from config)
        timeout: Request timeout in seconds (default: from config)

    Example:
        >>> provider = OllamaProvider(model_id="mistral")
        >>> result = await provider.process_chat(
        ...     user_message="Explain this code",
        ...     attached_content_metadata=[{
        ...         "type": "segmented_content",
        ...         "content": ["def hello(): print('hi')"]
        ...     }]
        ... )
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """Initialize Ollama provider with configuration."""
        self._model_id = model_id or OLLAMA_MODEL
        self._base_url = base_url or OLLAMA_BASE_URL
        self._timeout = timeout or OLLAMA_TIMEOUT

        logger.debug("OllamaProvider initialized - model: %s, base_url: %s", self._model_id, self._base_url)

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "ollama"

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return self._model_id

    async def verify_availability(self) -> bool:
        """Check if Ollama service is available."""
        from ...ollama_service import verificar_ollama_disponivel

        try:
            return await verificar_ollama_disponivel()
        except Exception as e:
            logger.error("Error verifying Ollama availability: %s", e)
            return False

    async def process_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rag_context: Optional[str] = None,
        attached_content_metadata: Optional[List[Dict[str, Any]]] = None,
        system_instructions: Optional[str] = None,
        use_rag: bool = True,
        selected_collections: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process chat with Ollama.

        Extracts segmented_content from attached_content_metadata and includes
        it directly in the prompt. Uses RAG for context retrieval if enabled.
        """
        from ...ollama_service import chamar_ollama
        from ..rag_service import get_rag_service
        from ..prompt_builder import PromptBuilder

        conversation_history = conversation_history or []

        logger.info("OllamaProvider processing chat - Model: %s, History: %s msgs, Use RAG: %s, Collections: %s", self._model_id, len(conversation_history), use_rag, selected_collections if selected_collections else 'none (RAG disabled)')

        # Verify Ollama is available
        if not await self.verify_availability():
            raise LLMProviderError(
                f"Ollama service not available at {self._base_url}", provider=self.provider_name
            )

        # Step 1: Extract segmented content from attached_content_metadata
        segmented_content = []
        if attached_content_metadata:
            for metadata in attached_content_metadata:
                if metadata.get("type") == "segmented_content":
                    content_list = metadata.get("content", [])
                    segmented_content.extend(content_list)

            if segmented_content:
                logger.info("Extracted %s segment(s) from attached_content_metadata", len(segmented_content))

        # Step 2: Retrieve RAG context if not provided and use_rag is True
        if not rag_context and use_rag:
            try:
                rag = get_rag_service()
                logger.debug(
                    "Retrieving RAG context - Query: %s..., Collections: %s",
                    user_message[:50], selected_collections if selected_collections else 'none (RAG disabled)'
                )

                chunks, metadatas, rag_context = await rag.get_context(
                    user_message=user_message,
                    k=5,  # Top 5 relevant chunks per collection
                    selected_collections=selected_collections,
                )

                if rag_context:
                    logger.info(
                        f"RAG context retrieved: {len(chunks)} chunks, " f"{len(rag_context)} chars"
                    )
            except Exception as e:
                logger.warning("Error retrieving RAG context: %s", e)
                rag_context = ""

        # Step 3: Build prompt using centralized builder
        builder = PromptBuilder(
            user_message=user_message,
            conversation_history=conversation_history,
            rag_context=rag_context,
            attached_content=segmented_content,
            system_instructions=system_instructions,
        )
        prompt = builder.build_for_ollama()

        logger.debug("Built prompt - Length: %s chars", len(prompt))

        # Step 4: Call Ollama
        try:
            resultado = await chamar_ollama(prompt, model=self._model_id)
            response_text = resultado.get("response", "")

            logger.info("Ollama response received - Length: %s chars", len(response_text))

            return {"response": response_text}

        except Exception as e:
            logger.error("Error calling Ollama: %s", e)
            raise LLMProviderError(
                f"Failed to process chat: {str(e)}", provider=self.provider_name
            ) from e
