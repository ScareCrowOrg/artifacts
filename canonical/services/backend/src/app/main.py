"""
Main FastAPI application for ScareCopilotPortal backend.

This is the staging backend that provides file operations and directory
tree management for the Cockpit Extension.
"""

import logging

# Configure logging with explicit stderr handler
import sys
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import (
    API_PREFIX,
    API_VERSION,
    CORS_ORIGINS,
    DEBUG,
    LOG_LEVEL,
    SCAREFERA_LAB_DIR,
)
from .routers.action_discovery_router import action_discovery_router
from .routers.agent_router import router as agent_router
from .routers.agent_websocket_router import router as agent_websocket_router
from .routers.ai_models_router import ai_models_router
from .routers.artifacts_router import (
    router as artifacts_router,  # Artifacts discovery (from ScareRunner integration)
)
from .routers.audit_router import audit_router
from .routers.books_router import books_router
from .routers.cells_router import cells_router

# sessions_router REMOVED - migrated to CentralHub (Phase: Session Centralization)
from .routers.chat_router import chat_router
from .routers.config_router import config_router
from .routers.content_router import router as content_router

# auth_router REMOVED - migrated to CentralHub (Complete Authentication Strangling)
from .routers.file_ops_router import file_ops_router
from .routers.gemini_router import (
    router as gemini_router,  # Gemini CLI (from ScareRunner integration)
)
from .routers.github_pr_router import github_pr_router
from .routers.health_router import router as health_router
from .routers.issues_dashboard_router import issues_dashboard_router
from .routers.issues_router import issues_router
from .routers.layout_books_router import layout_books_router
from .routers.logs_router import logs_router
from .routers.mesh_3d_router import mesh_3d_router
from .routers.monitoring_router import monitoring_router
from .routers.ngrok_router import ngrok_router
from .routers.notebook_item_types_router import notebook_item_types_router
from .routers.ollama_proxy import (
    router as ollama_router,  # SCARE-042 (Refactored to Ollama-compatible API)
)
from .routers.pipeline_items_router import pipeline_items_router
from .routers.proposals_router import router as proposals_router
from .routers.redis_explorer_router import redis_explorer_router
from .routers.roles_router import roles_router
from .routers.router import router
from .routers.search_router import search_router
from .routers.service_router import (
    router as service_router,  # Service info (from ScareRunner integration)
)
from .routers.services_router import services_router
from .routers.stable_diffusion_queue import router as sd_queue_router  # SD Queue Bridge
from .routers.system_router import system_router
from .routers.traces_router import traces_router
from .routers.users_router import users_router
from .routers.nodes_router import nodes_router
from .routers.tokens_router import tokens_router
from .routers.websocket_router import websocket_router

log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger(__name__)
logger.warning(">>> STARTUP: LOG_LEVEL=%s, effective_level=%s", LOG_LEVEL, log_level)


# Configurar limite de tamanho de requisição
# Padrão do FastAPI/Starlette é 2MB, aumentando para 100MB para suportar imagens 3D
# e upload de arquivos maiores (especialmente para célula 3d-mesh-prototyping)
REQUEST_SIZE_LIMIT = 100 * 1024 * 1024  # 100MB


