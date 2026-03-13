"""
Unified Prompt Builder Service

This module provides centralized prompt generation logic for all LLM providers
(Ollama, Gemini, OpenAI). It ensures consistent prompt structure and reduces
code duplication across service modules.

Key Features:
- Unified prompt construction with RAG context, conversation history, and attachments
- Provider-specific output formatting (string for Ollama, messages list for chat APIs)
- Consistent instructions about conversation history usage
- Configurable history minification to manage token limits
- Support for system prompts and conversation summaries
- **Explicit attachment notifications** (Zero Inference Principle compliance)
  - Clear notification when files are attached
  - Attachment count and importance emphasized
  - Provider-specific attachment handling (file URIs, file paths, or direct content)

Zero Inference Principle Compliance:
The PromptBuilder explicitly notifies LLMs about attached files to ensure they:
1. Are aware that attachments were provided
2. Understand the attachments contain essential context
3. Prioritize attachment content when generating responses
4. Do not require inference about whether files are present

Usage:
    >>> builder = PromptBuilder(
    ...     user_message="Explain the architecture",
    ...     conversation_history=[{"role": "user", "content": "Hi"}],
    ...     rag_context="Context from docs...",
    ...     attached_content=["file content..."],  # Explicit attachment
    ...     system_instructions="You are a helpful assistant"
    ... )
    >>>
    >>> # For Ollama (string format with explicit attachment notification)
    >>> prompt_str = builder.build_for_ollama()
    >>>
    >>> # For Gemini (messages list format with file URIs)
    >>> messages = builder.build_for_gemini(file_uris=["https://..."])
    >>>
    >>> # For OpenAI (messages list format with attachment notification)
    >>> messages = builder.build_for_openai(attachments_content=["file content..."])
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Constants
MINIFIED_CONTENT_MAX_LENGTH = 50
MAX_COMPLETE_MESSAGES = 5

# Standard instruction about conversation history usage
HISTORY_USAGE_INSTRUCTION = (
    "IMPORTANTE: O 'Histórico da Conversa' abaixo é fornecido apenas para sua referência "
    "e para manter a continuidade do diálogo. Sua resposta deve se basear exclusivamente "
    "na 'Nova Pergunta' do usuário, sem repetir questões ou assumir que as questões "
    "do histórico são a intenção atual."
)


class PromptBuilder:
    """
    Centralized prompt builder for all LLM providers.

    This class encapsulates the logic for constructing prompts with consistent
    structure across different LLM providers while adapting to their specific
    input format requirements.

    Args:
        user_message: Current user message/intent
        conversation_history: List of previous conversation turns
                             Format: [{'role': 'user'/'assistant', 'content': str}]
        rag_context: Retrieved context from RAG system
        attached_content: List of file contents attached to the message
        system_instructions: System-level instructions/prompt
        current_chat_summary: Summary of the conversation so far (optional)
        recent_chat_history: Recent chat history from hybrid management (optional)
        max_complete_messages: Number of recent messages to keep in full (default: 5)

    Example:
        >>> builder = PromptBuilder(
        ...     user_message="Create a login system",
        ...     conversation_history=[
        ...         {"role": "user", "content": "Hi"},
        ...         {"role": "assistant", "content": "Hello! How can I help?"}
        ...     ],
        ...     rag_context="Context about authentication...",
        ...     system_instructions="You are a helpful coding assistant"
        ... )
        >>> ollama_prompt = builder.build_for_ollama()
        >>> openai_messages = builder.build_for_openai()
    """

    def __init__(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rag_context: Optional[str] = None,
        attached_content: Optional[List[str]] = None,
        system_instructions: Optional[str] = None,
        current_chat_summary: Optional[str] = None,
        recent_chat_history: Optional[List[Dict[str, str]]] = None,
        max_complete_messages: int = MAX_COMPLETE_MESSAGES,
    ):
        """Initialize the prompt builder with message components."""
        self.user_message = user_message
        self.conversation_history = conversation_history or []
        self.rag_context = rag_context or ""
        self.attached_content = attached_content or []
        self.system_instructions = system_instructions or ""
        self.current_chat_summary = current_chat_summary
        self.recent_chat_history = recent_chat_history
        self.max_complete_messages = max_complete_messages

        # Use recent_chat_history if provided, otherwise use conversation_history
        self.history_to_use = (
            recent_chat_history if recent_chat_history else (conversation_history or [])
        )

        logger.debug("PromptBuilder initialized - User message length: %s, History messages: %s, RAG context: %s, Attachments: %s, System instructions: %s", len(user_message), len(self.history_to_use), bool(rag_context), len(self.attached_content), bool(system_instructions))

    def _format_context_section(self) -> str:
        """
        Format RAG context and attached content sections.

        Returns:
            Formatted context string with clear section markers and explicit
            attachment notifications to ensure LLMs understand files were provided.
        """
        sections = []

        # Add RAG context if available
        if self.rag_context:
            sections.append(
                "### Contexto Relevante do Repositório ###\n"
                f"{self.rag_context}\n"
                "### Fim do Contexto ###"
            )

        # Add attached file content if available with explicit notification
        if self.attached_content:
            # EXPLICIT ATTACHMENT NOTIFICATION
            attachment_count = len(self.attached_content)
            notification = (
                f"⚠️ IMPORTANTE: O usuário anexou {attachment_count} arquivo(s) com informações essenciais.\n"
                f"Estes arquivos contêm dados contextuais que devem ser utilizados como base para sua resposta.\n"
                f"VOCÊ DEVE analisar o conteúdo dos arquivos anexados abaixo.\n"
            )

            segments = [notification]
            for i, content in enumerate(self.attached_content, 1):
                segments.append(
                    f"--- Arquivo Anexado {i} de {attachment_count} ---\n{content}"
                )

            sections.append(
                "### 📎 ARQUIVOS ANEXADOS PELO USUÁRIO ###\n"
                + "\n\n".join(segments)
                + "\n"
                "### FIM DOS ARQUIVOS ANEXADOS ###"
            )

        # Add usage instruction if there's any context
        if sections:
            usage_instruction = "Use as informações do contexto acima como referência para apoiar sua resposta à pergunta do usuário. "

            # Add specific instruction if attachments are present
            if self.attached_content:
                usage_instruction += "PRIORIZE o conteúdo dos arquivos anexados, pois são dados fornecidos explicitamente pelo usuário. "

            usage_instruction += (
                "Responda diretamente à pergunta com base no que foi solicitado."
            )

            sections.append(usage_instruction)

        return "\n\n".join(sections)

    def _format_history_section(self) -> str:
        """
        Format conversation history with minification for older messages.

        Returns:
            Formatted history string with section markers
        """
        if not self.history_to_use:
            return ""

        # Add conversation summary if available
        summary_text = ""
        if self.current_chat_summary or self.recent_chat_history:
            try:
                from ..utils.conversation_memory import format_context_for_prompt

                context = format_context_for_prompt(
                    self.current_chat_summary, self.recent_chat_history or []
                )
                if context:
                    summary_text = context + "\n\n"
            except ImportError:
                logger.warning("conversation_memory module not available")

        # Separate recent complete messages from older ones
        complete_msgs = (
            self.history_to_use[-self.max_complete_messages :]
            if len(self.history_to_use) > self.max_complete_messages
            else self.history_to_use
        )
        older_msgs = (
            self.history_to_use[: -self.max_complete_messages]
            if len(self.history_to_use) > self.max_complete_messages
            else []
        )

        # Build history section
        history_parts = []

        # Add minified older messages if any
        if older_msgs:
            minified = " | ".join(
                (
                    f"{msg['role']}: {msg['content'][:MINIFIED_CONTENT_MAX_LENGTH]}..."
                    if len(msg["content"]) > MINIFIED_CONTENT_MAX_LENGTH
                    else f"{msg['role']}: {msg['content']}"
                )
                for msg in older_msgs
            )
            history_parts.append(f"Histórico resumido: {minified}\n")

        # Add recent complete messages
        for msg in complete_msgs:
            history_parts.append(f"{msg['role']}: {msg['content']}")

        history_content = "\n".join(history_parts)

        return (
            f"{summary_text}"
            f"{HISTORY_USAGE_INSTRUCTION}\n\n"
            f"### Histórico da Conversa ###\n"
            f"{history_content}"
        )

    def build_for_ollama(self) -> str:
        """
        Build prompt string for Ollama (single string format).

        Returns:
            Complete prompt as a single formatted string

        Example:
            >>> builder = PromptBuilder(user_message="Hello")
            >>> prompt = builder.build_for_ollama()
            >>> assert isinstance(prompt, str)
        """
        parts = []

        # Add context sections (RAG + attachments)
        context = self._format_context_section()
        if context:
            parts.append(context)

        # Add history section
        history = self._format_history_section()
        if history:
            parts.append(history)

        # Add current user message
        parts.append("### Nova Pergunta ###")
        parts.append(f"user: {self.user_message}")

        prompt = "\n\n".join(parts)

        logger.debug("Built Ollama prompt - Length: %s chars", len(prompt))
        return prompt

    def build_for_gemini(
        self, file_uris: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build messages list for Gemini API (contents format).

        Args:
            file_uris: Optional list of Gemini Files API URIs

        Returns:
            List of message dictionaries in Gemini format
            Format: [{"role": "user"/"model", "parts": [{"text": "..."}]}]

        Example:
            >>> builder = PromptBuilder(user_message="Analyze this file")
            >>> messages = builder.build_for_gemini(
            ...     file_uris=["https://generativelanguage.googleapis.com/v1beta/files/abc"]
            ... )
        """
        contents = []

        # Add conversation summary as context if available
        if self.current_chat_summary or self.recent_chat_history:
            try:
                from ..utils.conversation_memory import format_context_for_prompt

                context = format_context_for_prompt(
                    self.current_chat_summary, self.recent_chat_history or []
                )
                if context:
                    context_with_instruction = (
                        f"{HISTORY_USAGE_INSTRUCTION}\n\n{context}"
                    )
                    contents.append(
                        {"role": "user", "parts": [{"text": context_with_instruction}]}
                    )
                    contents.append(
                        {
                            "role": "model",
                            "parts": [
                                {"text": "I understand the conversation context."}
                            ],
                        }
                    )
            except ImportError:
                logger.warning("conversation_memory module not available")

        # Add history usage instruction if history exists
        if self.history_to_use:
            contents.append(
                {"role": "user", "parts": [{"text": HISTORY_USAGE_INSTRUCTION}]}
            )
            contents.append(
                {
                    "role": "model",
                    "parts": [
                        {"text": "Entendido. Vou focar na nova pergunta do usuário."}
                    ],
                }
            )

        # Add conversation history
        for msg in self.history_to_use:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        # Build current message with context and attachments
        current_message_parts = []

        # Add explicit file notification if files are provided via Gemini Files API
        if file_uris:
            file_count = len(file_uris)
            file_notification = (
                f"⚠️ IMPORTANTE: O usuário anexou {file_count} arquivo(s) usando a API de Arquivos do Gemini.\n"
                f"Estes arquivos contêm informações essenciais que você DEVE analisar e usar como contexto.\n"
                f"Os arquivos estão disponíveis nos {file_count} fileData parts anexados a esta mensagem.\n"
                f"VOCÊ TEM ACESSO ao conteúdo completo dos arquivos através do Gemini Files API."
            )
            current_message_parts.append({"text": file_notification})

        # Add RAG context to current message if available
        context = self._format_context_section()
        if context:
            current_message_parts.append({"text": context})

        # Add user message
        current_message_parts.append({"text": self.user_message})

        # Add file URIs if provided (after explicit notification)
        if file_uris:
            for uri in file_uris:
                current_message_parts.append({"fileData": {"fileUri": uri}})

        contents.append({"role": "user", "parts": current_message_parts})

        logger.debug(
            "Built Gemini messages - Count: %s, File URIs: %s",
            len(contents), len(file_uris) if file_uris else 0
        )
        return contents

    def build_for_openai(
        self, attachments_content: Optional[List[str]] = None
    ) -> List[Dict[str, str]]:
        """
        Build messages list for OpenAI API (chat completions format).

        Args:
            attachments_content: Optional list of attachment contents to include
                                in the user message

        Returns:
            List of message dictionaries in OpenAI format
            Format: [{"role": "system"/"user"/"assistant", "content": "..."}]

        Example:
            >>> builder = PromptBuilder(
            ...     user_message="Fix this code",
            ...     system_instructions="You are a helpful coding assistant"
            ... )
            >>> messages = builder.build_for_openai(
            ...     attachments_content=["def hello(): print('hi')"]
            ... )
        """
        messages = []

        # Build enhanced system prompt
        enhanced_system = self.system_instructions

        # Add conversation summary if available
        if self.current_chat_summary:
            try:
                from ..utils.conversation_memory import format_context_for_prompt

                context = format_context_for_prompt(
                    self.current_chat_summary, self.recent_chat_history or []
                )
                if context:
                    if enhanced_system:
                        enhanced_system += f"\n\n{context}"
                    else:
                        enhanced_system = context
            except ImportError:
                logger.warning("conversation_memory module not available")

        # Add history usage instruction to system prompt
        if self.history_to_use:
            history_instruction = f"\n\n{HISTORY_USAGE_INSTRUCTION}"
            enhanced_system += history_instruction

        # Add RAG context to system prompt if available
        if self.rag_context:
            rag_section = (
                "\n\n### Contexto Relevante do Repositório ###\n"
                f"{self.rag_context}\n"
                "### Fim do Contexto ###\n\n"
                "Use as informações do contexto acima como referência para apoiar sua resposta à pergunta do usuário. "
                "Priorize responder diretamente à pergunta com base no que foi solicitado."
            )
            enhanced_system += rag_section

        # Add system message if we have any system content
        if enhanced_system:
            messages.append({"role": "system", "content": enhanced_system})

        # Add conversation history
        for msg in self.history_to_use:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})

        # Build current user message
        full_message = self.user_message

        # Determine if we have attachments to add
        has_attachments = bool(attachments_content or self.attached_content)

        # Add attachment content with explicit notification
        if attachments_content:
            attachment_count = len(attachments_content)
            attachment_notification = (
                f"\n\n⚠️ IMPORTANTE: Você recebeu {attachment_count} arquivo(s) anexado(s) pelo usuário.\n"
                f"Estes arquivos contêm informações essenciais que você DEVE analisar e usar como base para sua resposta.\n"
                f"Os arquivos estão incluídos abaixo na seção '📎 Anexos'.\n"
            )
            full_message += attachment_notification
            full_message += "\n---\n📎 Anexos:\n" + "\n".join(attachments_content)

        # Add attached content from builder if available (no duplicate)
        elif self.attached_content:
            attachment_count = len(self.attached_content)
            attachment_notification = (
                f"\n\n⚠️ IMPORTANTE: Você recebeu {attachment_count} arquivo(s) anexado(s) pelo usuário.\n"
                f"Estes arquivos contêm informações essenciais que você DEVE analisar e usar como base para sua resposta.\n"
                f"Os arquivos estão incluídos abaixo na seção '📎 Anexos'.\n"
            )
            full_message += attachment_notification
            full_message += "\n---\n📎 Anexos:\n" + "\n".join(self.attached_content)

        messages.append({"role": "user", "content": full_message})

        logger.debug(
            "Built OpenAI messages - Count: %s, Attachments: %s",
            len(messages), attachment_count if has_attachments else 0
        )
        return messages


