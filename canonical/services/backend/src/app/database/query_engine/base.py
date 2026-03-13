"""
Base classes for Query Engine.

This module defines the abstract base class for query engines that translate
MongoDB-style queries to SQL. Concrete implementations must inherit from
QueryEngine and implement the required abstract methods.

Architecture:
    QueryEngine (ABC)
    ├── find() - Execute query and return results
    ├── _compile_query() - Compile MongoDB query to SQL
    └── _validate_query() - Validate query syntax

Usage:
    from backend.app.database.query_engine.base import QueryEngine

    class PostgreSQLQueryEngine(QueryEngine):
        async def find(self, collection: str, query: Dict) -> List[Dict]:
            # Validate query
            self._validate_query(query)

            # Compile to SQL
            sql = self._compile_query(collection, query)

            # Execute and return results
            return await self._execute_sql(sql)
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QueryEngine(ABC):
    """
    Abstract base class for query engines.

    A query engine translates MongoDB-style queries into SQL queries
    for execution against a relational database. Implementations must
    provide query validation, compilation, and execution logic.

    Attributes:
        logger: Logger instance for this query engine

    Abstract Methods:
        find(): Execute query and return results
        _compile_query(): Compile MongoDB query to SQL
        _validate_query(): Validate query syntax

    Example:
        class MyQueryEngine(QueryEngine):
            async def find(self, collection: str, query: Dict) -> List[Dict]:
                self._validate_query(query)
                sql = self._compile_query(collection, query)
                return await self._execute(sql)

            def _compile_query(self, collection: str, query: Dict) -> str:
                # Compilation logic
                return "SELECT * FROM ..."

            def _validate_query(self, query: Dict) -> None:
                # Validation logic
                if not isinstance(query, dict):
                    raise InvalidQueryException("Query must be a dictionary")
    """

    def __init__(self):
        """Initialize query engine with logger."""
        self.logger = logger

    @abstractmethod
    async def find(
        self,
        collection: str,
        query: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
        sort: Optional[List[tuple]] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute query and return results.

        This method should:
        1. Validate the query using _validate_query()
        2. Compile the query to SQL using _compile_query()
        3. Execute the SQL query
        4. Return results as list of dictionaries

        Args:
            collection: Collection/table name to query
            query: MongoDB-style query (e.g., {"status": "active", "age": {"$gt": 18}})
            projection: Fields to include/exclude (e.g., {"name": 1, "email": 1})
            sort: Sort specification (e.g., [("created_at", -1)])
            limit: Maximum number of results to return
            skip: Number of results to skip (for pagination)

        Returns:
            List of dictionaries representing query results

        Raises:
            InvalidQueryException: If query syntax is invalid
            ValidationException: If query validation fails
            CompilationException: If SQL compilation fails
            QueryEngineException: For other query engine errors

        Example:
            results = await engine.find(
                collection="users",
                query={"status": "active", "age": {"$gte": 18}},
                projection={"name": 1, "email": 1},
                sort=[("created_at", -1)],
                limit=10
            )
        """

    @abstractmethod
    def _compile_query(
        self,
        collection: str,
        query: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
        sort: Optional[List[tuple]] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> str:
        """
        Compile MongoDB query to SQL.

        This method translates a MongoDB-style query into a SQL query
        suitable for execution against a relational database.

        Args:
            collection: Collection/table name
            query: MongoDB-style query
            projection: Fields to include/exclude
            sort: Sort specification
            limit: Maximum results
            skip: Results to skip

        Returns:
            SQL query string

        Raises:
            CompilationException: If compilation fails
            UnsupportedOperatorException: If query uses unsupported operators

        Example:
            sql = self._compile_query(
                collection="users",
                query={"status": "active", "age": {"$gte": 18}}
            )
            # Returns: "SELECT * FROM users WHERE status = 'active' AND age >= 18"
        """

    @abstractmethod
    def _validate_query(self, query: Dict[str, Any]) -> None:
        """
        Validate query syntax and semantics.

        This method performs validation checks on the query to ensure:
        - Query is a valid dictionary
        - All operators are supported
        - Field names are valid
        - Values are appropriate for their operators
        - No SQL injection attempts

        Args:
            query: MongoDB-style query to validate

        Raises:
            InvalidQueryException: If query syntax is invalid
            ValidationException: If query validation fails
            UnsupportedOperatorException: If query uses unsupported operators

        Example:
            self._validate_query({"status": "active", "age": {"$gte": 18}})
            # Passes validation

            self._validate_query({"status": {"$invalid": "value"}})
            # Raises UnsupportedOperatorException
        """


__all__ = ["QueryEngine"]