# Desativando logs detalhados de httpx e httpcore
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# Lifespan event handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown.
    """
    # Startup
    logger.info("Starting ScareCopilotPortal Backend API")
    logger.info("ScareFeraLab directory: %s", SCAREFERA_LAB_DIR)

    # Ensure ScareFeraLab directory exists
    SCAREFERA_LAB_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("ScareFeraLab directory ready")

    # Generate and validate canonical schemas from Pydantic models (Phase 8)
    try:
        from .config.database import ARTIFACTS_DIR
        from .database.schema_initialization import generate_and_validate_schemas

        logger.info("🔧 Generating canonical schemas from Pydantic models...")
        _schemas = generate_and_validate_schemas(ARTIFACTS_DIR / "canonical")
        logger.info("✓ Schema generation complete")
    except Exception as e:
        logger.warning("⚠️  Schema generation failed, using static SCHEMAS.json: %s", e)
        logger.warning("Application will continue with existing SCHEMAS.json file")
        # Not critical - CanonicalQueryEngine will load from static file

    # Initialize database AFTER logging is configured
    from .database.connection import initialize_db

    initialize_db()

    from .config import HOST, PORT

    logger.info("API available at: http://%s:%s%s", HOST, PORT, API_PREFIX)
    logger.info("Documentation at: http://%s:%s%s/docs", HOST, PORT, API_PREFIX)

    # Validate MongoDB configuration, connectivity, and run migrations
    try:
        from .config.database import (
            MONGODB_DATABASE,
            MONGODB_ENABLED,
            MONGODB_HOST,
            MONGODB_MIGRATIONS_ENABLED,
            MONGODB_PORT,
        )
        from .database.mongodb.client import get_mongodb_client
        from .database.mongodb.migrations import run_migrations

        logger.info(
            "MongoDB configuration: ENABLED=%s, MIGRATIONS=%s, HOST=%s, PORT=%s, DB=%s",
            MONGODB_ENABLED, MONGODB_MIGRATIONS_ENABLED, MONGODB_HOST, MONGODB_PORT, MONGODB_DATABASE
        )

        if MONGODB_ENABLED:
            logger.info("Validating MongoDB connection...")
            try:
                client = await get_mongodb_client()
                if client is not None:
                    logger.info("✅ MongoDB connection validated successfully")

                    # Run migrations only if explicitly enabled
                    # NOTE: Migrations are now managed by CentralHub (Single Source of Truth)
                    # Set MONGODB_MIGRATIONS_ENABLED=true only for testing or emergency override
                    if MONGODB_MIGRATIONS_ENABLED:
                        logger.warning(
                            "⚠️  Running MongoDB migrations from Backend (NOT RECOMMENDED)"
                        )
                        logger.warning(
                            "    Migrations should run in CentralHub (Single Source of Truth)"
                        )
                        logger.warning(
                            "    Set MONGODB_MIGRATIONS_ENABLED=false to use CentralHub migrations"
                        )
                        migration_result = await run_migrations(client)

                        if migration_result["status"] == "success":
                            logger.info("✅ All migrations completed successfully")
                            logger.info(
                                "   Applied: %s, Skipped: %s",
                                migration_result['applied'], migration_result['skipped']
                            )
                        elif migration_result["status"] == "partial":
                            logger.warning("⚠️  Some migrations failed")
                            logger.warning(
                                "   Applied: %s, Failed: %s",
                                migration_result['applied'], migration_result['failed']
                            )
                        elif migration_result["status"] == "failed":
                            logger.error("❌ Migration failed")
                            logger.error("   Failed: %s", migration_result['failed'])
                        else:
                            logger.info("ℹ️  Migrations skipped: %s", migration_result.get('reason', 'Unknown reason'))
                    else:
                        logger.info(
                            "ℹ️  Backend migrations disabled (MONGODB_MIGRATIONS_ENABLED=false)"
                        )
                        logger.info(
                            "   Migrations are managed by CentralHub (Single Source of Truth)"
                        )
                else:
                    # get_mongodb_client returns None on connection failure
                    logger.error(
                        "❌ MongoDB is enabled but connection failed (client returned None)"
                    )
                    logger.error(
                        "Runtime collections (cells, books, sessions) will NOT be available"
                    )
                    logger.error(
                        "To fix: Check MongoDB connection with MONGODB_HOST environment variable"
                    )
                    logger.error(
                        "        For local MongoDB: Use 'make dev-up-local' (if implemented)"
                    )
                    logger.error(
                        "        For Atlas: Verify connection string and credentials in .env"
                    )
            except ConnectionError as e:
                # Explicit connection errors
                logger.error("❌ MongoDB connection error: %s", e)
                logger.error("Runtime collections will NOT be available")
                logger.error(
                    "To fix: Verify MONGODB_HOST, MONGODB_PORT, and credentials in .env"
                )
            except Exception as e:
                # Unexpected errors during validation or migration
                logger.error("❌ MongoDB initialization failed with unexpected error: %s", e)
                logger.error("Runtime collections will NOT be available")
                logger.error("To fix: Check MongoDB configuration and logs")
        else:
            logger.warning(
                "⚠️  MongoDB is DISABLED - Runtime collections will not be available"
            )
            logger.warning(
                "   To enable MongoDB: Set MONGODB_ENABLED=true in .env and restart"
            )
            logger.warning(
                "   Runtime collections: cells, books, sessions, users, memory, traces"
            )
            logger.warning(
                "   For external MongoDB (Atlas): Configure MONGODB_HOST, MONGODB_USERNAME, MONGODB_PASSWORD"
            )
    except Exception as e:
        logger.error("Error during MongoDB validation: %s", e)
        logger.error("This may indicate a configuration or import issue")

    # Initialize seed data (AI models, notebook types, agents, books, etc.)
    # This MUST happen before orchestrator initialization because orchestrator depends on agent data
    try:
        from app.scripts.seed_data import init_seed_data

        result = await init_seed_data()
        logger.info("Seed data initialized on startup: %s", result)
    except Exception as e:
        logger.error("Failed to initialize seed data on startup: %s", e)

    # Inicializa e registra o orchestrator global
    # This happens AFTER seed data because orchestrator requires the agent to exist in DB
    try:
        from app.orchestrator import Orchestrator, set_orchestrator_instance

        orchestrator = Orchestrator()
        await orchestrator.initialize()
        set_orchestrator_instance(orchestrator)
        logger.info("Orchestrator global instance initialized on backend startup.")
    except Exception as e:
        logger.error("Failed to initialize orchestrator on startup: %s", e)
        logger.error(
            "Orchestrator will not be available until the issue is resolved and server is restarted"
        )

    # Initialize NotebookItemType Registry (Plug and Play Cell Types)
    # This will automatically sync discovered types to the database
    try:
        from app.services.notebook_item_type_registry import get_registry

        registry = get_registry()
        discovered_types = await registry.discover_types(sync_to_db=True)
        logger.info("Cell type registry initialized: discovered %s types", len(discovered_types))
        logger.info("Registered cell types: %s", [t.id for t in discovered_types])
        logger.info("Cell types automatically synced to database and available via API")
    except Exception as e:
        logger.error("Failed to initialize cell type registry: %s", e)
        logger.warning("Cell type discovery will not be available until server restart")

    # Start event bus workers
    try:
        from app.workers.repository_access_worker import start_repository_worker

        await start_repository_worker()
        logger.info("Repository access worker started")
    except Exception as e:
        logger.error("Failed to start repository access worker: %s", e)
        logger.warning("File access via event bus will not be available")

    # Start session persistence worker (MVP 3)
    if MONGODB_ENABLED:
        try:
            from app.workers.session_persistence_worker import (
                start_session_persistence_worker,
            )

            await start_session_persistence_worker()
            logger.info("Session persistence worker started")
        except Exception as e:
            logger.error("Failed to start session persistence worker: %s", e)
            logger.warning("Session state persistence will not be available")

    # Start handshake worker (MVP 3)
    if MONGODB_ENABLED:
        try:
            from app.workers.handshake_worker import start_handshake_worker

            await start_handshake_worker()
            logger.info("Handshake worker started")
        except Exception as e:
            logger.error("Failed to start handshake worker: %s", e)
            logger.warning("State synchronization handshake will not be available")

    # Start log collection worker (MVP 3)
    if MONGODB_ENABLED:
        try:
            from app.workers.log_collection_worker import start_log_collection_worker

            await start_log_collection_worker()
            logger.info("Log collection worker started")
        except Exception as e:
            logger.error("Failed to start log collection worker: %s", e)
            logger.warning("Centralized log collection will not be available")

    # Initialize Redis pub/sub service for Event Bus (MVP 2)
    try:
        from .config.database import REDIS_L1_ENABLED
        from .services.redis_pubsub_service import get_pubsub_service

        if REDIS_L1_ENABLED:
            pubsub = await get_pubsub_service()
            if pubsub:
                logger.info("✅ Redis pub/sub service initialized for Event Bus")
            else:
                logger.warning("⚠️  Redis pub/sub service initialization failed")
                logger.warning(
                    "   Event Bus will not be available - check Redis connection"
                )
        else:
            logger.warning("⚠️  Redis L1 is DISABLED - Event Bus will not be available")
            logger.warning(
                "   To enable Redis L1: Set REDIS_L1_ENABLED=true in .env and restart"
            )
    except Exception as e:
        logger.error("Failed to initialize Redis pub/sub service: %s", e)
        logger.warning("Event Bus will not be available")

    # Initialize Gemini CLI session (from ScareRunner integration)
    gemini_available = False
    try:
        import os

        from .routers.gemini_router import set_gemini_session
        from .routers.service_router import set_gemini_available
        from .session_manager import GeminiSession

        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            gemini_session = GeminiSession(api_key=api_key, model=model)
            await gemini_session.initialize()
            set_gemini_session(gemini_session)
            gemini_available = True
            logger.info("✅ Gemini CLI session initialized (model: %s)", model)
        else:
            logger.info("ℹ️  Gemini CLI not configured (GEMINI_API_KEY not set)")
            logger.info("   Gemini functionality will not be available")

        set_gemini_available(gemini_available)
    except Exception as e:
        logger.error("Failed to initialize Gemini CLI: %s", e)
        logger.warning("Gemini CLI will not be available")

    # Vite dev server is now started via Docker entrypoint (supervisord)
    # No longer managed by Python subprocess

    # Mount artifacts directory as static files
    try:
        from pathlib import Path

        from fastapi.staticfiles import StaticFiles

        artifacts_path = Path("/app/artifacts")
        if artifacts_path.exists():
            app.mount(
                "/local",
                StaticFiles(directory=str(artifacts_path), html=True),
                name="local",
            )
            logger.info("✅ Mounted /local -> %s", artifacts_path)
        else:
            logger.info("ℹ️  Artifacts directory not found: %s", artifacts_path)
            logger.info("   Static artifacts serving will not be available")
    except Exception as e:
        logger.warning("Failed to mount artifacts directory: %s", e)

    # Optionally invalidate L1 cache on startup (useful for development)
    # Set INVALIDATE_CACHE_L1_ON_STARTUP=true or INVALIDATE_CACHE_L1_ON_STARTUP=all in .env
    try:
        import os
        from .database.hybrid.router import HybridDatabase

        invalidate_env = os.getenv("INVALIDATE_CACHE_L1_ON_STARTUP", "").lower()
        if invalidate_env in ("true", "all", "yes", "1"):
            logger.info("🔄 Invalidating L1 cache on startup (INVALIDATE_CACHE_L1_ON_STARTUP=%s)", invalidate_env)

            db = HybridDatabase()
            collection_to_invalidate = None

            # If env is "all" or "true", invalidate all collections
            if invalidate_env in ("all", "true"):
                collection_to_invalidate = None  # None = all collections

            result = await db.invalidate_cache_l1(collection=collection_to_invalidate)
            if result.get("success"):
                logger.info("✅ L1 cache invalidated successfully: %s", result.get("message"))
                if result.get("invalidated_collections"):
                    logger.info("   Collections invalidated: %s", result.get("invalidated_collections"))
                elif result.get("invalidated_collection"):
                    logger.info("   Collection invalidated: %s", result.get("invalidated_collection"))
            else:
                logger.warning("⚠️  L1 cache invalidation failed: %s", result.get("error"))
    except Exception as e:
        logger.warning("Failed to invalidate L1 cache on startup: %s", e)
        logger.warning("   To use this feature, set INVALIDATE_CACHE_L1_ON_STARTUP in .env")

    # Register Redis L1 heartbeat (fire-and-forget background task)
    # Writes state:service:backend:available every heartbeat_interval seconds
    # Allows GateKeeper to detect service availability without HTTP probes
    try:
        import asyncio
        import sys as _sys
        import os as _os
        _artifacts_path = _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'artifacts')
        if _artifacts_path not in _sys.path:
            _sys.path.insert(0, _os.path.abspath(_artifacts_path))
        from canonical.shared.services.base_service import BaseService as _BaseService
        _svc = _BaseService("backend", logger=logger)
        asyncio.create_task(_svc.heartbeat())
        logger.info("✅ Heartbeat registered: state:service:backend:available")
    except Exception as e:
        logger.warning("Heartbeat registration failed (non-critical): %s", e)

    yield

    # Shutdown
    logger.info("Shutting down ScareCopilotPortal Backend API")

    # Stop file watchers (development mode hot reload)
    try:
        from app.utils.json_file_watcher import stop_watchers

        await stop_watchers()
    except Exception:
        pass

    # Shutdown Gemini session
    try:
        from .routers.gemini_router import gemini_session

        if gemini_session:
            await gemini_session.shutdown()
            logger.info("Gemini CLI session shut down")
    except Exception:
        pass

    # Vite dev server shutdown is handled by supervisord (entrypoint)

    # Stop event bus workers
    try:
        from app.workers.repository_access_worker import stop_repository_worker

        await stop_repository_worker()
        logger.info("Repository access worker stopped")
    except Exception as e:
        logger.error("Error stopping repository access worker: %s", e)

    # Stop session persistence worker
    try:
        from app.workers.session_persistence_worker import (
            stop_session_persistence_worker,
        )

        await stop_session_persistence_worker()
        logger.info("Session persistence worker stopped")
    except Exception as e:
        logger.error("Error stopping session persistence worker: %s", e)

    # Stop handshake worker
    try:
        from app.workers.handshake_worker import stop_handshake_worker

        await stop_handshake_worker()
        logger.info("Handshake worker stopped")
    except Exception as e:
        logger.error("Error stopping handshake worker: %s", e)

    # Stop log collection worker
    try:
        from app.workers.log_collection_worker import stop_log_collection_worker

        await stop_log_collection_worker()
        logger.info("Log collection worker stopped")
    except Exception as e:
        logger.error("Error stopping log collection worker: %s", e)

    # Close Redis pub/sub service
    try:
        from .services.redis_pubsub_service import close_pubsub_service

        await close_pubsub_service()
        logger.info("Redis pub/sub service closed")
    except Exception as e:
        logger.error("Error closing Redis pub/sub service: %s", e)

    # Close MongoDB connection
    try:
        from .database.mongodb.client import close_mongodb_client

        await close_mongodb_client()
        logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error("Error closing MongoDB connection: %s", e)


# Create FastAPI app with increased request size limit
app = FastAPI(
    title="ScareVerse API",
    description="""
    RESTful API for ScareVerse notebook and cell management.

    ## Features
    - **Cell Management**: Create, read, update, delete, and execute cells
    - **Book Management**: Organize cells into books (master and volatile)
    - **Fragment Management**: Manage cell content fragments
    - **I18n Support**: Error responses include i18n keys for frontend localization
    - **Type-Driven Behavior**: Uses NotebookItemType for flexible cell and book behavior

    ## Authentication
    Most endpoints require authentication. Include JWT token in Authorization header:
    ```
    Authorization: Bearer <token>
    ```

    ## Error Responses
    All errors include:
    - `message`: Technical error message (English)
    - `i18n_key`: Translation key for frontend (e.g., 'errors.cellNotFound')
    - `details`: Additional context (e.g., {'cell_id': 'abc123'})

    ## API Conventions
    - All technical names (endpoints, parameters, attributes) are in English
    - User-facing messages are localized via i18n keys
    - All IDs use UUID format
    """,
    version="2.0.0",
    debug=DEBUG,
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
)


# Middleware para logar exceções não tratadas com stack trace
@app.middleware("http")
async def log_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
        raise


# JWT Context Middleware - Capture JWT token for forwarding to CentralHub
class JWTContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to capture JWT tokens from Authorization headers.

    This middleware extracts JWT tokens from incoming requests and stores them
    in request context (ContextVar) so they can be forwarded to CentralHub.

    Flow:
    1. Extract Authorization header
    2. If present and starts with "Bearer ", extract token
    3. Store token in ContextVar for request duration
    4. CentralHubClient will retrieve and forward to CentralHub

    Security Note:
    - Token is NOT validated here (delegated to CentralHub)
    - Token is request-scoped (ContextVar automatically isolated)
    - Token is only used for forwarding, not for local auth decisions
    """

    async def dispatch(self, request: Request, call_next):
        from .auth.context import set_current_token

        # Extract Authorization header
        auth_header = request.headers.get("Authorization", "")

        # If Bearer token present, store in context
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            set_current_token(token)
            logger.debug("JWT token captured for request: %s", request.url.path)

        # Process request
        response = await call_next(request)
        return response


