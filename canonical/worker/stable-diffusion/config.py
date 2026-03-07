"""
Configuration module for Stable Diffusion Queue Consumer Worker.

Manages Redis L1 configuration, job queue names, result key prefix,
and Stable Diffusion service connection settings.
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
JOB_QUEUE = os.getenv("JOB_QUEUE", "scareverse:sd-jobs:queue")

# Prefix for result keys – worker stores results here via RPUSH
# Backend router retrieves via BRPOP on scareverse:sd-results:{job_id}
RESULTS_KEY_PREFIX = os.getenv("RESULTS_KEY_PREFIX", "scareverse:sd-results")

# How long to block waiting for a job (seconds)
BRPOP_TIMEOUT = int(os.getenv("BRPOP_TIMEOUT", "300"))

# Auto-cleanup TTL for result keys (seconds) – slightly longer than Ollama for large images
RESULT_KEY_TTL = int(os.getenv("RESULT_KEY_TTL", "120"))

# ============================================================================
# Stable Diffusion Service Configuration
# ============================================================================

# Internal Docker network DNS for ScareNode-SD API service
SD_HOST = os.getenv("SD_HOST", "http://scarenode-sd:9090")

# Default SDXL model (high-quality asset rendering with flat lighting)
SD_MODEL = os.getenv("SD_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")

# Timeout for SD generation requests (seconds) – longer than Ollama due to image generation
SD_REQUEST_TIMEOUT = int(os.getenv("SD_REQUEST_TIMEOUT", "300"))

# HuggingFace model cache path (bind mount from host)
HF_HUB_CACHE = os.getenv("HF_HUB_CACHE", "/root/.cache/huggingface")

# ============================================================================
# Worker Configuration
# ============================================================================

WORKER_ID = os.getenv("WORKER_ID", "sd-consumer-01")

# Health endpoint port
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8081"))

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "LOG_FORMAT",
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
