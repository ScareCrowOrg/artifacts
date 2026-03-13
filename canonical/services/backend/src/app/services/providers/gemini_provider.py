"""
Gemini Provider Implementation

Concrete implementation of BaseLLMProvider for Google's Gemini API.
Handles file_id metadata from attached files via Gemini Files API.
"""

import logging
from typing import List, Dict, Any, Optional

from ..llm_provider_interface import BaseLLMProvider, LLMProviderError
from ...config import GEMINI_API_KEY, GEMINI_DEFAULT_MODEL, GEMINI_TIMEOUT

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Gemini LLM Provider implementation.

    This provider integrates with Google's Gemini API for generative AI chat.
    It handles attached content by extracting file_id from metadata and
    referencing already uploaded files via Gemini Files API.

    Args:
        model_id: Gemini model identifier (default: from config)
        api_key: Gemini API key (default: from config)
        timeout: Request timeout in seconds (default: from config)

    Example:
        >>> provider = GeminiProvider(model_id="gemini-2.5-flash")
        >>> result = await provider.process_chat(
        ...     user_message="Analyze this file",
        ...     attached_content_metadata=[{
        ...         "type": "file_id",
        ...         "id": "file_abc123"
        ...     }]
        ... )
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """Initialize Gemini provider with configuration."""
        self._model_id = model_id or GEMINI_DEFAULT_MODEL
        self._api_key = api_key or GEMINI_API_KEY
        self._timeout = timeout or GEMINI_TIMEOUT

        if not self._api_key:
            logger.warning("Gemini API key not configured")

        logger.debug(
            "GeminiProvider initialized - model: %s, api_key: %s",
            self._model_id, '***' if self._api_key else 'None'
        )

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "gemini"

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return self._model_id

    async def verify_availability(self) -> bool:
        """Check if Gemini API is available."""
        from ...gemini_service import verificar_gemini_disponivel

        try:
            return await verificar_gemini_disponivel()
        except Exception as e:
            logger.error("Error verifying Gemini availability: %s", e)
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
        Process chat with Gemini.

        Extracts file_id from attached_content_metadata and references them
        via Gemini Files API. Uses RAG for context retrieval if enabled.
        """
        from ...gemini_service import chamar_gemini
        from ..rag_service import get_rag_service
        from ..prompt_builder import PromptBuilder

        conversation_history = conversation_history or []

        # Validate API key
        if not self._api_key:
            raise LLMProviderError(
                "Gemini API Key not configured. Set GEMINI_API_KEY in .env",
                provider=self.provider_name,
            )

        logger.info("GeminiProvider processing chat - Model: %s, History: %s msgs, Use RAG: %s, Collections: %s", self._model_id, len(conversation_history), use_rag, selected_collections if selected_collections else 'none (RAG disabled)')

        # Step 1: Extract file URIs from attached_content_metadata
        file_uris = []
        if attached_content_metadata:
            for metadata in attached_content_metadata:
                # Support both "file_uri" (from chat_router) and "file_id" (legacy)
                if metadata.get("type") == "file_uri":
                    file_uri = metadata.get("uri")
                    if file_uri:
                        file_uris.append(file_uri)
                elif metadata.get("type") == "file_id":
                    file_id = metadata.get("id")
                    if file_id:
                        # Construct file URI from ID
                        # Format: https://generativelanguage.googleapis.com/v1beta/files/{fileId}
                        if not file_id.startswith("http"):
                            file_uri = (
                                f"https://generativelanguage.googleapis.com/v1beta/files/{file_id}"
                            )
                        else:
                            file_uri = file_id
                        file_uris.append(file_uri)

            if file_uris:
                logger.info(
                    f"Extracted {len(file_uris)} file URI(s) from " f"attached_content_metadata"
                )

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

        # Step 3: Build messages using centralized builder
        builder = PromptBuilder(
            user_message=user_message,
            conversation_history=conversation_history,
            rag_context=rag_context,
            system_instructions=system_instructions,
        )
        messages = builder.build_for_gemini(file_uris=file_uris if file_uris else None)

        logger.debug("Built Gemini messages - Count: %s", len(messages))

        # Step 4: Call Gemini
        try:
            resultado = await chamar_gemini(messages, model=self._model_id, api_key=self._api_key)
            response_text = resultado.get("response", "")

            logger.info("Gemini response received - Length: %s chars", len(response_text))

            return {"response": response_text}

        except Exception as e:
            logger.error("Error calling Gemini: %s", e)
            raise LLMProviderError(
                f"Failed to process chat: {str(e)}", provider=self.provider_name
            ) from e
