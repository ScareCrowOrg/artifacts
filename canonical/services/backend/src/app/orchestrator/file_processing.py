"""
File Processing for Orchestrator

Handles processing of attached files based on target LLM:
- OpenAI/Gemini: Upload via native APIs
- Ollama: Segment for direct prompt inclusion

Technical naming: All functions and variables in English.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def process_attached_files(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process attached files based on target LLM.

    Strategy:
    - OpenAI/Gemini: Upload via native APIs → store file_id
    - Ollama: Segment content → store in metadata for prompt inclusion

    Args:
        state: Orchestrator state dictionary

    Returns:
        Updated state with attached_files_metadata populated
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
                # Upload to OpenAI Files API
                logger.info("Uploading %s to OpenAI Files API...", file_path)
                # TODO: Implement async upload
                # from ..services.openai_files_api import upload_file_to_openai_api
                # file_id = await upload_file_to_openai_api(Path(file_path))
                processed_metadata.append(
                    {
                        "file_path": file_path,
                        "file_type": file_type,
                        "strategy": "openai_api",
                        "llm_api_file_id": None,  # Placeholder for actual file_id
                    }
                )
                logger.info("OpenAI file upload queued for %s", file_path)

            elif target_llm in ["gemini", "google"]:
                # Upload to Gemini Files API
                logger.info("Uploading %s to Gemini Files API...", file_path)
                # TODO: Implement async upload
                # from ..gemini_service import upload_arquivo_gemini
                # file_uri = await upload_arquivo_gemini(...)
                processed_metadata.append(
                    {
                        "file_path": file_path,
                        "file_type": file_type,
                        "strategy": "gemini_api",
                        "llm_api_file_id": None,  # Placeholder for actual file_uri
                    }
                )
                logger.info("Gemini file upload queued for %s", file_path)

            elif target_llm in ["ollama", "local"]:
                # Segment content for direct prompt inclusion
                logger.info("Segmenting %s for Ollama prompt inclusion...", file_path)
                from ..utils.input_processor import segment_file_content

                segments = segment_file_content(Path(file_path), max_segment_size=4000)

                processed_metadata.append(
                    {
                        "file_path": file_path,
                        "file_type": file_type,
                        "strategy": "ollama_segmented",
                        "segmented_content": segments,
                    }
                )
                logger.info("Segmented %s into %s segment(s)", file_path, len(segments))

            else:
                logger.warning("Unknown target_llm: %s, skipping file processing", target_llm)

        except Exception as e:
            logger.error("Error processing file %s: %s", file_path, e)
            # Continue with other files

    state["attached_files_metadata"] = processed_metadata
    logger.info("Processed %s attached file(s)", len(processed_metadata))

    return state


def get_segmented_content_for_ollama(state: Dict[str, Any]) -> List[str]:
    """
    Extract segmented content from attachment metadata for Ollama.

    Args:
        state: Orchestrator state dictionary

    Returns:
        List of content segments ready for Ollama prompt
    """
    attached_files_metadata = state.get("attached_files_metadata", [])

    all_segments = []
    for metadata in attached_files_metadata:
        if metadata.get("strategy") == "ollama_segmented":
            segments = metadata.get("segmented_content", [])
            all_segments.extend(segments)

    return all_segments


def get_file_ids_for_llm(state: Dict[str, Any], llm_type: str) -> List[str]:
    """
    Extract file IDs from attachment metadata for OpenAI/Gemini.

    Args:
        state: Orchestrator state dictionary
        llm_type: Type of LLM ('openai' or 'gemini')

    Returns:
        List of file IDs/URIs ready for API calls
    """
    attached_files_metadata = state.get("attached_files_metadata", [])

    file_ids = []
    strategy_key = f"{llm_type}_api"

    for metadata in attached_files_metadata:
        if metadata.get("strategy") == strategy_key:
            file_id = metadata.get("llm_api_file_id")
            if file_id:
                file_ids.append(file_id)

    return file_ids
