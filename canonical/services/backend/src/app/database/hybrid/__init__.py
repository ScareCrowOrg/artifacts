"""
HybridDatabase Module - Intelligent routing between file-based and MongoDB storage.

This module provides the HybridDatabase router that transparently routes data
operations to the appropriate backend based on data classification.

Phase 1.6 Features (RBAC-Mandatory):
- RBAC-mandatory API (all methods require current_user parameter)
- Multi-source search with precedence (Sandbox > Canonical > Runtime)
- Query engine integration (CanonicalQueryEngine, SandboxQueryEngine)
- Cache invalidation on writes (schema cache + L1 Redis)
- Modular architecture (router, multi_source_search, tier_operations)

Main exports:
- HybridDatabase: Main router class with RBAC-mandatory API
- MultiSourceSearch: Multi-tier search handler
- TierOperations: Tier-specific CRUD operations
- SandboxOperations: Sandbox file operations
- RedisCoordinator: Redis coordination utilities
- CacheSynchronizer: Cache synchronization utilities
- FallbackMixin: Backward compatibility and fallback methods
"""

from .collections import CANONICAL_COLLECTIONS, RUNTIME_COLLECTIONS
from .router import HybridDatabase
from .multi_source_search import MultiSourceSearch
from .tier_operations import TierOperations
from .coordination import RedisCoordinator, get_coordinator
from .cache_sync import CacheSynchronizer, get_synchronizer
from .fallback import FallbackMixin
from .sandbox_ops import SandboxOperations

__all__ = [
    "HybridDatabase",
    "MultiSourceSearch",
    "TierOperations",
    "CANONICAL_COLLECTIONS",
    "RUNTIME_COLLECTIONS",
    "RedisCoordinator",
    "get_coordinator",
    "CacheSynchronizer",
    "get_synchronizer",
    "FallbackMixin",
    "SandboxOperations",
]