# Add JWT context middleware (before CORS)
app.add_middleware(JWTContextMiddleware)

# Configure CORS for extension access
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(
    health_router, prefix=API_PREFIX
)  # Health checks first for quick access
app.include_router(router, prefix=API_PREFIX)
app.include_router(cells_router, prefix=API_PREFIX)
app.include_router(mesh_3d_router, prefix=API_PREFIX)
app.include_router(books_router, prefix=API_PREFIX)
app.include_router(layout_books_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(tokens_router, prefix=API_PREFIX)
app.include_router(nodes_router, prefix=API_PREFIX)
# sessions_router REMOVED - migrated to CentralHub (Phase: Session Centralization)
app.include_router(chat_router, prefix=API_PREFIX)
app.include_router(config_router, prefix=API_PREFIX)
app.include_router(system_router, prefix=API_PREFIX)
app.include_router(ai_models_router, prefix=API_PREFIX)
app.include_router(services_router, prefix=API_PREFIX)
# auth_router REMOVED - migrated to CentralHub (Complete Authentication Strangling)
app.include_router(file_ops_router, prefix=API_PREFIX)
app.include_router(ngrok_router, prefix=API_PREFIX)
app.include_router(issues_dashboard_router, prefix=API_PREFIX)
app.include_router(issues_router, prefix=API_PREFIX)
app.include_router(notebook_item_types_router, prefix=API_PREFIX)
app.include_router(pipeline_items_router, prefix=API_PREFIX)
app.include_router(traces_router, prefix=API_PREFIX)
app.include_router(roles_router, prefix=API_PREFIX)
app.include_router(audit_router, prefix=API_PREFIX)
app.include_router(search_router, prefix=API_PREFIX)
app.include_router(action_discovery_router, prefix=API_PREFIX)
app.include_router(websocket_router, prefix=API_PREFIX)
app.include_router(github_pr_router, prefix=API_PREFIX)
app.include_router(monitoring_router, prefix=API_PREFIX)
app.include_router(logs_router, prefix=API_PREFIX)
app.include_router(redis_explorer_router, prefix=API_PREFIX)
app.include_router(agent_router, prefix=API_PREFIX)
app.include_router(agent_websocket_router)
app.include_router(content_router, prefix=API_PREFIX)
app.include_router(
    ollama_router
)  # SCARE-042: Ollama-compatible proxy (router already includes /api prefix, do not add API_PREFIX)
app.include_router(
    sd_queue_router
)  # SD Queue Bridge: queue-based image generation (router already includes /api/images prefix)
# proposals_router already includes /api/proposals prefix, don't add API_PREFIX
app.include_router(proposals_router)

# ScareRunner integration routers (unified architecture)
app.include_router(
    gemini_router, tags=["gemini"]
)  # Gemini CLI endpoints: /prompt, /api/gemini/execute, /stats
app.include_router(
    artifacts_router, tags=["artifacts"]
)  # Artifacts discovery: /local/*
app.include_router(
    service_router, tags=["service"]
)  # Service info: /, /info, /vite/status (no API_PREFIX)

logger.info("[MAIN] Registered search_router: %s routes", len(search_router.routes))
logger.info("[MAIN] Search endpoints: %s", [f'{API_PREFIX}{r.path}' for r in search_router.routes])
logger.info("[MAIN] Registered action_discovery_router: %s routes", len(action_discovery_router.routes))
logger.info("[MAIN] Registered proposals_router: %s routes", len(proposals_router.routes))
logger.info("[MAIN] Proposals router prefix: %s", proposals_router.prefix)
logger.info("[MAIN] Proposals endpoints: %s", [f'{r.path}' for r in proposals_router.routes])
logger.info("[MAIN] Registered agent_websocket_router for real-time telemetry")


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "service": "ScareVerse Backend API",
        "version": API_VERSION,
        "status": "running",
        "docs": f"{API_PREFIX}/docs",
        "endpoints": {
            "health": f"{API_PREFIX}/health",
            "tree": f"{API_PREFIX}/tree",
            "tree_refresh": f"{API_PREFIX}/tree-refresh",
            "serve_file": f"{API_PREFIX}/ScareFeraLab/{{file_path}}",
            "persist_file": f"{API_PREFIX}/persist/{{path}}/{{filename}}",
            "persist_batch": f"{API_PREFIX}/persist-batch",
        },
        "core_endpoints": {
            "status": f"{API_PREFIX}/status",
            "cells": {
                "create": f"{API_PREFIX}/cells/create",
                "get": f"{API_PREFIX}/cells/{{id}}",
                "execute": f"{API_PREFIX}/cells/{{id}}/execute",
                "update": f"{API_PREFIX}/cells/{{id}}/update",
                "list": f"{API_PREFIX}/cells/list",
                "types_list": f"{API_PREFIX}/cells/types/list",
            },
            "books": {
                "criar": f"{API_PREFIX}/livros/criar",
                "obter": f"{API_PREFIX}/livros/{{id}}",
                "adicionar_celula": f"{API_PREFIX}/livros/{{id}}/adicionar_celula",
            },
            "users": {
                "register": f"{API_PREFIX}/users/register",
                "cells": f"{API_PREFIX}/users/{{id}}/cells",
            },
            "sessions": {
                "create": f"{API_PREFIX}/sessions/create",
                "list": f"{API_PREFIX}/sessions/user/{{id}}",
                "close": f"{API_PREFIX}/sessions/{{id}}/close",
            },
            "chat": {"processar": f"{API_PREFIX}/chat/processar"},
            "config": {
                "oauth_get": f"{API_PREFIX}/config/oauth",
                "oauth_update": f"{API_PREFIX}/config/oauth",
            },
        },
        "services_endpoints": {
            "status": f"{API_PREFIX}/services/status",
            "config": f"{API_PREFIX}/services/config",
            "test_connectivity": f"{API_PREFIX}/services/config/test",
            "service_logs": f"{API_PREFIX}/services/{{service_id}}/logs",
            "start_service": f"{API_PREFIX}/services/{{service_id}}/start",
            "stop_service": f"{API_PREFIX}/services/{{service_id}}/stop",
            "restart_service": f"{API_PREFIX}/services/{{service_id}}/restart",
        },
    }


if __name__ == "__main__":
    import uvicorn

    from .config import HOST, PORT

    # Configure with increased request size limit (100MB) to support 3D mesh generation
    # and large file uploads. Default FastAPI/Starlette limit is 2MB.
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level=LOG_LEVEL.lower(),
        limit_request_line=8190,  # Line length (default: 8190)
        limit_request_fields=100,  # Number of header fields (default: 100)
        limit_request_fields_size=16384,  # Total header size (default: 16384)
        timeout_keep_alive=5,  # Keep-alive timeout
        limit_max_requests=None,  # No limit on number of requests
    )
