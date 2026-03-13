"""
OpenAI Files API Integration

This module provides integration with OpenAI's Files API for file uploads,
enabling holistic file contextualization for OpenAI models.

Functions:
- upload_file_to_openai_api: Upload files to OpenAI
- delete_file_from_openai_api: Delete files from OpenAI
- list_files_from_openai_api: List uploaded files

Technical naming: All functions and variables in English.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..config import OPENAI_API_KEY, OPENAI_API_URL, OPENAI_TIMEOUT

logger = logging.getLogger(__name__)

# Constants for error message truncation
ERROR_RESPONSE_MAX_LENGTH = 500  # Maximum characters to log from error responses


async def upload_file_to_openai_api(
    file_path: Path, purpose: str = "assistants", api_key: Optional[str] = None
) -> str:
    """
    Upload a file to OpenAI Files API for holistic contextualization.

    Args:
        file_path: Path to the file to upload
        purpose: Purpose of the file upload (default: "assistants")
        api_key: API Key (prioritária sobre config global)

    Returns:
        File ID from OpenAI response (e.g., 'file-abc123')

    Raises:
        ValueError: If API key is not configured or file doesn't exist
        httpx.HTTPError: If there's an error communicating with OpenAI

    Example:
        >>> file_id = await upload_file_to_openai_api(
        ...     Path("documents/guide.pdf"),
        ...     purpose="assistants"
        ... )
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    logger.info(
        "Uploading file '%s' to OpenAI Files API (size: %s bytes, purpose: %s)",
        file_path.name, file_path.stat().st_size, purpose
    )

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            # Read file content
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                data = {"purpose": purpose}

                response = await client.post(
                    f"{OPENAI_API_URL}/files",
                    headers={"Authorization": f"Bearer {effective_api_key}"},
                    files=files,
                    data=data,
                )

                # Log response for debugging
                logger.debug(
                    "OpenAI Files API response - Status: %s, Headers: %s",
                    response.status_code, dict(response.headers)
                )

                response.raise_for_status()

                result = response.json()
                file_id = result.get("id")

                if not file_id:
                    logger.error("Invalid response from Files API: %s", result)
                    raise ValueError("Invalid response from OpenAI Files API")

                logger.info(
                    "File '%s' uploaded successfully: %s (bytes: %s, status: %s)",
                    file_path.name, file_id, result.get('bytes', 'unknown'), result.get('status', 'unknown')
                )
                return file_id

    except httpx.TimeoutException as e:
        logger.error("Timeout uploading file '%s' to OpenAI Files API after %ss: %s", file_path.name, OPENAI_TIMEOUT, e)
        raise
    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP error uploading file '%s' to OpenAI Files API: Status %s, Response: %s",
            file_path.name, e.response.status_code, e.response.text[:ERROR_RESPONSE_MAX_LENGTH]
        )
        raise
    except httpx.HTTPError as e:
        logger.error("HTTP error uploading file '%s': %s", file_path.name, e)
        raise
    except Exception as e:
        logger.error(
            "Unexpected error uploading file '%s' to OpenAI Files API: %s: %s",
            file_path.name, type(e).__name__, e
        )
        logger.exception("Full traceback:")
        raise


async def delete_file_from_openai_api(file_id: str, api_key: Optional[str] = None) -> bool:
    """
    Delete a file from OpenAI Files API.

    Args:
        file_id: File ID to delete
        api_key: API Key (prioritária sobre config global)

    Returns:
        True if deletion was successful, False otherwise

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with OpenAI

    Example:
        >>> success = await delete_file_from_openai_api("file-abc123")
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Deleting file '%s' from OpenAI Files API", file_id)

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            response = await client.delete(
                f"{OPENAI_API_URL}/files/{file_id}",
                headers={"Authorization": f"Bearer {effective_api_key}"},
            )
            response.raise_for_status()

            result = response.json()
            deleted = result.get("deleted", False)

            if deleted:
                logger.info("File '%s' deleted successfully", file_id)
            else:
                logger.warning("File '%s' deletion returned False", file_id)

            return deleted

    except httpx.HTTPError as e:
        logger.error("HTTP error deleting file from OpenAI Files API: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error deleting file from OpenAI Files API: %s", e)
        raise


async def list_files_from_openai_api(
    purpose: Optional[str] = None, api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List files from OpenAI Files API.

    Args:
        purpose: Filter by purpose (optional)
        api_key: API Key (prioritária sobre config global)

    Returns:
        List of file objects from OpenAI

    Raises:
        ValueError: If API key is not configured
        httpx.HTTPError: If there's an error communicating with OpenAI

    Example:
        >>> files = await list_files_from_openai_api(purpose="assistants")
    """
    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info("Listing files from OpenAI Files API")

    try:
        async with httpx.AsyncClient(timeout=OPENAI_TIMEOUT) as client:
            params = {}
            if purpose:
                params["purpose"] = purpose

            response = await client.get(
                f"{OPENAI_API_URL}/files",
                headers={"Authorization": f"Bearer {effective_api_key}"},
                params=params,
            )
            response.raise_for_status()

            result = response.json()
            files = result.get("data", [])

            logger.info("Retrieved %s files from OpenAI Files API", len(files))
            return files

    except httpx.HTTPError as e:
        logger.error("HTTP error listing files from OpenAI Files API: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error listing files from OpenAI Files API: %s", e)
        raise
