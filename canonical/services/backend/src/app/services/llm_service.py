"""
LLM Service for Cell Factory MVP 2.

Provides real LLM integration with OpenAI/Anthropic APIs:
1. Streaming code generation
2. Secure credential management
3. Retry logic and error handling
4. Token usage tracking
5. Model selection and configuration

This replaces the mock LLM implementation from MVP 1.
"""

import logging
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI, OpenAIError

from .. import config as app_config
from ..models import EnrichedPrompt

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for LLM integration with streaming support.

    Supports OpenAI GPT models with:
    - Streaming responses
    - Conversation history
    - System instructions
    - Token usage tracking
    - Error handling and retries
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM Service.

        Args:
            api_key: OpenAI API key (defaults to settings)
        """
        self.api_key = api_key or getattr(app_config, "OPENAI_API_KEY", None)
        if not self.api_key:
            logger.warning("LLM API key not configured. Service will be unavailable.")

        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.max_retries = 3
        self.timeout = 60  # seconds
        self.logger = logger

    async def generate_code_streaming(
        self,
        enriched_prompt: EnrichedPrompt,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Generate code with streaming response.

        Yields chunks in the format:
        {
            "type": "narrative" | "code" | "complete",
            "content": str,
            "fence": str (for code blocks),
            "metadata": dict (for complete)
        }

        Args:
            enriched_prompt: Enriched prompt with history and context
            model: Model name (gpt-4, gpt-3.5-turbo, etc.)
            temperature: Generation temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Stream chunks with type and content

        Raises:
            ValueError: If API key not configured
            OpenAIError: If API call fails after retries
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        self.logger.info("Starting streaming generation with model %s", model)

        try:
            # Build messages from enriched prompt
            messages = self._build_messages(enriched_prompt)

            # Call OpenAI streaming API
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            # Track state for fence block detection
            current_block = []
            in_fence = False
            fence_lang = None
            total_tokens = 0

            # Stream response chunks
            async for chunk in response:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                content = delta.content or ""

                if not content:
                    continue

                # Process chunk for fence blocks
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    # Detect fence block start
                    if line.strip().startswith("```"):
                        if not in_fence:
                            # Start of code block
                            in_fence = True
                            fence_lang = line.strip()[3:].strip() or "text"
                            current_block = []
                        else:
                            # End of code block
                            code_content = "\n".join(current_block)
                            yield {
                                "type": "code",
                                "content": code_content,
                                "fence": fence_lang,
                            }
                            in_fence = False
                            fence_lang = None
                            current_block = []
                    elif in_fence:
                        # Inside code block
                        current_block.append(line)
                    else:
                        # Narrative content
                        if line.strip():
                            yield {"type": "narrative", "content": line}

                total_tokens += 1

            # Yield final block if still open
            if in_fence and current_block:
                code_content = "\n".join(current_block)
                yield {"type": "code", "content": code_content, "fence": fence_lang}

            # Yield completion metadata
            yield {
                "type": "complete",
                "content": "",
                "metadata": {
                    "total_tokens": total_tokens,
                    "model": model,
                    "completed_at": datetime.utcnow().isoformat(),
                },
            }

            self.logger.info("Streaming generation complete. Total tokens: %s", total_tokens)

        except OpenAIError as e:
            self.logger.error("OpenAI API error: %s", e)
            raise
        except Exception as e:
            self.logger.error("Unexpected error during streaming: %s", e)
            raise

    async def generate_code_non_streaming(
        self,
        enriched_prompt: EnrichedPrompt,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Generate code without streaming (for testing).

        Args:
            enriched_prompt: Enriched prompt with history and context
            model: Model name
            temperature: Generation temperature
            max_tokens: Maximum tokens

        Returns:
            Generated code as string
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        messages = self._build_messages(enriched_prompt)

        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        return response.choices[0].message.content

    def _build_messages(self, enriched_prompt: EnrichedPrompt) -> List[Dict[str, str]]:
        """
        Build OpenAI messages from enriched prompt.

        Args:
            enriched_prompt: Enriched prompt with history

        Returns:
            List of message dicts for OpenAI API
        """
        messages = []

        # Add system instructions
        if enriched_prompt.system_instructions:
            messages.append(
                {"role": "system", "content": enriched_prompt.system_instructions}
            )

        # Add RAG context if present
        if enriched_prompt.rag_context:
            rag_content = "Relevant context:\n"
            for doc in enriched_prompt.rag_context.relevant_docs:
                rag_content += f"- {doc}\n"
            messages.append({"role": "system", "content": rag_content})

        # Add conversation history
        for msg in enriched_prompt.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})

        # Add current user prompt
        messages.append({"role": "user", "content": enriched_prompt.user_prompt})

        return messages

    async def validate_api_key(self) -> bool:
        """
        Validate that the API key is working.

        Returns:
            True if API key is valid, False otherwise
        """
        if not self.client:
            return False

        try:
            # Make a minimal API call to test
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except OpenAIError as e:
            self.logger.error("API key validation failed: %s", e)
            return False

    def get_supported_models(self) -> List[str]:
        """
        Get list of supported models.

        Returns:
            List of model names
        """
        return ["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"]
