"""
Configuration settings for the backend API.

Phase 0 Update: Added CentralHub configuration for local-first mode
- Backend runs locally in ScareRunner (local-first)
- CentralHub runs in Kind cluster (centralized infrastructure)
- Backend can optionally communicate with CentralHub for system operations
"""

import logging
import os

# Phase 0: CentralHub configuration (centralized infrastructure service)
# CentralHub runs in Kubernetes and handles system-wide operations
# Backend can communicate with it for cluster-level functionality
CENTRALHUB_URL = os.getenv("CENTRALHUB_URL", "http://localhost:5051")
CENTRALHUB_ENABLED = os.getenv("CENTRALHUB_ENABLED", "false").lower() == "true"

# Database configuration (MongoDB, Redis, paths)
# Centralized in config.database module per RULESET.md Rule 4.1
from app.config.database import (
    # Import BASE_DIR first for use in this module
    BASE_DIR as _BASE_DIR,
)

# Base directory for all file operations (ScareFeraLab directory)
# This should be the root of the workspace/project
# Now sourced from config.database for centralization
BASE_DIR = _BASE_DIR
SCAREFERA_LAB_DIR = BASE_DIR

logger = logging.getLogger(__name__)
# Log base_dir e SCAREFERA_LAB_DIR na inicialização
# Server configuration
# Phase 1B: Backend port standardized to 5050 (was 5051)
# This aligns with VITE_API_BASE_PORT and VITE_API_BASE_URL
# Using port 5050 to avoid conflicts with common ports (8000, 8080, 3000, etc.)
HOST = os.getenv("API_HOST", "127.0.0.1")
PORT = int(os.getenv("API_PORT", "5050"))
DEBUG = os.getenv("API_DEBUG", "true").lower() == "true"

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", None)
# CORS configuration - allow extension access
# Can be comma-separated list or single value
# In production, replace "*" with specific extension origin
_cors_origins_str = os.getenv("CORS_ORIGINS")
if _cors_origins_str is not None:
    CORS_ORIGINS = [origin.strip() for origin in _cors_origins_str.split(",")]
else:
    CORS_ORIGINS = ["*"]

# Authentication configuration
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_TOKEN = os.getenv("AUTH_TOKEN", None)

# Google OAuth2 configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", None)


# API configuration
API_PREFIX = os.getenv("API_PREFIX", "/api")
API_VERSION = os.getenv("API_VERSION", "v1")

# Tree cache configuration
TREE_CACHE_TTL = int(os.getenv("TREE_CACHE_TTL", "60"))  # seconds

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# HTTP Client Configuration
# Global timeouts for HTTP connections (in seconds)
# These are used for external API calls that don't have service-specific timeouts
HTTP_CONNECTION_TIMEOUT = float(
    os.getenv("HTTP_CONNECTION_TIMEOUT", "10.0")
)  # Connection timeout
HTTP_READ_TIMEOUT = float(os.getenv("HTTP_READ_TIMEOUT", "30.0"))  # Read timeout

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT = int(
    os.getenv("OLLAMA_TIMEOUT", "120")
)  # Increased from 30s for prompt optimization

# Ollama Queue Bridge configuration (SCARE-042)
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "mistral")
"""Default Ollama model for queue-based requests"""

# Available Ollama models (7 models supported)
AVAILABLE_OLLAMA_MODELS = [
    "gemma",
    "phi",
    "phi3",
    "qwen2.5-coder",
    "deepseek-coder",
    "llama2",
    "mistral",
]
"""List of available Ollama models"""

# RAG and Embeddings configuration
# Model to use for embeddings (supports: mistral, phi, deepseek-coder)
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "mistral")
# ChromaDB vector store configuration
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH", "chroma_db")
VECTORSTORE_COLLECTION = os.getenv("VECTORSTORE_COLLECTION", "scareverse_docs")
# Chunking configuration for document ingestion
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Embedding Generation Rate Limiting Configuration
# These settings control request rate to prevent overwhelming the Ollama backend
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))  # Chunks per batch
EMBEDDING_BATCH_DELAY = float(
    os.getenv("EMBEDDING_BATCH_DELAY", "0.5")
)  # Seconds between batches
EMBEDDING_MAX_CONCURRENT = int(
    os.getenv("EMBEDDING_MAX_CONCURRENT", "1")
)  # Max concurrent requests

