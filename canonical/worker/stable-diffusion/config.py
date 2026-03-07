"""
Configuration module for Stable Diffusion Worker.

Manages SD service connection and worker port settings.
All queue management is handled by GateKeeper.
"""

import os
from pathlib import Path

# ============================================================================
# Base Paths
# ============================================================================

BASE_DIR = Path(__file__).parent.absolute()

# ============================================================================
# Stable Diffusion Service Configuration
# ============================================================================

# Internal Docker network DNS for ScareNode-SD API service
SD_HOST = os.getenv("SD_HOST", "http://scarenode-sd:9090")

# Default SDXL model
SD_MODEL = os.getenv("SD_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")

# Timeout for SD generation requests (seconds)
SD_REQUEST_TIMEOUT = int(os.getenv("SD_REQUEST_TIMEOUT", "300"))

# HuggingFace model cache path (bind mount from host)
HF_HUB_CACHE = os.getenv("HF_HUB_CACHE", "/root/.cache/huggingface")

# ============================================================================
# Worker Configuration
# ============================================================================

WORKER_ID = os.getenv("WORKER_ID", "sd-worker-01")

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
