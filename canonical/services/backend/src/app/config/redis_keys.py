"""
Redis Keys Configuration for ScareVerse

This module defines Redis key constants for the Ollama Queue Bridge
and other distributed features. Following naming convention:
    scareverse:{feature}:{type}:{identifier}

Example:
    scareverse:ollama-jobs:queue
    scareverse:ollama-results:abc123
    scareverse:ollama-deadletter

All keys use kebab-case for consistency and readability.
"""

# ============================================================================
# Ollama Queue Bridge Keys (SCARE-042)
# ============================================================================

OLLAMA_JOBS_QUEUE = "scareverse:ollama-jobs:queue"
"""Main queue for Ollama job requests (FIFO with RPUSH/LPOP)"""

OLLAMA_RESULTS_PREFIX = "scareverse:ollama-results"
"""Prefix for Ollama job results. Append :{job_id} for specific job.
Example: scareverse:ollama-results:abc-123-def"""

OLLAMA_DEADLETTER = "scareverse:ollama-deadletter"
"""Dead-letter queue for failed Ollama jobs after max retries"""

OLLAMA_METRICS = "scareverse:ollama-metrics"
"""Hash key for Ollama queue metrics (active jobs, total processed, etc.)"""

OLLAMA_ACTIVE_JOBS = "scareverse:ollama-metrics:active"
"""Set of currently active Ollama job IDs"""


def get_ollama_result_key(job_id: str) -> str:
    """
    Get the Redis key for a specific Ollama job result.

    Args:
        job_id: Unique job identifier

    Returns:
        str: Full Redis key (e.g., "scareverse:ollama-results:abc-123")
    """
    return f"{OLLAMA_RESULTS_PREFIX}:{job_id}"


# ============================================================================
# Future Keys (Placeholder for Phase 2+)
# ============================================================================

# Priority queue for Phase 2 (Sorted Set with ZADD/ZPOPMIN)
# OLLAMA_JOBS_PRIORITY = "scareverse:ollama-jobs:priority"

# Metrics for Phase 2 (Prometheus/Grafana integration)
# OLLAMA_METRICS_LATENCY = "scareverse:ollama-metrics:latency"
# OLLAMA_METRICS_THROUGHPUT = "scareverse:ollama-metrics:throughput"
