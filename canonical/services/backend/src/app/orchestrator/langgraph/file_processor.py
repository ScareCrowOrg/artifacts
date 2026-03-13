"""
File Attachment Processing Module

Handles processing of attached files based on target LLM capabilities.
Updated to use OpenAI Assistants API for file contextualization.
"""

import logging
import traceback
from pathlib import Path
from typing import Any, Dict, List

from .langgraph_state import OrchestratorState

logger = logging.getLogger(__name__)


async def process_attached_files(state: OrchestratorState) -> OrchestratorState:
    """
    Process attached files based on target LLM.

    Strategy:
    - OpenAI: Upload via Files API → store file_id (for Assistants API)
    - Gemini: Upload via native APIs → store file_uri
    - Ollama: Segment content → store in metadata for prompt inclusion

    Args:
        state: Current orchestrator state

    Returns:
        Updated state with processed file metadata
    """
    attached_files = state.get("attached_files", [])
    target_llm = state.get("target_llm", "").lower()

    if not attached_files or not target_llm:
        return state

    logger.info("Processing %s attached file(s) for %s", len(attached_files), target_llm)

    processed_metadata = []

    for file_info in attached_files:
        file_path = file_info.get("path", "")
        file_type = file_info.get("type", "")

        try:
            if target_llm in ["openai", "gpt"]:
                # Upload to OpenAI Files API for Assistants
                metadata = await _process_openai_file(file_path, file_type)
                processed_metadata.append(metadata)

            elif target_llm in ["gemini", "google"]:
                # Upload to Gemini Files API
                metadata = await _process_gemini_file(file_path, file_type)
                processed_metadata.append(metadata)

            elif target_llm in ["ollama", "local"]:
                # Segment content for direct prompt inclusion
                metadata = _process_ollama_file(file_path, file_type)
                processed_metadata.append(metadata)

            else:
                logger.warning("Unknown target_llm: %s, skipping file processing", target_llm)

        except Exception as e:
            logger.error("Error processing file %s: %s", file_path, e)
            logger.error("Full traceback:\n%s", traceback.format_exc())
            # Continue with other files

    state["attached_files_metadata"] = processed_metadata
    logger.info("Processed %s attached file(s)", len(processed_metadata))

    # Record trace fragment if tracing is enabled
    if state.get("enable_tracing") and state.get("trace_cell_id"):
        await _record_file_upload_fragment(state, attached_files, processed_metadata)

    return state


async def _process_openai_file(file_path: str, file_type: str) -> Dict[str, Any]:
    """
    Process file for OpenAI Assistants API.

    Uploads file to OpenAI Files API and returns file_id.

    Args:
        file_path: Path to the file
        file_type: MIME type of the file

    Returns:
        Metadata dictionary with file_id for OpenAI Assistants API
    """
    from ...services.openai_files_api import upload_file_to_openai_api

    logger.info("Uploading %s to OpenAI Files API for Assistants...", file_path)

    try:
        file_id = await upload_file_to_openai_api(
            file_path=Path(file_path), purpose="assistants"
        )

        logger.info("File uploaded successfully: %s → %s", file_path, file_id)
        return {
            "file_path": file_path,
            "file_type": file_type,
            "strategy": "openai_assistants",
            "file_id": file_id,
        }
    except Exception as e:
        logger.error("Failed to upload file to OpenAI: %s", e)
        logger.error("Full traceback:\n%s", traceback.format_exc())
        # Return metadata without file_id
        return {
            "file_path": file_path,
            "file_type": file_type,
            "strategy": "openai_assistants",
            "file_id": None,
            "error": str(e),
        }


async def _process_gemini_file(file_path: str, file_type: str) -> Dict[str, Any]:
    """
    Process file for Gemini API.

    Uploads file to Gemini Files API and returns file URI.

    Args:
        file_path: Path to the file
        file_type: MIME type of the file

    Returns:
        Metadata dictionary with file_uri for Gemini API
    """
    from ...gemini_service import upload_arquivo_gemini

    logger.info("Uploading %s to Gemini Files API...", file_path)

    try:
        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        # Upload to Gemini Files API
        file_uri = await upload_arquivo_gemini(
            file_content=file_content,
            file_name=Path(file_path).name,
            mime_type=file_type or "text/plain",
        )

        logger.info("File uploaded successfully: %s → %s", file_path, file_uri)
        return {
            "file_path": file_path,
            "file_type": file_type,
            "strategy": "gemini_api",
            "file_uri": file_uri,
            "llm_api_file_id": file_uri,  # For compatibility with existing code
        }
    except Exception as e:
        logger.error("Failed to upload file to Gemini: %s", e)
        logger.error("Full traceback:\n%s", traceback.format_exc())
        # Return metadata without file_uri
        return {
            "file_path": file_path,
            "file_type": file_type,
            "strategy": "gemini_api",
            "file_uri": None,
            "llm_api_file_id": None,
            "error": str(e),
        }


def _process_ollama_file(file_path: str, file_type: str) -> Dict[str, Any]:
    """
    Process file for Ollama (local model).

    Segments file content for direct inclusion in prompts.

    Args:
        file_path: Path to the file
        file_type: MIME type of the file

    Returns:
        Metadata dictionary with segmented content
    """
    logger.info("Segmenting %s for Ollama prompt inclusion...", file_path)
    from ...utils.input_processor import segment_file_content

    segments = segment_file_content(Path(file_path), max_segment_size=4000)

    logger.info("Segmented %s into %s segment(s)", file_path, len(segments))
    return {
        "file_path": file_path,
        "file_type": file_type,
        "strategy": "ollama_segmented",
        "segmented_content": segments,
    }


async def _record_file_upload_fragment(
    state: OrchestratorState,
    attached_files: List[Dict[str, Any]],
    processed_metadata: List[Dict[str, Any]],
) -> None:
    """
    Record file upload trace fragment.

    Args:
        state: Current orchestrator state
        attached_files: Original attached files list
        processed_metadata: Processed file metadata
    """
    try:
        from ...services.conversation_trace_service import (
            get_conversation_trace_service,
        )

        trace_service = get_conversation_trace_service()

        # Extract file names and types
        file_names = [
            Path(f.get("path", "")).name for f in attached_files if f.get("path")
        ]
        file_types = [f.get("type", "unknown") for f in attached_files]
        processing_methods = [m.get("strategy", "unknown") for m in processed_metadata]

        await trace_service.record_fragment(
            trace_cell_id=state["trace_cell_id"],
            stage="file_upload",
            data={
                "file_count": len(attached_files),
                "file_names": file_names,
                "file_types": file_types,
                "processing_methods": processing_methods,
                "target_llm": state.get("target_llm"),
            },
            conversation_id=state["conversation_id"],
        )
        logger.info("[ConversationTrace] Recorded file_upload fragment for %s file(s)", len(attached_files))

    except Exception as e:
        logger.error("[ConversationTrace] Error recording file_upload fragment: %s", e)
        # Don't fail the workflow on tracing errors
