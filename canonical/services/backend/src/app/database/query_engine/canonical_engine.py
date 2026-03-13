"""
CanonicalQueryEngine - Schema-aware SQLite query engine for canonical data.

This engine translates MongoDB-like queries to optimized SQLite SQL for
canonical data (templates, roles, workflows) using predefined schemas
from artifacts/canonical/SCHEMAS.json.

Key features:
- Schema-aware SQLite compilation
- Support for 13 MongoDB operators
- Automatic indexing on critical fields
- Performance: <50ms for simple queries, <100ms for complex queries (5k docs)
- Full query validation and error handling

Architecture:
    CanonicalQueryEngine (QueryEngine)
    ├── _load_schemas() - Load schemas from JSON
    ├── _init_tables() - Create SQLite tables from schemas
    ├── _create_indices() - Create performance indices
    ├── find() - Execute MongoDB-like queries
    ├── _compile_query() - Compile MongoDB query to SQL
    └── _compile_operators() - Compile MongoDB operators to SQL conditions
"""

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import QueryEngine
from .canonical_compilers import SQLiteCompiler
from .canonical_schema import SchemaLoader
from .exceptions import (
    CompilationException,
    UnsupportedOperatorException,
    ValidationException,
)
from .utils import QueryValidator

logger = logging.getLogger(__name__)


