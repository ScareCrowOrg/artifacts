"""
Canonical JobType model.

Defines the schema for job-type definitions stored in
``artifacts/canonical/job-types/*.json``.

This model is the source of truth for:
- SCHEMAS.json ``job_types`` collection (HybridDatabase canonical store)
- GateKeeper config loader validation
- New worker onboarding documentation

Phase 4 Architecture: Job-types declare execution model (service vs subprocess)
and their dependencies, allowing GateKeeper to manage worker availability via
Docker health checks.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ServiceConfig(BaseModel):
    """HTTP service execution configuration."""

    name: str = Field(..., description="Service name (matches docker-compose service name)")
    endpoint: str = Field(..., description="HTTP base URL (e.g. http://scareverse-ollama-service:11434)")


class WorkerConfig(BaseModel):
    """Subprocess worker execution configuration."""

    type: str = Field(..., description="Worker type (e.g. 'job')")
    path: str = Field(..., description="Relative path to worker implementation (e.g. 'artifacts/canonical/workers/rembg')")
    entry_point: str = Field(..., description="Entry point file (e.g. 'main.py')")
    python_version: str = Field(..., description="Required Python version (e.g. '3.11+')")


class JobConfiguration(BaseModel):
    """Job-type execution configuration."""

    timeout_seconds: int = Field(..., ge=1, le=3600, description="Execution timeout in seconds")
    memory_limit_mb: Optional[int] = Field(None, ge=1, description="Memory limit in MB (optional)")
    requires_gpu: Optional[bool] = Field(None, description="Whether GPU is required")
    requires_internet: Optional[bool] = Field(None, description="Whether internet access is required")


class JobType(BaseModel):
    """
    Canonical job type definition with validation (Phase 4 format).

    Each JSON file in ``artifacts/canonical/job-types/`` must conform to
    this schema. The ``name`` field is the primary key used by GateKeeper
    to look up routing config; ``aliases`` allows legacy job-type names to
    resolve to the same entry.

    Phase 4 supports two execution models:
    - "service": Long-lived HTTP service (e.g. Ollama, Stable Diffusion)
    - "subprocess": Ephemeral subprocess launched per job (e.g. Rembg)
    """

    name: str = Field(
        ...,
        description="Primary key – canonical job type name (matches filename without .json)",
    )
    version: str = Field(
        ...,
        description="Semantic version (e.g. '2.0.0')",
    )
    description: str = Field(
        ...,
        description="Human-readable description of the job type",
    )
    execution_model: str = Field(
        ...,
        description="Execution model: 'service' (HTTP) or 'subprocess' (ephemeral)",
        pattern="^(service|subprocess)$",
    )
    service: Optional[ServiceConfig] = Field(
        None,
        description="Service configuration (required if execution_model='service')",
    )
    worker: Optional[WorkerConfig] = Field(
        None,
        description="Worker configuration (required if execution_model='subprocess')",
    )
    configuration: JobConfiguration = Field(
        ...,
        description="Job execution configuration",
    )
    queue: str = Field(
        ...,
        description="Primary Redis queue name",
    )
    queue_l1: str = Field(
        ...,
        description="Redis L1 (local) queue name",
    )
    queue_l2: str = Field(
        ...,
        description="Redis L2 (global/fallback) queue name",
    )
    result_storage: str = Field(
        default="rpush_l1",
        description="Result persistence strategy: 'rpush_l1' (RPUSH to L1) or 'hset_l2' (HSET to L2)",
    )
    result_key_prefix: str = Field(
        ...,
        description="Redis key prefix for storing job results (e.g. 'scareverse:ollama-results')",
    )
    result_key_ttl: int = Field(
        default=120,
        ge=0,
        description="TTL in seconds for result keys in Redis",
    )
    timeout: int = Field(
        ...,
        ge=1,
        le=3600,
        description="Execution timeout in seconds (mirrors configuration.timeout_seconds)",
    )
    worker_availability_key: str = Field(
        ...,
        description="Redis key indicating worker availability (e.g. 'state:worker:ollama_generate:available')",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Docker service names this job depends on for execution (e.g. ['ollama', 'redis'])",
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="Legacy or alternate job-type names that resolve to this entry",
    )
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for input validation",
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for output validation",
    )
