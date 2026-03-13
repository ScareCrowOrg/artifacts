"""
OpenAI Provider Implementation

Concrete implementation of BaseLLMProvider for OpenAI's API.
Handles file_id metadata from attached files via OpenAI Assistants API.
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..llm_provider_interface import BaseLLMProvider, LLMProviderError
from ...config import OPENAI_API_KEY, OPENAI_DEFAULT_MODEL, OPENAI_TIMEOUT

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM Provider implementation.

    This provider integrates with OpenAI's API for generative AI chat.
    It handles attached content by extracting file_id from metadata and
    referencing files via OpenAI Assistants API.

    Supports two modes:
    1. Chat Completions API (standard)
    2. Assistants API (with thread management and file attachments)

    Args:
        model_id: OpenAI model identifier (default: from config)
        api_key: OpenAI API key (default: from config)
        timeout: Request timeout in seconds (default: from config)
        use_assistants_api: Whether to use Assistants API (default: True for file handling)

    Example:
        >>> provider = OpenAIProvider(model_id="gpt-4")
        >>> result = await provider.process_chat(
        ...     user_message="Analyze this file",
        ...     attached_content_metadata=[{
        ...         "type": "file_id",
        ...         "id": "file_abc123"
        ...     }],
        ...     thread_id="thread_xyz"  # For conversation continuity
        ... )
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        use_assistants_api: bool = True,
    ):
        """Initialize OpenAI provider with configuration."""
        self._model_id = model_id or OPENAI_DEFAULT_MODEL
        self._api_key = api_key or OPENAI_API_KEY
        self._timeout = timeout or OPENAI_TIMEOUT
        self._use_assistants_api = use_assistants_api

        if not self._api_key:
            logger.warning("OpenAI API key not configured")

        logger.debug(
            "OpenAIProvider initialized - model: %s, api_key: %s, use_assistants_api: %s",
            self._model_id, '***' if self._api_key else 'None', use_assistants_api
        )

    @property
    def provider_name(self) -> str:
        """Return provider identifier."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Return model identifier."""
        return self._model_id

    async def verify_availability(self) -> bool:
        """Check if OpenAI API is available."""
        from ...openai_service import verificar_openai_disponivel

        try:
            return await verificar_openai_disponivel(api_key=self._api_key)
        except Exception as e:
            logger.error("Error verifying OpenAI availability: %s", e)
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
        thread_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process chat with OpenAI.

        Extracts file_id from attached_content_metadata and references them
        via OpenAI Assistants API. Uses RAG for context retrieval if enabled.

        Additional Args:
            thread_id: Existing thread ID for conversation continuity (optional)
            assistant_id: Existing assistant ID for reuse (optional)

        Returns:
            Dict with:
                - response: str - Response text
                - thread_id: str - Thread ID for continuation (if using Assistants API)
                - assistant_id: str - Assistant ID for reuse (if using Assistants API)
        """
        from ...openai_service import chamar_openai
        from ..rag_service import get_rag_service
        from ..prompt_builder import PromptBuilder

        conversation_history = conversation_history or []

        # Validate API key
        if not self._api_key:
            raise LLMProviderError(
                "OpenAI API Key not configured. Set OPENAI_API_KEY in .env",
                provider=self.provider_name,
            )

        logger.info("OpenAIProvider processing chat - Model: %s, History: %s msgs, Use RAG: %s, Collections: %s, Thread: %s", self._model_id, len(conversation_history), use_rag, selected_collections if selected_collections else 'none (RAG disabled)', thread_id or 'new')

        # Step 1: Extract file paths/IDs from attached_content_metadata
        file_paths = []
        if attached_content_metadata:
            for metadata in attached_content_metadata:
                # Support both "file_path" (from chat_router) and "file_id" (legacy)
                if metadata.get("type") == "file_path":
                    file_path = metadata.get("path")
                    if file_path:
                        file_paths.append(Path(file_path))
                        logger.debug("Added file path from attached_content_metadata: %s", file_path)
                elif metadata.get("type") == "file_id":
                    file_id = metadata.get("id")
                    if file_id:
                        # For Assistants API, we need file paths, not IDs
                        # The metadata should contain the path to temp files
                        file_path = metadata.get("path")
                        if file_path:
                            file_paths.append(Path(file_path))
                            logger.debug("Added file path from file_id metadata: %s", file_path)

            if file_paths:
                logger.info(
                    "Extracted %s file path(s) from attached_content_metadata for OpenAI Assistants API",
                    len(file_paths)
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

        # Step 3: Decide which API to use based on attachments and configuration
        has_attachments = bool(file_paths)
        use_assistants = self._use_assistants_api and (has_attachments or thread_id)

        if use_assistants:
            # Use Assistants API for file handling and thread continuity
            return await self._process_with_assistants_api(
                user_message=user_message,
                conversation_history=conversation_history,
                rag_context=rag_context,
                system_instructions=system_instructions,
                file_paths=file_paths,
                thread_id=thread_id,
                assistant_id=assistant_id,
            )
        else:
            # Use standard Chat Completions API
            return await self._process_with_chat_api(
                user_message=user_message,
                conversation_history=conversation_history,
                rag_context=rag_context,
                system_instructions=system_instructions,
            )

    async def _process_with_chat_api(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        rag_context: Optional[str],
        system_instructions: Optional[str],
    ) -> Dict[str, Any]:
        """Process chat using standard Chat Completions API."""
        from ...openai_service import chamar_openai
        from ..prompt_builder import PromptBuilder

        # Build messages using centralized builder
        builder = PromptBuilder(
            user_message=user_message,
            conversation_history=conversation_history,
            rag_context=rag_context,
            system_instructions=system_instructions,
        )
        messages = builder.build_for_openai()

        logger.debug("Built OpenAI messages - Count: %s", len(messages))

        # Build payload
        payload = {
            "model": self._model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        try:
            response_data = await chamar_openai(
                payload=payload, api_key=self._api_key, timeout=self._timeout
            )

            if response_data and response_data.get("choices"):
                response_text = response_data["choices"][0]["message"]["content"]
            else:
                response_text = "No response from OpenAI."

            logger.info(
                f"OpenAI Chat API response received - " f"Length: {len(response_text)} chars"
            )

            return {"response": response_text}

        except Exception as e:
            logger.error("Error calling OpenAI Chat API: %s", e)
            raise LLMProviderError(
                f"Failed to process chat: {str(e)}", provider=self.provider_name
            ) from e

    async def _process_with_assistants_api(
        self,
        user_message: str,
        _conversation_history: List[Dict[str, str]],
        rag_context: Optional[str],
        system_instructions: Optional[str],
        file_paths: List[Path],
        thread_id: Optional[str],
        assistant_id: Optional[str],
    ) -> Dict[str, Any]:
        """Process chat using OpenAI Assistants API with file handling."""
        from ..openai_assistant_service import process_with_assistant

        # Build enhanced message with explicit file notification and RAG context
        enhanced_message = ""

        # Add explicit file notification if files are being uploaded
        if file_paths:
            file_count = len(file_paths)
            file_notification = (
                f"⚠️ IMPORTANTE: O usuário anexou {file_count} arquivo(s) usando a API de Assistentes do OpenAI.\n"
                f"Estes arquivos contêm informações essenciais que você DEVE analisar e usar como contexto.\n"
                f"Os arquivos foram carregados para o assistente e estão disponíveis para análise.\n"
                f"VOCÊ TEM ACESSO ao conteúdo completo dos arquivos através da OpenAI Assistants API.\n\n"
            )
            enhanced_message += file_notification

        # Add RAG context if available
        if rag_context:
            enhanced_message += (
                "### Contexto Relevante do Repositório ###\n"
                f"{rag_context}\n"
                "### Fim do Contexto ###\n\n"
                "Use as informações do contexto acima como referência para "
                "apoiar sua resposta à pergunta do usuário. "
                "Priorize responder diretamente à pergunta com base no que foi solicitado.\n\n"
            )

        # Add user message
        enhanced_message += f"Pergunta do usuário: {user_message}"

        logger.debug(
            f"Using Assistants API - " f"Files: {len(file_paths)}, " f"Thread: {thread_id or 'new'}"
        )

        try:
            response_text, new_thread_id, new_assistant_id = await process_with_assistant(
                user_message=enhanced_message,
                thread_id=thread_id,
                assistant_id=assistant_id,
                file_paths=file_paths if file_paths else None,
                system_instructions=system_instructions,
                model=self._model_id,
                api_key=self._api_key,
            )

            logger.info(
                "OpenAI Assistants API response received - Length: %s chars, Thread: %s...",
                len(response_text), new_thread_id[:12]
            )

            return {
                "response": response_text,
                "thread_id": new_thread_id,
                "assistant_id": new_assistant_id,
            }

        except Exception as e:
            logger.error("Error calling OpenAI Assistants API: %s", e)
            raise LLMProviderError(
                f"Failed to process chat: {str(e)}", provider=self.provider_name
            ) from e
