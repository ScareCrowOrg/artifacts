"""
OpenAI Assistant Manager Module

Handles assistant creation and retrieval operations for the OpenAI Assistants API.

Functions:
- create_or_get_assistant: Create or retrieve an assistant

Technical naming: All functions and variables in English.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from ...config import OPENAI_API_KEY, OPENAI_API_URL, OPENAI_TIMEOUT

logger = logging.getLogger(__name__)


async def create_or_get_assistant(
    name: str,
    instructions: str,
    model: str = "gpt-4o-mini",
    tools: Optional[List[Dict[str, Any]]] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Create a new assistant or retrieve existing one by name.

    Args:
        name: Name of the assistant
        instructions: System instructions for the assistant
        model: Model to use (default: gpt-4o-mini)
        tools: List of tool definitions (optional)
        api_key: API Key (optional, falls back to config)

    Returns:
        Assistant ID (e.g., 'asst_abc123')

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with OpenAI

    Example:
        >>> assistant_id = await create_or_get_assistant(
        ...     name="ScareVerse Lab Agent",
        ...     instructions="You are a helpful coding assistant.",
        ...     model="gpt-4o-mini"
        ... )
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Creating/retrieving assistant '%s' with model %s", name, model)

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            # Create assistant
            payload = {"name": name, "instructions": instructions, "model": model}

            if tools:
                payload["tools"] = tools

            response = await client.post(
                f"{OPENAI_API_URL}/assistants",
                headers={
                    "Authorization": f"Bearer {effective_api_key}",
                    "Content-Type": "application/json",
                    "OpenAI-Beta": "assistants=v2",
                },
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            assistant_id = result.get("id")

            if not assistant_id:
                logger.error("Invalid response from Assistants API: %s", result)
                raise ValueError("Invalid response from OpenAI Assistants API")

            logger.info("Assistant created successfully: %s", assistant_id)
            return assistant_id

    except httpx.TimeoutException:
        logger.error("Timeout creating assistant after %ss", OPENAI_TIMEOUT)
        raise
    except httpx.HTTPError as e:
        logger.error("HTTP error creating assistant: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error creating assistant: %s", e)
        raise
