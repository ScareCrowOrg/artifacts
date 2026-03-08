"""
Canonical JobType model.

Defines the schema for job-type definitions stored in
``artifacts/canonical/job-types/*.json``.

This model is the source of truth for:
- SCHEMAS.json ``job_types`` collection (HybridDatabase canonical store)
- GateKeeper config loader validation
- New worker onboarding documentation
"""

from typing import List

from pydantic import BaseModel, Field


class JobType(BaseModel):
    """
    Canonical job type definition with validation.

    Each JSON file in ``artifacts/canonical/job-types/`` must conform to
    this schema.  The ``name`` field is the primary key used by GateKeeper
    to look up routing config; ``aliases`` allows legacy job-type names to
    resolve to the same entry.
    """

    name: str = Field(
        ...,
        description="Primary key – canonical job type name (matches filename without .json)",
    )
    worker_type: str = Field(
        ...,
        description="Worker implementation type (e.g. 'ollama', 'rembg', 'stable-diffusion')",
    )
    endpoint: str = Field(
        ...,
        description="Default HTTP base URL of the atomic worker (overridable via env var)",
    )
    queue_l1: str = Field(
        ...,
        description="Redis L1 (owner/local) queue name",
    )
    queue_l2: str = Field(
        ...,
        description="Redis L2 (global) queue name",
    )
    timeout: int = Field(
        ...,
        ge=1,
        le=3600,
        description="HTTP request timeout in seconds",
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
    aliases: List[str] = Field(
        default_factory=list,
        description="Legacy or alternate job-type names that resolve to this entry",
    )