# RAG Post-processing configuration with Local LLM
# Enable/disable RAG context post-processing with local LLM (Phi/Ollama)
RAG_POSTPROCESS_LLM_ENABLED = (
    os.getenv("RAG_POSTPROCESS_LLM_ENABLED", "false").lower() == "true"
)
# Local LLM model to use for RAG context post-processing
RAG_POSTPROCESS_LLM_MODEL = os.getenv("RAG_POSTPROCESS_LLM_MODEL", "phi3:latest")
# Prompt template for RAG context post-processing
RAG_POSTPROCESS_LLM_PROMPT = os.getenv(
    "RAG_POSTPROCESS_LLM_PROMPT",
    """You are a helpful assistant that condenses and filters retrieved context.

Your task: Analyze the retrieved context chunks and create a concise, relevant summary that will help answer the user's question. Keep essential information and eliminate redundancies. If the chunks don't contain relevant information for the question, state that clearly.

Context Chunks:
{context}

User's Question: {query}

Instructions:
1. Extract only information relevant to the question
2. Remove duplicate or redundant information
3. Organize information logically
4. Keep technical details and specific facts
5. If context is not relevant, say "No relevant information found in context."

Condensed Context:""",
)

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)
GEMINI_API_URL = os.getenv(
    "GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta"
)
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT", "120"))
GEMINI_DEFAULT_MODEL = os.getenv("GEMINI_DEFAULT_MODEL", "gemini-2.5-flash")

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1")
OPENAI_DEFAULT_MODEL = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-3.5-turbo")
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "60.0"))
OPENAI_MODELS = [
    m.strip()
    for m in os.getenv("OPENAI_MODELS", "gpt-3.5-turbo,gpt-4o,gpt-4o-mini").split(",")
]

# Supported AI models
OLLAMA_MODELS = os.getenv("OLLAMA_MODELS", "mistral,deepseek,phi").split(",")
GEMINI_MODELS = os.getenv("GEMINI_MODELS", "gemini").split(",")
NGROK_API_URL = os.getenv("NGROK_API_URL", "http://ngrok:4040")

# RAG-specific vector store path
RAG_VECTORSTORE_PATH = os.getenv("RAG_VECTORSTORE_PATH", "backend/chroma_db")

# Conversation Tracing Configuration
ENABLE_CONVERSATION_TRACING = (
    os.getenv("ENABLE_CONVERSATION_TRACING", "false").lower() == "true"
)

# RBAC Configuration
# Email of the initial admin user (used during user migration)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@scareverse.com")

# Stable Diffusion Configuration (Legacy - Direct HTTP to SD Forge)
STABLE_DIFFUSION_URL = os.getenv("STABLE_DIFFUSION_URL", "http://localhost:7860")
STABLE_DIFFUSION_TIMEOUT = int(os.getenv("STABLE_DIFFUSION_TIMEOUT", "120"))

# Stable Diffusion Queue Bridge Configuration (Recommended)
SD_QUEUE_URL = os.getenv("SD_QUEUE_URL", "http://localhost:5050")
SD_QUEUE_TIMEOUT = int(os.getenv("SD_QUEUE_TIMEOUT", "300"))  # 5 min BRPOP timeout
SD_DEFAULT_MODEL = os.getenv(
    "SD_DEFAULT_MODEL", "stabilityai/stable-diffusion-xl-base-1.0"
)  # SDXL for superior asset rendering with flat lighting support

# Stable Fast 3D Configuration (Stability AI)
STABLE_FAST_3D_API_KEY = os.getenv("STABLE_FAST_3D_API_KEY", None)
STABLE_FAST_3D_URL = os.getenv(
    "STABLE_FAST_3D_URL", "https://api.stability.ai/v2beta/3d/stable-fast-3d"
)
STABLE_FAST_3D_TIMEOUT = int(os.getenv("STABLE_FAST_3D_TIMEOUT", "60"))

# Aider-Worker Configuration (Open Interpreter integration)
AIDER_WORKER_BASE_URL = os.getenv(
    "AIDER_WORKER_BASE_URL", "http://scareverse-aider-worker:8001"
)
AIDER_WORKER_TIMEOUT = int(os.getenv("AIDER_WORKER_TIMEOUT", "120"))
