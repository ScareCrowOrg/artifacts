"""
Query Engine module for ScareVerse - MongoDB-style query to SQL translation.

This module provides an intelligent query engine that translates MongoDB-style
queries into SQL queries for PostgreSQL, enabling RBAC-aware database access.

Main exports:
- QueryEngine: Abstract base class for query engines
- QueryEngineException: Base exception for query engine errors
- QueryValidator: Utility class for query validation
- MONGODB_OPERATORS: Mapping of MongoDB operators to SQL

Usage:
    from backend.app.database.query_engine import QueryEngine

    class MyQueryEngine(QueryEngine):
        async def find(self, collection: str, query: Dict) -> List[Dict]:
            # Implementation
            pass
"""

from .base import QueryEngine
from .cache_manager import CacheManager
from .canonical_engine import CanonicalQueryEngine
from .constants import MONGODB_OPERATORS, OPERATOR_MAPPING, SQL_OPERATORS
from .exceptions import (
    CompilationException,
    InvalidQueryException,
    QueryEngineException,
    UnsupportedOperatorException,
    ValidationException,
)
from .rbac import PUBLIC_COLLECTIONS, PermissionError, RBACValidator
from .sandbox_engine import SandboxQueryEngine
from .utils import QueryCompiler, QueryValidator

__all__ = [
    "QueryEngine",
    "QueryEngineException",
    "InvalidQueryException",
    "UnsupportedOperatorException",
    "ValidationException",
    "CompilationException",
    "QueryValidator",
    "QueryCompiler",
    "MONGODB_OPERATORS",
    "SQL_OPERATORS",
    "OPERATOR_MAPPING",
    "CanonicalQueryEngine",
    "SandboxQueryEngine",
    "RBACValidator",
    "PermissionError",
    "PUBLIC_COLLECTIONS",
    "CacheManager",
]
