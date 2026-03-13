"""
Chat IA API Router - RESTful endpoints for ScareVerse AI chat integration.

Implements chat processing with LangChain/LangGraph orchestration.
"""

from fastapi import APIRouter, HTTPException, status, Depends
import logging
import traceback

from ..models import (
    User,
    NotebookItemType,
    AIModel,
    ProcessChatIntentRequest,
    ProcessChatIntentResponse,
)
from ..database import db
from ..auth import get_current_user_required
from ..config import OLLAMA_MODELS, GEMINI_MODELS, OPENAI_MODELS

logger = logging.getLogger(__name__)

# Create chat router
chat_router = APIRouter(prefix="/chat", tags=["Chat IA"])


@chat_router.post("/processar", response_model=ProcessChatIntentResponse)
async def processar_intencao_chat(
    request: ProcessChatIntentRequest, current_user: User = Depends(get_current_user_required)
):
    """
    Process user intent via AI chat with LangChain + LangGraph orchestration.

    CRITICAL: RAG (Retrieval-Augmented Generation) is ONLY executed when collections
    are EXPLICITLY selected by the user via 'selected_collections' field.
    If 'selected_collections' is None, empty [], or omitted, RAG is DISABLED.
    NO fallback to "all collections" will occur.

    This endpoint uses LangGraph to orchestrate the interaction:
    1. Classifies message intent (chat, create, execute, reflect, debug)
    2. Executes necessary actions using LangChain Tools
    3. Generates contextualized response or calls LLM if needed
    4. Returns response and created cell data (if applicable)

    LangGraph flow:
    - ReceiveInstruction -> ClassifyIntent
    - ClassifyIntent -> ExecuteAction (if needed) or ReturnResponse
    - ExecuteAction -> ReturnResponse
    - ReturnResponse -> END

    Formato do histórico esperado:
    - Lista de mensagens com 'role' (user/assistant) e 'content'
    - As últimas 5 mensagens são mantidas completas
    - Mensagens anteriores são minificadas para economizar tokens

    Exemplo de request body (SEM RAG - padrão):
    ```json
    {
        "purpose": "Criar uma célula para sistema de login",
        "model": "mistral",
        "history": [
            {"role": "user", "content": "Olá"},
            {"role": "assistant", "content": "Olá! Como posso ajudar?"}
        ]
    }
    ```

    Note: `assignee_id` is optional and deprecated. The API uses the authenticated user from JWT token.

    Exemplo de request body (COM RAG - coleções explícitas):
    ```json
    {
        "purpose": "Explique a arquitetura do projeto",
        "model": "mistral",
        "selected_collections": ["scareverse_docs", "scareverse_code"],
        "history": []
    }
    ```

    Exemplo de request body (COM TRACING - observabilidade de pipeline):
    ```json
    {
        "purpose": "Debug this RAG query",
        "model": "mistral",
        "selected_collections": ["scareverse_docs"],
        "enable_tracing": true,
        "history": []
    }
    ```
    """
    try:
        # [TRACE] Request entry log
        logger.info("[TRACE] /api/chat/processar - Request received: purpose=%s, model=%s, attachments=%s, history=%s, classify_intent=%s, thread_id=%s, assistant_id=%s, conversation_id=%s", request.purpose, request.model, len(request.attachments) if request.attachments else 0, len(request.history) if request.history else 0, request.classify_intent, request.thread_id, request.assistant_id, request.conversation_id)
        logger.info("Processing chat intent with LangGraph: %s...", request.purpose[:50])

        # Log to verify use_rag value
        logger.info("[TRACE] use_rag value received: %s", request.use_rag)

        # [CONV_ID] Enhanced conversation_id inspection
        logger.info("[CONV_ID] Request received - Payload inspection:")
        logger.info("[CONV_ID]   - request.dict() keys: %s", list(request.dict().keys()))
        logger.info("[CONV_ID]   - 'conversation_id' in dict: %s", 'conversation_id' in request.dict())
        logger.info("[CONV_ID]   - hasattr conversation_id: %s", hasattr(request, 'conversation_id'))
        logger.info("[CONV_ID]   - conversation_id value: %s", getattr(request, 'conversation_id', 'ATTR_NOT_FOUND'))
        logger.info("[CONV_ID]   - conversation_id type: %s", type(getattr(request, 'conversation_id', None)))

        # [TRACE] Log conversation_id for debugging session tracking
        if request.conversation_id:
            logger.info("[CONV_ID] ✓ conversation_id present: %s", request.conversation_id)
        else:
            logger.warning("[CONV_ID] ✗ conversation_id is None/empty - InterpreterProvider will use 'default-session'")

        # Use current authenticated user as the responsible user
        user = current_user
        assignee_id = user.id
        # [TRACE] Log after user authentication
        logger.info("[TRACE] Authenticated user: id=%s, name=%s", user.id, getattr(user, 'nome', None))

        # Verify the user still exists in database
        try:
            if not await db.find_one("users", assignee_id, current_user=current_user, model_class=User):
                logger.info("[TRACE] use_rag value in user check: %s", request.use_rag)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Authenticated user not found in database",
                )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        # Get available cell types (using NotebookItemType)
        try:
            notebook_item_types = await db.find_many(
                "notebook_item_types",
                current_user=current_user,
                model_class=NotebookItemType,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

        if not notebook_item_types:
            logger.info("[TRACE] use_rag value in notebook_item_types check: %s", request.use_rag)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No notebook item types available. Run /seed-data first.",
            )

        # Validate model against registered artifacts
        model = request.model or "mistral"

        # Get available models from database
        try:
            available_models = await db.find_many(
                "ai_models",
                current_user=current_user,
                model_class=AIModel,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        active_models = [m for m in available_models if m.active]

        # Check if the requested model exists and is active
        found_model = None
        for m in active_models:
            if m.modelId.lower() == model.lower():
                found_model = m
                break

        if not found_model:
            # Fallback to .env arrays if database is empty or model not found
            model_lower = model.lower()

            if (
                model_lower not in OLLAMA_MODELS
                and model_lower not in GEMINI_MODELS
                and model_lower not in OPENAI_MODELS
            ):
                # Build readable list of available models
                if active_models:
                    model_names = [f"{m.name} ({m.modelId})" for m in active_models]
                else:
                    model_names = [
                        f"Ollama: {', '.join(OLLAMA_MODELS)}",
                        f"Gemini: {', '.join(GEMINI_MODELS)}",
                        f"OpenAI: {', '.join(OPENAI_MODELS)}",
                    ]

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Model '{model}' not found or inactive. Available models: {', '.join(model_names)}",
                )

        # Use the validated model
        validated_model = found_model.modelId if found_model else model
        model_lower = model.lower()
        if found_model:
            model_provider = found_model.provider
        elif model_lower in OLLAMA_MODELS:
            model_provider = "ollama"
        elif model_lower in GEMINI_MODELS:
            model_provider = "gemini"
        elif model_lower in OPENAI_MODELS:
            model_provider = "openai"
        else:
            model_provider = "ollama"  # fallback
        model_api_key = found_model.apiKey if found_model else None
        # [TRACE] Log after model validation
        logger.info(
            "[TRACE] Model validated: id=%s, provider=%s, api_key=%s",
            validated_model, model_provider, '***' if model_api_key else None
        )

        # Convert history to dict format
        historico_dicts = []
        if request.history:
            historico_dicts = [
                {"role": msg.role, "content": msg.content} for msg in request.history
            ]
        # [TRACE] Log after history conversion
        logger.info("[TRACE] History converted: %s", historico_dicts[-2:] if historico_dicts else historico_dicts)

        # Process attachments using Files API for Gemini
        intencao_completa = request.purpose
        file_uris = []
        if request.attachments and len(request.attachments) > 0:
            # [TRACE] Log when processing attachments
            logger.info(
                "[TRACE] Processing attachments: total=%s, names=%s",
                len(request.attachments), [a.name for a in request.attachments]
            )
            # For Gemini provider, use Files API instead of raw injection
            if model_provider == "gemini":
                from app.gemini_service import upload_arquivo_gemini

                for anexo in request.attachments:
                    try:
                        file_uri = await upload_arquivo_gemini(
                            file_content=anexo.content,
                            file_name=anexo.name,
                            mime_type="text/plain",
                            api_key=model_api_key,
                        )
                        file_uris.append(file_uri)
                        logger.info("Anexo '%s' enviado para Files API: %s", anexo.name, file_uri)
                    except Exception as e:
                        logger.warning("Erro ao enviar anexo '%s' para Files API: %s", anexo.name, e)
            else:
                # For non-Gemini providers, append to intention (legacy mode)
                intencao_completa += "\n\n---\n📎 Anexos:\n"
                for idx, anexo in enumerate(request.attachments, 1):
                    intencao_completa += f"\n[Anexo {idx}: {anexo.name}]\n{anexo.content}\n"

        # Initialize tracking for OpenAI Assistants API (thread_id, assistant_id)
        openai_thread_id = request.thread_id
        openai_assistant_id = request.assistant_id

        # Initialize conversation_id (will be set by orchestrator if tracing is enabled)
        conversation_id = None

        # Check if intention classification is enabled
        if not request.classify_intent:
            # Direct conversation mode - skip orchestrator and go straight to LLM with RAG
            logger.info("Intent classification disabled - direct conversation mode with RAG")

            try:
                # Import the polymorphic LLM provider factory
                from ..services.llm_provider_factory import LLMProviderFactory
                from pathlib import Path
                import tempfile

                # Get provider instance using the factory
                llm_provider = LLMProviderFactory.get_provider(
                    provider_name=model_provider, model_id=validated_model, api_key=model_api_key
                )

                logger.info("Using %s provider with model %s", llm_provider.provider_name, llm_provider.model_name)

                # Prepare attached_content_metadata based on provider type
                attached_content_metadata = None
                temp_files = []

                if request.attachments and len(request.attachments) > 0:
                    if model_provider == "ollama":
                        # Ollama expects segmented_content format
                        attached_content_metadata = [
                            {
                                "type": "segmented_content",
                                "content": [anexo.content for anexo in request.attachments],
                            }
                        ]
                        logger.info(
                            "Prepared %s attachment(s) for Ollama (segmented_content)",
                            len(request.attachments)
                        )

                    elif model_provider == "gemini":
                        # Gemini expects file URIs from Files API (already prepared earlier)
                        if file_uris:
                            attached_content_metadata = [
                                {"type": "file_uri", "uri": uri} for uri in file_uris
                            ]
                            logger.info("Prepared %s file URI(s) for Gemini", len(file_uris))

                    elif model_provider == "openai":
                        # OpenAI expects file paths for Assistants API
                        attached_content_metadata = []
                        for anexo in request.attachments:
                            try:
                                # Create temp file with proper extension
                                suffix = Path(anexo.name).suffix or ".txt"
                                temp_file = tempfile.NamedTemporaryFile(
                                    mode="w", suffix=suffix, delete=False, encoding="utf-8"
                                )
                                temp_file.write(anexo.content)
                                temp_file.close()
                                temp_files.append(temp_file.name)
                                attached_content_metadata.append(
                                    {
                                        "type": "file_path",
                                        "path": temp_file.name,
                                        "mime_type": anexo.type or "text/plain",
                                    }
                                )
                            except Exception as e:
                                logger.warning("Failed to create temp file for %s: %s", anexo.name, e)
                        logger.info("Prepared %s file(s) for OpenAI Assistants API", len(attached_content_metadata))

                # Extract system_prompt if configured in model
                system_prompt = (
                    found_model.configuration.get("system_prompt")
                    if found_model and found_model.configuration
                    else None
                )

                # Call the provider's process_chat method (polymorphic dispatch)
                try:
                    # Only use RAG if collections are explicitly selected
                    # RAG is disabled when selected_collections is None, empty [], or omitted
                    should_use_rag = bool(request.selected_collections)

                    result = await llm_provider.process_chat(
                        user_message=request.purpose,
                        conversation_history=historico_dicts,
                        attached_content_metadata=attached_content_metadata,
                        system_instructions=system_prompt,
                        use_rag=should_use_rag,
                        selected_collections=request.selected_collections,
                        thread_id=request.thread_id if model_provider == "openai" else None,
                        assistant_id=request.assistant_id if model_provider == "openai" else None,
                        conversation_id=request.conversation_id,
                    )

                    resposta_base = result["response"]

                    # Extract OpenAI-specific data if available
                    if model_provider == "openai":
                        openai_thread_id = result.get("thread_id")
                        openai_assistant_id = result.get("assistant_id")
                        logger.info("Resposta do %s (%s), thread=%s..., RAG: %s, collections: %s", model_provider, validated_model, openai_thread_id[:12] if openai_thread_id else 'N/A', should_use_rag, request.selected_collections or 'none')
                    else:
                        logger.info(
                            "Resposta do %s (%s), RAG: %s, collections: %s",
                            model_provider, validated_model, should_use_rag, request.selected_collections or 'none'
                        )

                finally:
                    # NOTE: Temporary files are NOT deleted to allow prolonged use.
                    # - OpenAI: Local temp files need to persist for Assistants API
                    # - Gemini: Files managed by Google's Files API, no local cleanup needed
                    # - Ollama: No temp files created (uses content directly)
                    if temp_files:
                        logger.info(
                            "Keeping %s temporary file(s) for prolonged use by %s",
                            len(temp_files), model_provider
                        )

            except Exception as e:
                logger.error("Erro ao processar resposta direta: %s", e)
                logger.error("Full traceback:\n%s", traceback.format_exc())
                resposta_base = f"Desculpe, não consegui processar sua mensagem. Erro: {str(e)}"

            # No cell creation in direct conversation mode
            intencao_classificada = "conversar"
            celula_criada = None

        else:
            # Use LangGraph orchestrator to process the message with intention classification
            logger.info("Intent classification enabled - using orchestrator")

            from ..orchestrator.langgraph import get_orchestrator

            # Prepare attached files for orchestrator processing
            attached_files_for_orchestrator = None
            if request.attachments and len(request.attachments) > 0:
                # Create temporary files for orchestrator processing
                import tempfile

                attached_files_for_orchestrator = []
                temp_files_orchestrator = []
                for anexo in request.attachments:
                    try:
                        suffix = Path(anexo.name).suffix or ".txt"
                        temp_file = tempfile.NamedTemporaryFile(
                            mode="w", suffix=suffix, delete=False, encoding="utf-8"
                        )
                        temp_file.write(anexo.content)
                        temp_file.close()
                        temp_files_orchestrator.append(temp_file.name)
                        attached_files_for_orchestrator.append(
                            {"path": temp_file.name, "type": anexo.type or "text/plain"}
                        )
                    except Exception as e:
                        logger.warning("Failed to create temp file for %s: %s", anexo.name, e)

                logger.info("Orchestrator: %s file(s) prepared", len(attached_files_for_orchestrator))

            orchestrator = get_orchestrator()
            resultado = await orchestrator.process(
                mensagem=intencao_completa,
                responsavel_id=assignee_id,  # Note: orchestrator API uses 'responsavel_id' (legacy naming preserved for compatibility)
                modelo=validated_model,
                historico=historico_dicts,
                use_rag=request.use_rag,
                attached_files=attached_files_for_orchestrator,
                target_llm=model_provider,
                enable_tracing=request.enable_tracing,
            )

            # NOTE: Temporary files for orchestrator are NOT deleted to allow prolonged use
            # The orchestrator may need to access these files multiple times
            if "temp_files_orchestrator" in locals() and temp_files_orchestrator:
                logger.info("Keeping %s orchestrator file(s) for prolonged use", len(temp_files_orchestrator))

            resposta_base = resultado["resposta"]
            intencao_classificada = resultado.get("intencao")
            celula_criada = resultado.get("celula")
            conversation_id = resultado.get("conversation_id")

            # Log to verify use_rag value at decision points
            if model_provider == "ollama":
                logger.info("[TRACE] model_provider=ollama decision with use_rag=%s", request.use_rag)

            elif model_provider == "openai":
                logger.info("[TRACE] model_provider=openai decision with use_rag=%s", request.use_rag)

            if request.attachments and len(request.attachments) > 0:
                logger.info("[TRACE] Attachments present decision with use_rag=%s", request.use_rag)
            else:
                logger.info("[TRACE] No attachments decision with use_rag=%s", request.use_rag)

            # Orchestrator now handles RAG and file processing internally
            # No need for separate LLM enhancement here
            logger.info("Orchestrator processed message with intention: %s", intencao_classificada)

        logger.info("Intenção processada: %s", intencao_classificada)

        return ProcessChatIntentResponse(
            response=resposta_base,
            cell=celula_criada,
            thread_id=openai_thread_id if model_provider == "openai" else None,
            assistant_id=openai_assistant_id if model_provider == "openai" else None,
            conversation_id=conversation_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing chat intent: %s", e)
        logger.error("Full traceback:\n%s", traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing intent: {str(e)}",
        )
