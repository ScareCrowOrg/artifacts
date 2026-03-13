"""
OpenAI Message Manager Module

Handles message operations for the OpenAI Assistants API.

Functions:
- add_message_to_thread: Add a message with optional file attachments
- get_run_messages: Retrieve messages from a thread

Technical naming: All functions and variables in English.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from ...config import OPENAI_API_KEY, OPENAI_API_URL, OPENAI_TIMEOUT

logger = logging.getLogger(__name__)


async def add_message_to_thread(
    thread_id: str,
    content: str,
    role: str = "user",
    file_ids: Optional[List[str]] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Add a message to a thread with optional file attachments.

    Args:
        thread_id: Thread ID to add message to
        content: Message content
        role: Message role (default: "user")
        file_ids: List of file IDs to attach (optional)
        api_key: API Key (optional, falls back to config)

    Returns:
        Message ID (e.g., 'msg_abc123')

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with OpenAI

    Example:
        >>> message_id = await add_message_to_thread(
        ...     thread_id="thread_abc123",
        ...     content="Explain this code",
        ...     file_ids=["file-abc123"]
        ... )
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Adding message to thread %s, files: %s", thread_id, len(file_ids) if file_ids else 0)

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            payload = {"role": role, "content": content}

            # Add file attachments if provided
            if file_ids:
                payload["attachments"] = [
                    {"file_id": file_id, "tools": [{"type": "file_search"}]}
                    for file_id in file_ids
                ]

            response = await client.post(
                f"{OPENAI_API_URL}/threads/{thread_id}/messages",
                headers={
                    "Authorization": f"Bearer {effective_api_key}",
                    "Content-Type": "application/json",
                    "OpenAI-Beta": "assistants=v2",
                },
                json=payload,
            )
            response.raise_for_status()

            result = response.json()
            message_id = result.get("id")

            if not message_id:
                logger.error("Invalid response from Messages API: %s", result)
                raise ValueError("Invalid response from OpenAI Messages API")

            logger.info("Message added successfully: %s", message_id)
            return message_id

    except httpx.HTTPError as e:
        logger.error("HTTP error adding message to thread: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error adding message to thread: %s", e)
        raise


async def get_run_messages(
    thread_id: str, api_key: Optional[str] = None, limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Retrieve messages from a thread (typically after a run completes).

    Args:
        thread_id: Thread ID to retrieve messages from
        api_key: API Key (optional, falls back to config)
        limit: Maximum number of messages to retrieve (default: 20)

    Returns:
        List of message objects

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with OpenAI

    Example:
        >>> messages = await get_run_messages("thread_abc123")
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Retrieving messages from thread %s", thread_id)

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            response = await client.get(
                f"{OPENAI_API_URL}/threads/{thread_id}/messages",
                headers={
                    "Authorization": f"Bearer {effective_api_key}",
                    "OpenAI-Beta": "assistants=v2",
                },
                params={"limit": limit},
            )
            response.raise_for_status()

            result = response.json()
            messages = result.get("data", [])

            logger.info("Retrieved %s messages from thread %s", len(messages), thread_id)
            return messages

    except httpx.HTTPError as e:
        logger.error("HTTP error retrieving messages: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error retrieving messages: %s", e)
        raise
