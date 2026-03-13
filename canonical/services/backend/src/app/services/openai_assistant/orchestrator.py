"""
OpenAI Assistant Orchestrator Module

High-level orchestration function for complete assistant conversation flow.

Functions:
- process_with_assistant: Complete flow for processing a message with OpenAI Assistants API

Technical naming: All functions and variables in English.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from ...config import OPENAI_API_KEY, OPENAI_DEFAULT_MODEL
from .assistant_manager import create_or_get_assistant
from .file_validator import get_file_info, validate_file_for_upload
from .message_manager import add_message_to_thread, get_run_messages
from .run_manager import run_assistant
from .thread_manager import create_thread

logger = logging.getLogger(__name__)


async def process_with_assistant(
    user_message: str,
    thread_id: Optional[str] = None,
    assistant_id: Optional[str] = None,
    file_paths: Optional[List[Path]] = None,
    system_instructions: Optional[str] = None,
    model: str = OPENAI_DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> Tuple[str, str, str]:
    """
    High-level function to process a message with OpenAI Assistants API.

    This function orchestrates the complete flow:
    1. Upload files (if provided) to get file_ids
    2. Create/retrieve assistant
    3. Create/retrieve thread
    4. Add message to thread with file attachments
    5. Run assistant and wait for completion
    6. Extract and return response

    Args:
        user_message: User's message/question
        thread_id: Existing thread ID (optional, creates new if not provided)
        assistant_id: Existing assistant ID (optional, creates new if not provided)
        file_paths: List of file paths to attach (optional)
        system_instructions: System instructions for assistant (optional)
        model: Model to use (default: from config)
        api_key: API Key (optional, falls back to config)

    Returns:
        Tuple of (response_text, thread_id, assistant_id)

    Raises:
        ValueError: If API key is not configured
        RuntimeError: For errors during processing

    Example:
        >>> response, thread_id, asst_id = await process_with_assistant(
        ...     user_message="Explain this code",
        ...     file_paths=[Path("main.py")],
        ...     system_instructions="You are a helpful code assistant.",
        ...     api_key="sk-..."
        ... )
    """
    from ..openai_files_api import upload_file_to_openai_api

    effective_api_key = api_key or OPENAI_API_KEY

    if not effective_api_key:
        raise ValueError(
            "OpenAI API Key não configurada. Configure OPENAI_API_KEY no .env ou "
            "forneça uma chave específica no modelo IA."
        )

    logger.info(
        "Processing with assistant - Files: %s, Thread: %s, Assistant: %s",
        len(file_paths) if file_paths else 0, thread_id or 'new', assistant_id or 'new'
    )

    try:
        # Step 1: Upload files if provided
        file_ids = []
        if file_paths:
            logger.info("Uploading %s file(s) to OpenAI Files API", len(file_paths))

            for file_path in file_paths:
                try:
                    # Validate file before upload
                    is_valid, error_msg, mime_type = validate_file_for_upload(
                        file_path=file_path, purpose="assistants"
                    )

                    if not is_valid:
                        logger.error("File validation failed for %s: %s", file_path.name, error_msg)
                        # Log detailed file info for diagnostics
                        file_info = get_file_info(file_path)
                        logger.info("File info for %s: %s", file_path.name, file_info)
                        continue  # Skip this file

                    logger.info(
                        "Uploading %s (MIME: %s, size: %s bytes)",
                        file_path.name, mime_type, file_path.stat().st_size
                    )

                    file_id = await upload_file_to_openai_api(
                        file_path=file_path,
                        purpose="assistants",
                        api_key=effective_api_key,
                    )
                    file_ids.append(file_id)
                    logger.info("File uploaded successfully: %s → %s", file_path.name, file_id)
                except Exception as e:
                    logger.error("Failed to upload file %s: %s", file_path, e)
                    # Log full exception for debugging
                    logger.exception("Full traceback for upload failure of %s:", file_path.name)
                    # Continue with other files

        # Step 2: Create or use existing assistant
        if not assistant_id:
            default_instructions = system_instructions or (
                "You are a helpful AI assistant for the ScareVerse project. "
                "You help with code analysis, documentation, and technical questions. "
                "Use the provided files to give accurate and contextual responses."
            )

            # Enable file_search tool if files are attached
            tools = None
            if file_ids:
                tools = [{"type": "file_search"}]

            assistant_id = await create_or_get_assistant(
                name="ScareVerse Assistant",
                instructions=default_instructions,
                model=model,
                tools=tools,
                api_key=effective_api_key,
            )

        # Step 3: Create or use existing thread
        if not thread_id:
            thread_id = await create_thread(api_key=effective_api_key)

        # Step 4: Add message to thread with file attachments
        message_id = await add_message_to_thread(
            thread_id=thread_id,
            content=user_message,
            role="user",
            file_ids=file_ids if file_ids else None,
            api_key=effective_api_key,
        )
        logger.info("Message added to thread: %s", message_id)

        # Step 5: Run assistant
        run_result = await run_assistant(
            thread_id=thread_id, assistant_id=assistant_id, api_key=effective_api_key
        )

        if run_result["status"] != "completed":
            logger.warning("Run finished with status: %s", run_result['status'])
            if run_result.get("last_error"):
                error_msg = run_result["last_error"].get("message", "Unknown error")
                raise RuntimeError(f"Assistant run failed: {error_msg}")

        # Step 6: Get messages and extract response
        messages = await get_run_messages(
            thread_id=thread_id, api_key=effective_api_key, limit=10
        )

        # Extract assistant's response (most recent assistant message)
        assistant_response = ""
        for msg in messages:
            if msg.get("role") == "assistant":
                # Extract text content
                content_blocks = msg.get("content", [])
                for block in content_blocks:
                    if block.get("type") == "text":
                        # Safely extract text value with type checking
                        text_field = block.get("text", {})
                        if isinstance(text_field, dict):
                            text = text_field.get("value", "")
                        elif isinstance(text_field, str):
                            # Handle case where text is already a string
                            text = text_field
                        else:
                            logger.warning("Unexpected text field type: %s", type(text_field))
                            text = ""

                        if text:
                            assistant_response = text
                            break
                if assistant_response:
                    break

        if not assistant_response:
            logger.warning("No assistant response found in messages")
            assistant_response = "Não foi possível obter uma resposta do assistente."

        logger.info("Assistant processing completed successfully")
        return assistant_response, thread_id, assistant_id

    except Exception as e:
        logger.error("Error processing with assistant: %s", e)
        raise RuntimeError(f"Erro ao processar com assistente: {e}") from e
