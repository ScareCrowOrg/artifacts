"""
Configuration module for Ollama Queue Consumer Worker.

Manages Redis L1 configuration, job queue names, result key prefix,
and Ollama service connection settings.
"""

import os
from pathlib import Path

# ============================================================================
# Base Paths
# ============================================================================

BASE_DIR = Path(__file__).parent.absolute()

# ============================================================================
# Redis L1 Configuration (local queue)
# ============================================================================

REDIS_L1_HOST = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_PASSWORD = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
REDIS_L1_DB = int(os.getenv("REDIS_L1_DB", "0"))

# ============================================================================
# Job Queue Configuration
# ============================================================================

# Queue where backend router enqueues jobs via RPUSH
JOB_QUEUE = os.getenv("JOB_QUEUE", "scareverse:ollama-jobs:queue")

# Prefix for result keys – worker stores results here via RPUSH
# Backend router retrieves via BRPOP on scareverse:ollama-results:{job_id}
RESULTS_KEY_PREFIX = os.getenv("RESULTS_KEY_PREFIX", "scareverse:ollama-results")

# How long to block waiting for a job (seconds)
BRPOP_TIMEOUT = int(os.getenv("BRPOP_TIMEOUT", "300"))

# Auto-cleanup TTL for result keys (seconds)
RESULT_KEY_TTL = int(os.getenv("RESULT_KEY_TTL", "60"))

# ============================================================================
# Ollama Service Configuration
# ============================================================================

# Internal Docker network DNS for Ollama LLM service
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

# Default model (comma-separated list of models to pre-pull on startup)
OLLAMA_MODELS = os.getenv("OLLAMA_MODELS", "mistral")

# Timeout for Ollama inference requests (seconds)
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))

# ============================================================================
# Worker Configuration
# ============================================================================

WORKER_ID = os.getenv("WORKER_ID", "ollama-consumer-01")

# Health endpoint port
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8080"))

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "LOG_FORMAT",
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
