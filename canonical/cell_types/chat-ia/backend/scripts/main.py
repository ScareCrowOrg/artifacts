"""
Chat IA Cell - Backend Script for execute-ephemeral Pattern

This script executes the Chat IA cell via the /api/cells/execute-ephemeral endpoint.
It reuses the logic from the chat_router.py instead of duplicating code.

Architecture:
- Accepts cell_data from execute-ephemeral
- Validates input and normalizes parameters
- Routes to either direct LLM or orchestrator based on intention classification
- Returns standardized response format
"""

import asyncio
import logging
import traceback
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


async def execute_cell(cell_data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute the Chat IA cell via /api/cells/execute-ephemeral pattern.

    Args:
        cell_data: Cell execution payload containing:
            - prompt (str): User message/intention
            - model (str): AI model to use (e.g., "gpt-4", "ollama/mistral", "gemini")
            - selectedModel (str, optional): Alias for model parameter
            - selectedCollections (List[str], optional): RAG collections to search
            - systemPrompt (str, optional): Custom system prompt
            - enableIntentionClassification (bool, optional): Enable intent classification
            - history (List[Dict], optional): Conversation history
            - attachments (List[Dict], optional): File attachments
            - conversation_id (str, optional): Conversation session ID
            - thread_id (str, optional): OpenAI Assistants thread ID
            - assistant_id (str, optional): OpenAI Assistants assistant ID

        user_id: Authenticated user ID from JWT token (provided by execute-ephemeral middleware)

    Returns:
        Dict with structure:
        {
            "success": True/False,
            "output": {
                "response": str,  # AI response text
                "model_used": str,  # Model that was used
                "conversation_id": str,  # Session ID (if tracing enabled)
                "cell": Dict,  # Created cell (if applicable)
                "thread_id": str,  # OpenAI thread ID (if applicable)
                "assistant_id": str,  # OpenAI assistant ID (if applicable)
            },
            "error": str  # Error message (if success=False)
        }

    Example:
    ```python
    result = await execute_cell({
        "prompt": "Create a cell to calculate fibonacci",
        "model": "gpt-4",
        "enableIntentionClassification": True,
        "history": [],
        "selectedCollections": ["docs"],
        "conversation_id": "conv-123"
    }, user_id="user-456")

    print(result)
    # {
    #     "success": True,
    #     "output": {
    #         "response": "I'll create a fibonacci cell for you...",
    #         "model_used": "gpt-4",
    #         "conversation_id": "conv-123",
    #         "cell": {...},  # If a cell was created
    #         "thread_id": None,
    #         "assistant_id": None
    #     }
    # }
    ```
    """
    start_time = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
    temp_files = []

    try:
        # ============== STEP 1: Normalize Input ==============
        prompt = cell_data.get("prompt", "").strip()
        model = cell_data.get("model") or cell_data.get("selectedModel") or "gpt-4"
        enable_classification = cell_data.get("enableIntentionClassification", False)
        selected_collections = cell_data.get("selectedCollections") or []
        system_prompt = cell_data.get("systemPrompt", "")
        history = cell_data.get("history") or []
        attachments = cell_data.get("attachments") or []
        conversation_id = cell_data.get("conversation_id")
        thread_id = cell_data.get("thread_id")
        assistant_id = cell_data.get("assistant_id")

        # ============== STEP 2: Validate Input ==============
        if not prompt:
            return {
                "success": False,
                "output": {},
                "error": "prompt is required and cannot be empty"
            }

        if not model:
            return {
                "success": False,
                "output": {},
                "error": "model is required"
            }

        logger.info(
            "[Chat-IA] Execute cell: prompt=%s..., model=%s, classification=%s, user=%s",
            prompt[:50], model, enable_classification, user_id
        )

        # ============== STEP 3: Determine Model Provider ==============
        from backend.app.config import OLLAMA_MODELS, GEMINI_MODELS, OPENAI_MODELS

        model_lower = model.lower()
        if model_lower in OLLAMA_MODELS:
            model_provider = "ollama"
        elif model_lower in GEMINI_MODELS:
            model_provider = "gemini"
        elif model_lower in OPENAI_MODELS:
            model_provider = "openai"
        else:
            # Try to detect from model string (e.g., "ollama/mistral" → ollama)
            if "/" in model:
                provider_prefix = model.split("/")[0].lower()
                if provider_prefix in ["ollama", "gemini", "openai"]:
                    model_provider = provider_prefix
                else:
                    model_provider = "ollama"  # fallback
            else:
                model_provider = "ollama"  # default fallback

        logger.info("[Chat-IA] Model provider: %s", model_provider)

        # ============== STEP 4: Process Attachments ==============
        attachment_metadata = []
        if attachments:
            logger.info("[Chat-IA] Processing %d attachment(s)", len(attachments))

            if model_provider == "ollama":
                # Ollama expects segmented_content format
                attachment_metadata = [
                    {
                        "type": "segmented_content",
                        "content": [a.get("content") for a in attachments if a.get("content")],
                    }
                ]

            elif model_provider == "gemini":
                # Gemini would use Files API (simplified here)
                attachment_metadata = [
                    {
                        "type": "file_uri",
                        "name": a.get("name", "attachment"),
                        "content": a.get("content", "")
                    }
                    for a in attachments
                ]

            elif model_provider == "openai":
                # OpenAI Assistants expects file paths
                for attachment in attachments:
                    try:
                        suffix = Path(attachment.get("name", "file.txt")).suffix or ".txt"
                        temp_file = tempfile.NamedTemporaryFile(
                            mode="w",
                            suffix=suffix,
                            delete=False,
                            encoding="utf-8"
                        )
                        temp_file.write(attachment.get("content", ""))
                        temp_file.close()
                        temp_files.append(temp_file.name)

                        attachment_metadata.append({
                            "type": "file_path",
                            "path": temp_file.name,
                            "name": attachment.get("name", "file.txt"),
                            "mime_type": attachment.get("type", "text/plain")
                        })
                    except Exception as e:
                        logger.warning("[Chat-IA] Failed to create temp file: %s", e)

        # ============== STEP 5: Process Based on Classification Setting ==============
        response_text = None
        created_cell = None
        output_thread_id = None
        output_assistant_id = None

        if not enable_classification:
            # ========== Direct LLM Mode (No Intent Classification) ==========
            logger.info("[Chat-IA] Direct LLM mode (no intent classification)")

            try:
                from backend.app.services.llm_provider_factory import LLMProviderFactory

                # Get LLM provider instance
                llm_provider = LLMProviderFactory.get_provider(
                    provider_name=model_provider,
                    model_id=model,
                    api_key=None  # API key would be in environment or model config
                )

                logger.info("[Chat-IA] Using %s provider", llm_provider.provider_name)

                # Convert history format
                history_dicts = [
                    {"role": msg.get("role"), "content": msg.get("content")}
                    for msg in history
                    if msg.get("role") and msg.get("content")
                ]

                # Call LLM provider
                should_use_rag = bool(selected_collections)
                result = await llm_provider.process_chat(
                    user_message=prompt,
                    conversation_history=history_dicts,
                    attached_content_metadata=attachment_metadata if attachment_metadata else None,
                    system_instructions=system_prompt or None,
                    use_rag=should_use_rag,
                    selected_collections=selected_collections,
                    thread_id=thread_id if model_provider == "openai" else None,
                    assistant_id=assistant_id if model_provider == "openai" else None,
                    conversation_id=conversation_id,
                )

                response_text = result.get("response", "")

                # Extract OpenAI-specific IDs if applicable
                if model_provider == "openai":
                    output_thread_id = result.get("thread_id")
                    output_assistant_id = result.get("assistant_id")

                logger.info("[Chat-IA] LLM response received (%d chars)", len(response_text))

            except Exception as e:
                logger.error("[Chat-IA] LLM processing failed: %s", e)
                logger.error("[Chat-IA] Traceback: %s", traceback.format_exc())
                return {
                    "success": False,
                    "output": {},
                    "error": f"LLM processing failed: {str(e)}"
                }

        else:
            # ========== Orchestrator Mode (Intent Classification Enabled) ==========
            logger.info("[Chat-IA] Orchestrator mode (intent classification enabled)")

            try:
                from backend.app.orchestrator.langgraph import get_orchestrator

                orchestrator = get_orchestrator()

                # Prepare files for orchestrator
                orchestrator_files = None
                if attachments:
                    orchestrator_files = [
                        {
                            "path": temp_file,
                            "type": a.get("type", "text/plain")
                        }
                        for temp_file, a in zip(temp_files, attachments)
                    ]

                # Call orchestrator
                result = await orchestrator.process(
                    mensagem=prompt,
                    responsavel_id=user_id or "system",
                    modelo=model,
                    historico=history,
                    use_rag=bool(selected_collections),
                    attached_files=orchestrator_files,
                    target_llm=model_provider,
                    enable_tracing=cell_data.get("enableTracing", False),
                )

                response_text = result.get("resposta", "")
                created_cell = result.get("celula")
                conversation_id = result.get("conversation_id")

                logger.info(
                    "[Chat-IA] Orchestrator response received, intention=%s, cell_created=%s",
                    result.get("intencao"),
                    bool(created_cell)
                )

            except Exception as e:
                logger.error("[Chat-IA] Orchestrator processing failed: %s", e)
                logger.error("[Chat-IA] Traceback: %s", traceback.format_exc())
                return {
                    "success": False,
                    "output": {},
                    "error": f"Orchestrator processing failed: {str(e)}"
                }

        # ============== STEP 6: Build Response ==============
        if not response_text:
            return {
                "success": False,
                "output": {},
                "error": "No response generated from LLM"
            }

        return {
            "success": True,
            "output": {
                "response": response_text,
                "model_used": model,
                "conversation_id": conversation_id,
                "cell": created_cell,
                "thread_id": output_thread_id,
                "assistant_id": output_assistant_id,
            }
        }

    except Exception as e:
        logger.error("[Chat-IA] Unexpected error: %s", e)
        logger.error("[Chat-IA] Traceback: %s", traceback.format_exc())
        return {
            "success": False,
            "output": {},
            "error": f"Unexpected error: {str(e)}"
        }

    finally:
        # Note: Temporary files are NOT deleted here to allow prolonged use
        # by async providers (OpenAI Assistants API, etc.)
        if temp_files:
            logger.info("[Chat-IA] Keeping %d temporary file(s) for prolonged use", len(temp_files))


# ============== CLI Testing ==============
if __name__ == "__main__":
    import json
    import sys

    # Example usage for testing
    test_data = {
        "prompt": "Hello! How are you today?",
        "model": "gpt-4",
        "selectedModel": None,
        "enableIntentionClassification": False,
        "selectedCollections": [],
        "systemPrompt": "",
        "history": [],
        "attachments": [],
        "conversation_id": None,
        "thread_id": None,
        "assistant_id": None,
    }

    # Override with CLI args if provided
    if len(sys.argv) > 1:
        try:
            test_data = json.loads(sys.argv[1])
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            sys.exit(1)

    # Run the cell execution
    result = asyncio.run(execute_cell(test_data, user_id="test-user"))

    # Print result as formatted JSON
    print(json.dumps(result, indent=2))