class CanonicalQueryEngine(QueryEngine):
    """
    Schema-aware query engine for Canonical data.

    Translates MongoDB-style queries to SQLite SQL using predefined schemas.
    Supports comparison, logical, array, field, and string operators.

    Example:
        engine = CanonicalQueryEngine()

        # Simple query
        results = await engine.find(
            "templates",
            {"status": "published"}
        )

        # Complex query
        results = await engine.find(
            "templates",
            {
                "$and": [
                    {"status": "published"},
                    {"tags": {"$all": ["featured"]}},
                    {"metadata.level": {"$gte": 5}}
                ]
            },
            limit=10
        )
    """

    def __init__(
        self,
        schemas_path: Optional[Path] = None,
        redis_client=None,
        base_path: Optional[Path] = None,
    ):
        """
        Initialize CanonicalQueryEngine with schemas and optional Redis caching.

        Args:
            schemas_path: Path to SCHEMAS.json (default: artifacts/canonical/SCHEMAS.json)
            redis_client: Redis client for caching (optional)
            base_path: Base path to canonical artifacts (default: artifacts/canonical)

        Raises:
            ValidationException: If schema file is invalid or not found
        """
        super().__init__()
        self.redis = redis_client

        # Set base_path for canonical data loading
        if base_path is None:
            # Use BASE_DIR if set (Docker standard)
            base_dir = os.getenv("BASE_DIR")
            if base_dir:
                base_path = Path(base_dir) / "artifacts" / "canonical"
            else:
                # Fallback to __file__ location (development without BASE_DIR)
                try:
                    current_file = Path(__file__).resolve()
                    project_root = current_file.parent.parent.parent.parent.parent
                    base_path = project_root / "artifacts" / "canonical"
                except (FileNotFoundError, ValueError):
                    base_path = Path("/app") / "artifacts" / "canonical"

        self.base_path = base_path

        logger.info("🚀 Initializing CanonicalQueryEngine...")
        logger.debug("📂 Schemas path: %s", schemas_path)
        logger.debug("📍 Base path: %s", self.base_path)
        logger.debug("📍 Base path exists: %s", self.base_path.exists())
        logger.debug("📍 BASE_DIR env: %s", os.getenv('BASE_DIR', 'NOT SET'))

        self.schemas = SchemaLoader.load_schemas(schemas_path)
        logger.info("📋 Loaded %s schema definitions", len(self.schemas))

        logger.debug("🔧 Creating in-memory SQLite connection...")
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        logger.debug("✓ SQLite connection created (:memory:)")

        logger.debug("📊 Initializing database tables from schemas...")
        SchemaLoader.init_tables(self.conn, self.schemas)
        logger.info("✓ Created %s tables (excluding version/description/last_updated)", len(self.schemas) - 3)

        logger.debug("🔍 Creating database indices...")
        SchemaLoader.create_indices(self.conn, self.schemas)
        logger.info("✓ Database indices created")

        # Load canonical data from JSON files into SQLite tables
        logger.info("=" * 60)
        logger.info("CANONICAL DATA LOADING PHASE")
        logger.info("=" * 60)
        self._load_canonical_data()
        logger.info("=" * 60)

        # Verify data was loaded
        self._log_table_stats()

        logger.info("🎉 CanonicalQueryEngine fully initialized with %s collections", len(self.schemas) - 3)

    def _load_canonical_data(self) -> None:
        """
        Load canonical data from JSON files into SQLite tables.

        Discovers and loads all *.json files from artifacts/canonical/{collection}/
        directories and inserts them into the corresponding SQLite tables.
        """
        logger.info("🔄 Starting canonical data loading from: %s", self.base_path)
        total_docs_loaded = 0
        collections_loaded = 0

        for collection in self.schemas.keys():
            # Skip metadata fields
            if collection in ["version", "description", "last_updated"]:
                logger.debug("⏭️  Skipping metadata field: %s", collection)
                continue

            logger.info("📦 Processing collection: %s", collection)
            collection_dir = self.base_path / collection
            logger.debug("📁 Collection directory: %s", collection_dir)

            if not collection_dir.exists():
                logger.warning("⚠️  [%s] Directory not found: %s", collection, collection_dir)
                continue

            # Load all JSON files from the collection directory
            documents = []
            file_count = 0
            try:
                json_files = list(collection_dir.glob("*.json"))
                if not json_files:
                    logger.warning("⚠️  [%s] No JSON files found", collection)
                    continue
                logger.info("📄 [%s] Found %s JSON files", collection, len(json_files))

                for json_file in json_files:
                    file_count += 1
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            doc = json.load(f)
                            # Ensure doc is a dict
                            if isinstance(doc, dict):
                                # Normalize: map "id" → "_id" if _id doesn't exist
                                if "_id" not in doc and "id" in doc:
                                    doc["_id"] = doc["id"]
                                documents.append(doc)
                                logger.debug("  ✓ Loaded: %s", json_file.name)
                            else:
                                logger.warning("  ✗ Invalid doc format (not dict): %s", json_file.name)
                    except json.JSONDecodeError as e:
                        logger.warning("  ✗ JSON decode error in %s: %s", json_file.name, e)
                        continue
                    except IOError as e:
                        logger.warning("  ✗ IO error reading %s: %s", json_file.name, e)
                        continue

                # Insert documents if any were loaded
                if documents:
                    logger.info("📝 [%s] Inserting %s documents", collection, len(documents))
                    self.insert_data(collection, documents)
                    logger.info("✅ [%s] Loaded %s/%s documents", collection, len(documents), file_count)
                    total_docs_loaded += len(documents)
                    collections_loaded += 1
                else:
                    logger.warning("⚠️  [%s] No valid documents found (%s files checked)", collection, file_count)

            except Exception as e:
                logger.error("❌ Error loading canonical data for %s: %s", collection, e, exc_info=True)

        logger.info(
            "✨ Canonical data loading complete: %s documents loaded into %s collections",
            total_docs_loaded, collections_loaded
        )

    def _log_table_stats(self) -> None:
        """
        Log statistics about loaded tables to verify data was inserted correctly.
        """
        logger.info("📊 TABLE STATISTICS:")
        logger.info("-" * 60)

        for collection in self.schemas.keys():
            if collection in ["version", "description", "last_updated"]:
                continue

            try:
                cursor = self.conn.execute(
                    f"SELECT COUNT(*) as count FROM {collection}"
                )
                row = cursor.fetchone()
                doc_count = row["count"] if row else 0

                if doc_count > 0:
                    logger.info("  ✅ %s %s documents", collection, doc_count)
                else:
                    logger.warning("  ⚠️  %s %s documents (EMPTY!)", collection, doc_count)
            except Exception as e:
                logger.error("  ❌ %s Error: %s", collection, e)

        logger.info("-" * 60)

    def _validate_collection(self, collection: str):
        """
        Validate collection name exists in schema.

        Args:
            collection: Collection name to validate

        Raises:
            ValidationException: If collection not found
        """
        if collection not in self.schemas or collection in ["version", "description"]:
            available = [
                k for k in self.schemas.keys() if k not in ["version", "description"]
            ]
            raise ValidationException(
                f"Collection '{collection}' not found in schema",
                field="collection",
                value=f"Available: {', '.join(available)}",
            )

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
        Execute MongoDB-like query on canonical data.

        Args:
            collection: Collection name (e.g., "templates", "roles")
            query: MongoDB-style query (e.g., {"status": "active"})
            projection: Fields to include/exclude (not implemented yet)
            sort: Sort specification (not implemented yet)
            limit: Maximum number of results
            skip: Number of results to skip

        Returns:
            List of dictionaries representing query results

        Raises:
            ValidationException: If collection or query is invalid
            CompilationException: If query compilation fails

        Example:
            results = await engine.find(
                "templates",
                {"status": "published", "owner": "user1"},
                limit=10
            )
        """
        self._validate_collection(collection)
        self._validate_query(query)

        schema = self.schemas[collection]
        sql = self._compile_query(collection, query, projection, sort, limit, skip)

        try:
            # Debug: check row count before query
            if collection == "notebook_item_types":
                count_sql = f"SELECT COUNT(*) as cnt FROM {collection}"
                count_result = self.conn.execute(count_sql).fetchone()
                logger.info("[CanonicalQueryEngine.find] DEBUG: %s table has %s rows before query",
                           collection, count_result[0] if count_result else 0)
                logger.info("[CanonicalQueryEngine.find] DEBUG: SQL query = %s", sql)

            cursor = self.conn.execute(sql)
            results = [dict(row) for row in cursor.fetchall()]

            if collection == "notebook_item_types":
                logger.info("[CanonicalQueryEngine.find] Query returned %s results from %s", len(results), collection)

            if results and collection == "notebook_item_types":
                logger.info("[CanonicalQueryEngine.find] First result from %s: %s", collection, results[0])

            # Parse JSON fields
            for result in results:
                for field_name, field_spec in schema.items():
                    if field_spec.get("type") == "JSON" and result.get(field_name):
                        try:
                            result[field_name] = json.loads(result[field_name])
                        except (json.JSONDecodeError, TypeError):
                            pass

            return results
        except sqlite3.Error as e:
            raise CompilationException(
                f"SQL execution error: {e}",
                query=query,
                partial_sql=sql,
            )

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
        Compile MongoDB query to SQLite SQL.

        Args:
            collection: Collection/table name
            query: MongoDB-style query
            projection: Fields to include/exclude (not implemented yet)
            sort: Sort specification (not implemented yet)
            limit: Maximum results
            skip: Results to skip

        Returns:
            SQL query string

        Raises:
            CompilationException: If compilation fails
        """
        schema = self.schemas[collection]

        # Build SELECT clause
        sql = f"SELECT * FROM {collection}"

        # Build WHERE clause
        if query:
            where_conditions = self._compile_where(query, schema)
            if where_conditions:
                sql += f" WHERE {where_conditions}"

        # Add LIMIT and OFFSET
        # SQLite requires LIMIT when using OFFSET, so use -1 for "no limit"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        elif skip is not None:
            # OFFSET without LIMIT needs LIMIT -1 (means unlimited in SQLite)
            sql += " LIMIT -1"

        if skip is not None:
            sql += f" OFFSET {int(skip)}"

        logger.debug("Compiled SQL: %s", sql)
        return sql

    def _compile_where(self, query: Dict[str, Any], schema: Dict) -> str:
        """
        Compile MongoDB query to WHERE clause.

        Args:
            query: MongoDB query dict
            schema: Collection schema

        Returns:
            SQL WHERE clause conditions
        """
        conditions = []

        for key, value in query.items():
            if key.startswith("$"):
                # Logical operator
                if key == "$and":
                    subconditions = [
                        self._compile_where(subcond, schema) for subcond in value
                    ]
                    conditions.append(f"({' AND '.join(subconditions)})")
                elif key == "$or":
                    subconditions = [
                        self._compile_where(subcond, schema) for subcond in value
                    ]
                    conditions.append(f"({' OR '.join(subconditions)})")
                elif key == "$nor":
                    subconditions = [
                        self._compile_where(subcond, schema) for subcond in value
                    ]
                    conditions.append(f"NOT ({' OR '.join(subconditions)})")
                elif key == "$not":
                    subcondition = self._compile_where(value, schema)
                    conditions.append(f"NOT ({subcondition})")
                else:
                    raise UnsupportedOperatorException(key)
            else:
                # Field condition
                field_condition = self._compile_field_condition(key, value, schema)
                conditions.append(field_condition)

        return " AND ".join(conditions)

    def _compile_field_condition(self, field: str, value: Any, schema: Dict) -> str:
        """
        Compile field condition to SQL.

        Args:
            field: Field name (supports nested like "metadata.level")
            value: Field value or operator dict
            schema: Collection schema

        Returns:
            SQL condition string
        """
        # Get field type from schema
        field_type = self._get_field_type(field, schema)

        if isinstance(value, dict):
            # Field operators
            operator_conditions = self._compile_operators(field, value, field_type)
            return " AND ".join(operator_conditions)
        else:
            # Implicit equality
            field_accessor = SQLiteCompiler.compile_field_accessor(field, field_type)
            return f"{field_accessor} = {self._escape_value(value)}"

    def _compile_operators(
        self, field: str, operators: Dict, field_type: str
    ) -> List[str]:
        """
        Compile MongoDB operators to SQL conditions.

        Args:
            field: Field name
            operators: Dictionary of operators and values
            field_type: Field type from schema

        Returns:
            List of SQL conditions

        Raises:
            UnsupportedOperatorException: If operator not supported
        """
        conditions = []
        # Check if field is already a SQL expression (e.g., from nested $elemMatch)
        if "(" in field:
            # Field is already a complete SQL expression, don't process it further
            field_accessor = field
        else:
            # Normal field, compile accessor
            field_accessor = SQLiteCompiler.compile_field_accessor(field, field_type)

        for op, value in operators.items():
            if op == "$eq":
                conditions.append(f"{field_accessor} = {self._escape_value(value)}")
            elif op == "$in":
                conditions.append(
                    SQLiteCompiler.compile_in(field_accessor, value, self._escape_value)
                )
            elif op == "$nin":
                conditions.append(
                    SQLiteCompiler.compile_nin(
                        field_accessor, value, self._escape_value
                    )
                )
            elif op == "$gt":
                conditions.append(f"{field_accessor} > {self._escape_value(value)}")
            elif op == "$gte":
                conditions.append(f"{field_accessor} >= {self._escape_value(value)}")
            elif op == "$lt":
                conditions.append(f"{field_accessor} < {self._escape_value(value)}")
            elif op == "$lte":
                conditions.append(f"{field_accessor} <= {self._escape_value(value)}")
            elif op == "$ne":
                conditions.append(f"{field_accessor} != {self._escape_value(value)}")
            elif op == "$regex":
                conditions.append(
                    SQLiteCompiler.compile_regex(
                        field_accessor, value, self._escape_value
                    )
                )
            elif op == "$all":
                conditions.append(
                    SQLiteCompiler.compile_all(
                        field_accessor, value, self._escape_value
                    )
                )
            elif op == "$elemMatch":
                # Compile nested conditions for $elemMatch
                nested_conditions = []
                if isinstance(value, dict):
                    for nested_op, nested_value in value.items():
                        if nested_op.startswith("$"):
                            # Operator-based condition (e.g., {"$eq": "featured"})
                            # Use 'value' as the field accessor (json_each returns 'value')
                            nested = self._compile_operators(
                                "value",
                                {nested_op: nested_value},
                                "TEXT",  # json_each returns TEXT values
                            )
                            nested_conditions.extend(nested)
                        else:
                            # Field-based condition for nested objects (e.g., {"level": {"$gte": 5}})
                            # Access nested field in json_each value
                            if isinstance(nested_value, dict):
                                # Has operators
                                nested = self._compile_operators(
                                    f"json_extract(value, '$.{nested_op}')",
                                    nested_value,
                                    "TEXT",
                                )
                                nested_conditions.extend(nested)
                            else:
                                # Direct equality
                                nested_conditions.append(
                                    f"json_extract(value, '$.{nested_op}') = {self._escape_value(nested_value)}"
                                )

                conditions.append(
                    SQLiteCompiler.compile_elem_match(field_accessor, nested_conditions)
                )
            elif op == "$size":
                conditions.append(f"json_array_length({field_accessor}) = {int(value)}")
            elif op == "$exists":
                conditions.append(
                    SQLiteCompiler.compile_exists(field, value, field_type)
                )
            elif op == "$type":
                conditions.append(SQLiteCompiler.compile_type(field_accessor, value))
            else:
                raise UnsupportedOperatorException(op)

        return conditions

    def _get_field_type(self, field: str, schema: Dict) -> str:
        """
        Get field type from schema, handling nested fields.

        Args:
            field: Field name (may be nested)
            schema: Collection schema

        Returns:
            Field type string
        """
        if "." in field:
            # Nested field - get base field type
            base_field = field.split(".")[0]
            return schema.get(base_field, {}).get("type", "TEXT")
        else:
            return schema.get(field, {}).get("type", "TEXT")

    def _escape_value(self, value: Any) -> str:
        """Escape and format value for SQL query."""
        return SQLiteCompiler.escape_value(value)

    def _validate_query(self, query: Dict[str, Any]) -> None:
        """
        Validate query syntax using QueryValidator.

        Args:
            query: MongoDB-style query to validate

        Raises:
            InvalidQueryException: If query is invalid
            ValidationException: If validation fails
            UnsupportedOperatorException: If unsupported operator found
        """
        QueryValidator.validate_query(query)

    def insert_data(self, collection: str, data: List[Dict[str, Any]]):
        """
        Insert data into collection for testing and canonical data loading.

        Args:
            collection: Collection name
            data: List of documents to insert
        """
        self._validate_collection(collection)
        schema = self.schemas[collection]

        logger.debug("  📥 insert_data: Starting bulk insert for %s (%s docs)", collection, len(data))

        inserted_count = 0
        skipped_count = 0

        for doc_idx, doc in enumerate(data, 1):
            # Build INSERT statement
            fields = []
            values = []

            for field_name, field_spec in schema.items():
                if field_name in doc:
                    fields.append(field_name)

                    # Convert JSON fields to string if not already a string
                    if field_spec.get("type") == "JSON":
                        # If it's already a string (pre-serialized), use it directly
                        # Otherwise, serialize it
                        if isinstance(doc[field_name], str):
                            values.append(doc[field_name])
                        else:
                            values.append(json.dumps(doc[field_name]))
                    else:
                        values.append(doc[field_name])

            if not fields:
                logger.debug("    ⏭️  Doc #%s: Skipped (no matching fields)", doc_idx)
                skipped_count += 1
                continue

            try:
                placeholders = ", ".join(["?" for _ in values])
                insert_sql = f"""
                    INSERT INTO {collection} ({", ".join(fields)})
                    VALUES ({placeholders})
                """

                self.conn.execute(insert_sql, values)
                inserted_count += 1
                logger.debug("    ✓ Doc #%s: Inserted (%s fields)", doc_idx, len(fields))
            except Exception as e:
                # Enhanced error logging with document details
                doc_id = doc.get("id") or doc.get("_id") or "unknown"
                doc_fields = set(doc.keys())
                required_fields = {
                    k
                    for k, v in schema.items()
                    if "NOT NULL" in v.get("constraints", "")
                }
                missing_fields = required_fields - doc_fields

                logger.error("    ❌ [%s] Doc #%s (%s): Insert failed - %s", collection, doc_idx, doc_id, e)
                if missing_fields:
                    logger.error("       Missing required fields: %s", missing_fields)
                logger.error("       Document has: %s", list(doc_fields))
                skipped_count += 1

        logger.debug("  💾 Committing transaction...")
        self.conn.commit()

        logger.debug("  ✨ insert_data complete: %s inserted, %s skipped", inserted_count, skipped_count)


__all__ = ["CanonicalQueryEngine"]
