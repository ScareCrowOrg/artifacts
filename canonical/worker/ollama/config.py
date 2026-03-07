"""
Configuration module for Ollama Worker.

Manages Ollama service connection and worker port settings.
All queue management is handled by GateKeeper.
"""

import os
from pathlib import Path

# ============================================================================
# Base Paths
# ============================================================================

BASE_DIR = Path(__file__).parent.absolute()

# ============================================================================
# Ollama Service Configuration
# ============================================================================

# Internal Docker network DNS for Ollama LLM service
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

# Timeout for Ollama inference requests (seconds)
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))

# ============================================================================
# Worker Configuration
# ============================================================================

WORKER_ID = os.getenv("WORKER_ID", "ollama-worker-01")

# HTTP port – GateKeeper calls POST /process, Docker health check uses GET /health
WORKER_PORT = int(os.getenv("WORKER_PORT", "9000"))

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "LOG_FORMAT",
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