def build_prompt_for_provider(
    provider: str,
    user_message: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    rag_context: Optional[str] = None,
    attached_content: Optional[List[str]] = None,
    system_instructions: Optional[str] = None,
    current_chat_summary: Optional[str] = None,
    recent_chat_history: Optional[List[Dict[str, str]]] = None,
    max_complete_messages: int = MAX_COMPLETE_MESSAGES,
    **provider_specific_kwargs,
) -> Any:
    """
    Convenience function to build prompts for any provider.

    Args:
        provider: LLM provider identifier ("ollama", "gemini", "openai")
        user_message: Current user message/intent
        conversation_history: Previous conversation turns
        rag_context: Retrieved context from RAG
        attached_content: File contents attached to message
        system_instructions: System-level instructions
        current_chat_summary: Conversation summary (optional)
        recent_chat_history: Recent chat history (optional)
        max_complete_messages: Number of recent messages to keep in full
        **provider_specific_kwargs: Provider-specific arguments
            - For Gemini: file_uris (List[str])
            - For OpenAI: attachments_content (List[str])

    Returns:
        Provider-specific prompt format (str for Ollama, List[Dict] for others)

    Raises:
        ValueError: If provider is not recognized

    Example:
        >>> # For Ollama
        >>> prompt = build_prompt_for_provider(
        ...     provider="ollama",
        ...     user_message="Hello",
        ...     rag_context="Context..."
        ... )
        >>>
        >>> # For Gemini with files
        >>> messages = build_prompt_for_provider(
        ...     provider="gemini",
        ...     user_message="Analyze",
        ...     file_uris=["https://..."]
        ... )
    """
    builder = PromptBuilder(
        user_message=user_message,
        conversation_history=conversation_history,
        rag_context=rag_context,
        attached_content=attached_content,
        system_instructions=system_instructions,
        current_chat_summary=current_chat_summary,
        recent_chat_history=recent_chat_history,
        max_complete_messages=max_complete_messages,
    )

    provider_lower = provider.lower()

    if provider_lower == "ollama":
        return builder.build_for_ollama()
    elif provider_lower == "gemini":
        file_uris = provider_specific_kwargs.get("file_uris")
        return builder.build_for_gemini(file_uris=file_uris)
    elif provider_lower == "openai":
        attachments_content = provider_specific_kwargs.get("attachments_content")
        return builder.build_for_openai(attachments_content=attachments_content)
    else:
        raise ValueError(
            f"Unsupported provider: {provider}. "
            "Supported providers: ollama, gemini, openai"
        )
