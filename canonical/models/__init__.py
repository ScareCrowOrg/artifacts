"""
Canonical model definitions for ScareVerse artifact schemas.

Pydantic models in this package serve as the source of truth for
canonical collection schemas (SCHEMAS.json) and are used by HybridDatabase
for validation when loading artifacts from canonical/sandbox/runtime sources.
"""

from .job_type import JobType

__all__ = ["JobType"]
