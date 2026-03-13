"""
OpenAI Thread Manager Module

Handles thread creation and retrieval operations for the OpenAI Assistants API.

Functions:
- create_thread: Create a new conversation thread
- get_thread: Retrieve an existing thread

Technical naming: All functions and variables in English.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from ...config import OPENAI_API_KEY, OPENAI_API_URL, OPENAI_TIMEOUT

logger = logging.getLogger(__name__)


async def create_thread(api_key: Optional[str] = None) -> str:
    """
    Create a new conversation thread.

    Args:
        api_key: API Key (optional, falls back to config)

    Returns:
        Thread ID (e.g., 'thread_abc123')

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with OpenAI

    Example:
        >>> thread_id = await create_thread()
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Creating new thread")

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            response = await client.post(
                f"{OPENAI_API_URL}/threads",
                headers={
                    "Authorization": f"Bearer {effective_api_key}",
                    "Content-Type": "application/json",
                    "OpenAI-Beta": "assistants=v2",
                },
                json={},
            )
            response.raise_for_status()

            result = response.json()
            thread_id = result.get("id")

            if not thread_id:
                logger.error("Invalid response from Threads API: %s", result)
                raise ValueError("Invalid response from OpenAI Threads API")

            logger.info("Thread created successfully: %s", thread_id)
            return thread_id

    except httpx.HTTPError as e:
        logger.error("HTTP error creating thread: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error creating thread: %s", e)
        raise


async def get_thread(thread_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve an existing thread.

    Args:
        thread_id: Thread ID to retrieve
        api_key: API Key (optional, falls back to config)

    Returns:
        Thread object

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with OpenAI

    Example:
        >>> thread = await get_thread("thread_abc123")
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Retrieving thread %s", thread_id)

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            response = await client.get(
                f"{OPENAI_API_URL}/threads/{thread_id}",
                headers={
                    "Authorization": f"Bearer {effective_api_key}",
                    "OpenAI-Beta": "assistants=v2",
                },
            )
            response.raise_for_status()

            result = response.json()
            logger.info("Thread %s retrieved successfully", thread_id)
            return result

    except httpx.HTTPError as e:
        logger.error("HTTP error retrieving thread: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error retrieving thread: %s", e)
        raise
