"""
MongoDB CRUD operations compatible with JSONDatabase interface.

Provides async CRUD operations for MongoDB that mirror the JSONDatabase
interface, enabling transparent migration from file-based to MongoDB storage.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from .client import get_mongodb_database

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _get_db_name(db: Optional[AsyncIOMotorDatabase]) -> str:
    """
    Safely get database name for logging.

    Args:
        db: MongoDB database instance

    Returns:
        Database name or 'No Connection' if not available
    """
    if db is None:
        return "No Connection"
    return getattr(db, "name", "Unknown Database")


class MongoDBOperations:
    """
    MongoDB CRUD operations mixin compatible with JSONDatabase interface.

    Provides async methods for creating, reading, updating, and deleting documents
    in MongoDB collections.
    """

    def __init__(self):
        """Initialize MongoDB operations."""
        self._db: Optional[AsyncIOMotorDatabase] = None

    async def _ensure_db(self) -> Optional[AsyncIOMotorDatabase]:
        """
        Ensure MongoDB database connection.

        Returns:
            Database instance or None if unavailable
        """
        if self._db is None:
            self._db = await get_mongodb_database()
            if self._db is not None:  # Explicit comparison with None
                logger.info("MongoDB database connection established: %s", _get_db_name(self._db))
            else:
                logger.warning("MongoDB database connection failed - database is None")
        return self._db

    def _get_collection_name(self, collection: str, _is_canonical: bool = False) -> str:
        """
        Get MongoDB collection name.

        Args:
            collection: Base collection name
            is_canonical: Whether this is canonical data (not used for MongoDB)

        Returns:
            Collection name with runtime suffix
        """
        # MongoDB stores only runtime data
        # Canonical data remains in file system
        return f"{collection}_runtime"

    async def insert(
        self,
        collection: str,
        document: BaseModel,
        _user_id: Optional[str] = None,
        _session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> Optional[str]:
        """
        Insert a document into MongoDB collection.

        Args:
            collection: Collection name
            document: Pydantic model instance to insert
            user_id: User ID (for context)
            session_id: Session ID (for context)
            is_canonical: Ignored for MongoDB (canonical data stays in files)

        Returns:
            Document ID

        Raises:
            RuntimeError: If MongoDB is not available or insert fails
        """
        if is_canonical:
            # Canonical data is not stored in MongoDB
            logger.debug("Skipping MongoDB insert for canonical document in %s", collection)
            raise ValueError(
                f"Attempted to insert canonical data into MongoDB collection '{collection}'. "
                f"Canonical data must be stored in file system only."
            )

        db = await self._ensure_db()
        if db is None:
            raise RuntimeError(
                f"MongoDB database not available for collection '{collection}'. "
                f"Cannot insert runtime data without MongoDB connection."
            )

        collection_name = self._get_collection_name(collection, is_canonical)

        # Serialize Pydantic model to dictionary
        try:
            doc_dict = document.model_dump(mode="json")
            doc_id = doc_dict.get("id")

            if not doc_id:
                raise ValueError("Document must have an 'id' field")

            # Only add updated_at if not already present (created_at should come from model)
            if "updated_at" not in doc_dict:
                doc_dict["updated_at"] = datetime.utcnow()

            # Ensure created_at is present
            if "created_at" not in doc_dict:
                doc_dict["created_at"] = datetime.utcnow()

        except Exception as e:
            # Model serialization errors
            logger.error("MongoDB insert document serialization FAILED:\n  Collection: '%s'\n  Model class: %s\n  Error type: %s\n  Error: %s", collection_name, type(document).__name__, type(e).__name__, e)
            raise RuntimeError(
                f"Failed to serialize {type(document).__name__} for MongoDB insert in '{collection_name}': "
                f"{type(e).__name__}: {str(e)}"
            ) from e

        # Execute MongoDB insert operation
        try:
            logger.debug(
                "MongoDB insert: collection='%s', doc_id='%s', db=%s",
                collection_name, doc_id, _get_db_name(db)
            )

            result = await db[collection_name].insert_one(doc_dict)

            logger.debug("MongoDB insert: Successfully inserted document '%s' into '%s'", doc_id, collection_name)
            return doc_id

        except Exception as e:
            # MongoDB operation errors
            logger.error("MongoDB insert operation FAILED:\n  Collection (input): '%s'\n  Collection (actual): '%s'\n  Document ID: '%s'\n  Database: %s\n  Error type: %s\n  Error: %s", collection, collection_name, doc_id, _get_db_name(db), type(e).__name__, e)
            raise RuntimeError(
                f"MongoDB insert failed for collection '{collection_name}': {type(e).__name__}: {str(e)}"
            ) from e

    async def find_one(
        self,
        collection: str,
        doc_id: str,
        model_class: Type[T],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by ID in MongoDB.

        Args:
            collection: Collection name
            doc_id: Document ID
            model_class: Pydantic model class to deserialize into
            user_id: User ID (for filtering)
            session_id: Session ID (for filtering)
            is_canonical: Ignored for MongoDB

        Returns:
            Document instance or None if not found

        Raises:
            RuntimeError: If MongoDB is not available
        """
        if is_canonical:
            # Canonical data is not in MongoDB
            return None

        db = await self._ensure_db()
        if db is None:
            raise RuntimeError(
                f"MongoDB database not available for collection '{collection}'. "
                f"Cannot query runtime data without MongoDB connection."
            )

        collection_name = self._get_collection_name(collection, is_canonical)

        # Build query
        query = {"id": doc_id}

        # Add optional filters
        if user_id:
            query["user_id"] = user_id
        if session_id:
            query["session_id"] = session_id

        logger.debug("MongoDB find_one: collection='%s', query=%s, db=%s", collection_name, query, _get_db_name(db))

        try:
            # Query MongoDB
            doc_dict = await db[collection_name].find_one(query)

            if doc_dict is None:
                logger.debug("MongoDB find_one: No document found in '%s' with query %s", collection_name, query)
                return None

            # Remove MongoDB _id field
            doc_dict.pop("_id", None)

        except Exception as e:
            # MongoDB query/connection errors
            logger.error("MongoDB find_one query FAILED:\n  Collection (input): '%s'\n  Collection (actual): '%s'\n  Document ID: '%s'\n  Query: %s\n  Database: %s\n  Error type: %s\n  Error: %s", collection, collection_name, doc_id, query, _get_db_name(db), type(e).__name__, e)
            raise RuntimeError(
                f"MongoDB query failed for collection '{collection_name}': {type(e).__name__}: {str(e)}"
            ) from e

        # Try to instantiate the model
        try:
            logger.debug(
                "MongoDB find_one: Successfully retrieved document from '%s', instantiating model",
                collection_name
            )
            return model_class(**doc_dict)
        except Exception as e:
            # Pydantic validation errors
            logger.error("MongoDB find_one model instantiation FAILED:\n  Collection: '%s'\n  Document ID: '%s'\n  Model class: %s\n  Document data keys: %s\n  Error type: %s\n  Error: %s", collection_name, doc_id, model_class.__name__, list(doc_dict.keys()), type(e).__name__, e)
            raise RuntimeError(
                f"Failed to instantiate {model_class.__name__} from MongoDB document in '{collection_name}': "
                f"{type(e).__name__}: {str(e)}"
            ) from e

    async def update(
        self,
        collection: str,
        doc_id: str,
        updates: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> bool:
        """
        Update a document in MongoDB.

        Args:
            collection: Collection name
            doc_id: Document ID
            updates: Dictionary of fields to update
            user_id: User ID (for filtering)
            session_id: Session ID (for filtering)
            is_canonical: Ignored for MongoDB

        Returns:
            True if updated, False if not found

        Raises:
            RuntimeError: If MongoDB is not available or update fails
        """
        if is_canonical:
            raise ValueError(
                f"Attempted to update canonical data in MongoDB collection '{collection}'. "
                f"Canonical data must be stored in file system only."
            )

        db = await self._ensure_db()
        if db is None:
            raise RuntimeError(
                f"MongoDB database not available for collection '{collection}'. "
                f"Cannot update runtime data without MongoDB connection."
            )

        collection_name = self._get_collection_name(collection, is_canonical)

        # Build query and updates
        query = {"id": doc_id}

        # Add optional filters
        if user_id:
            query["user_id"] = user_id
        if session_id:
            query["session_id"] = session_id

        # Add updated timestamp
        updates["updated_at"] = datetime.utcnow()

        logger.debug(
            "MongoDB update: collection='%s', doc_id='%s', query=%s, db=%s",
            collection_name, doc_id, query, _get_db_name(db)
        )

        # Execute MongoDB update operation
        try:
            result = await db[collection_name].update_one(query, {"$set": updates})

            if result.modified_count > 0:
                logger.debug("MongoDB update: Successfully updated document '%s' in '%s'", doc_id, collection_name)
                return True

            logger.debug("MongoDB update: No document found to update in '%s' with query %s", collection_name, query)
            return False

        except Exception as e:
            # MongoDB operation errors
            logger.error("MongoDB update operation FAILED:\n  Collection (input): '%s'\n  Collection (actual): '%s'\n  Document ID: '%s'\n  Updates: %s\n  Query: %s\n  Database: %s\n  Error type: %s\n  Error: %s", collection, collection_name, doc_id, updates, query, _get_db_name(db), type(e).__name__, e)
            raise RuntimeError(
                f"MongoDB update failed for collection '{collection_name}': {type(e).__name__}: {str(e)}"
            ) from e

    async def delete(
        self,
        collection: str,
        doc_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> bool:
        """
        Delete a document from MongoDB.

        Args:
            collection: Collection name
            doc_id: Document ID
            user_id: User ID (for filtering)
            session_id: Session ID (for filtering)
            is_canonical: Ignored for MongoDB

        Returns:
            True if deleted, False if not found

        Raises:
            RuntimeError: If MongoDB is not available or delete fails
        """
        if is_canonical:
            raise ValueError(
                f"Attempted to delete canonical data from MongoDB collection '{collection}'. "
                f"Canonical data must be stored in file system only."
            )

        db = await self._ensure_db()
        if db is None:
            raise RuntimeError(
                f"MongoDB database not available for collection '{collection}'. "
                f"Cannot delete runtime data without MongoDB connection."
            )

        collection_name = self._get_collection_name(collection, is_canonical)

        # Build query
        query = {"id": doc_id}

        # Add optional filters
        if user_id:
            query["user_id"] = user_id
        if session_id:
            query["session_id"] = session_id

        logger.debug(
            "MongoDB delete: collection='%s', doc_id='%s', query=%s, db=%s",
            collection_name, doc_id, query, _get_db_name(db)
        )

        # Execute MongoDB delete operation
        try:
            result = await db[collection_name].delete_one(query)

            if result.deleted_count > 0:
                logger.debug("MongoDB delete: Successfully deleted document '%s' from '%s'", doc_id, collection_name)
                return True

            logger.debug("MongoDB delete: No document found to delete in '%s' with query %s", collection_name, query)
            return False

        except Exception as e:
            # MongoDB operation errors
            logger.error("MongoDB delete operation FAILED:\n  Collection (input): '%s'\n  Collection (actual): '%s'\n  Document ID: '%s'\n  Query: %s\n  Database: %s\n  Error type: %s\n  Error: %s", collection, collection_name, doc_id, query, _get_db_name(db), type(e).__name__, e)
            raise RuntimeError(
                f"MongoDB delete failed for collection '{collection_name}': {type(e).__name__}: {str(e)}"
            ) from e

    async def find_many(
        self,
        collection: str,
        model_class: Type[T],
        user_id: Optional[str] = None,
        is_canonical: bool = False,
        limit: Optional[int] = None,
    ) -> List[T]:
        """
        Find multiple documents in MongoDB collection.

        Args:
            collection: Collection name
            model_class: Pydantic model class to deserialize into
            user_id: User ID to filter by
            is_canonical: Ignored for MongoDB
            limit: Maximum number of documents to return

        Returns:
            List of document instances

        Raises:
            RuntimeError: If MongoDB is not available
        """
        if is_canonical:
            return []

        db = await self._ensure_db()
        if db is None:
            raise RuntimeError(
                f"MongoDB database not available for collection '{collection}'. "
                f"Cannot query runtime data without MongoDB connection."
            )

        collection_name = self._get_collection_name(collection, is_canonical)
        query = {}

        if user_id:
            query["user_id"] = user_id

        logger.debug("MongoDB find_many: collection='%s', query=%s, limit=%s", collection_name, query, limit)

        try:
            cursor = db[collection_name].find(query)

            if limit:
                cursor = cursor.limit(limit)

            documents = []
            async for doc_dict in cursor:
                # Remove MongoDB _id field
                doc_dict.pop("_id", None)
                try:
                    documents.append(model_class(**doc_dict))
                except Exception as e:
                    logger.error(
                        "MongoDB find_many: Failed to instantiate %s from document in '%s': %s: %s",
                        model_class.__name__, collection_name, type(e).__name__, e
                    )
                    logger.debug("  Document data keys: %s", list(doc_dict.keys()))
                    continue

            logger.debug("MongoDB find_many: Retrieved %s documents from '%s'", len(documents), collection_name)
            return documents

        except Exception as e:
            logger.error("MongoDB find_many query FAILED:\n  Collection: '%s'\n  Query: %s\n  Database: %s\n  Error type: %s\n  Error: %s", collection_name, query, _get_db_name(db), type(e).__name__, e)
            return []

    async def find_by_field(
        self,
        collection: str,
        field: str,
        value: Any,
        model_class: Type[T],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by a specific field value in MongoDB.

        Args:
            collection: Collection name
            field: Field name to search
            value: Field value to match
            model_class: Pydantic model class
            user_id: User ID (for filtering)
            session_id: Session ID (for filtering)
            is_canonical: Ignored for MongoDB

        Returns:
            First matching document or None
        """
        if is_canonical:
            return None

        db = await self._ensure_db()
        if db is None:
            logger.warning("MongoDB database not available for find_by_field on collection '%s'", collection)
            return None

        collection_name = self._get_collection_name(collection, is_canonical)

        # Build query
        query = {field: value}

        # Add optional filters
        if user_id:
            query["user_id"] = user_id
        if session_id:
            query["session_id"] = session_id

        logger.debug(
            "MongoDB find_by_field: collection='%s', field='%s', query=%s, db=%s",
            collection_name, field, query, _get_db_name(db)
        )

        try:
            # Query MongoDB
            doc_dict = await db[collection_name].find_one(query)

            if doc_dict is None:
                logger.debug("MongoDB find_by_field: No document found in '%s' with query %s", collection_name, query)
                return None

            # Remove MongoDB _id field
            doc_dict.pop("_id", None)

        except Exception as e:
            # MongoDB query/connection errors
            logger.error("MongoDB find_by_field query FAILED:\n  Collection (input): '%s'\n  Collection (actual): '%s'\n  Field: '%s'\n  Value: '%s'\n  Query: %s\n  Database: %s\n  Error type: %s\n  Error: %s", collection, collection_name, field, value, query, _get_db_name(db), type(e).__name__, e)
            raise RuntimeError(
                f"MongoDB query failed for collection '{collection_name}': {type(e).__name__}: {str(e)}"
            ) from e

        # Try to instantiate the model
        try:
            logger.debug(
                "MongoDB find_by_field: Successfully retrieved document from '%s', instantiating model",
                collection_name
            )
            return model_class(**doc_dict)
        except Exception as e:
            # Pydantic validation errors
            logger.error("MongoDB find_by_field model instantiation FAILED:\n  Collection: '%s'\n  Field: '%s'\n  Value: '%s'\n  Model class: %s\n  Document data keys: %s\n  Error type: %s\n  Error: %s", collection_name, field, value, model_class.__name__, list(doc_dict.keys()), type(e).__name__, e)
            raise RuntimeError(
                f"Failed to instantiate {model_class.__name__} from MongoDB document in '{collection_name}': "
                f"{type(e).__name__}: {str(e)}"
            ) from e

    async def find_by_fields(
        self,
        collection: str,
        fields: Dict[str, Any],
        model_class: Type[T],
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by matching multiple field values in MongoDB.

        Args:
            collection: Collection name
            fields: Dictionary of field names and values to match
            model_class: Pydantic model class
            is_canonical: Ignored for MongoDB

        Returns:
            First matching document or None
        """
        if is_canonical:
            return None

        db = await self._ensure_db()
        if db is None:
            logger.warning("MongoDB database not available for find_by_fields on collection '%s'", collection)
            return None

        collection_name = self._get_collection_name(collection, is_canonical)

        try:
            # Query MongoDB
            doc_dict = await db[collection_name].find_one(fields)

            if doc_dict is None:
                logger.debug(
                    "MongoDB find_by_fields: No document found in '%s' with fields %s",
                    collection_name, fields
                )
                return None

            # Remove MongoDB _id field
            doc_dict.pop("_id", None)

        except Exception as e:
            # MongoDB query/connection errors
            logger.error("MongoDB find_by_fields query FAILED:\n  Collection: '%s'\n  Fields: %s\n  Database: %s\n  Error type: %s\n  Error: %s", collection_name, fields, _get_db_name(db), type(e).__name__, e)
            raise RuntimeError(
                f"MongoDB query failed for collection '{collection_name}': {type(e).__name__}: {str(e)}"
            ) from e

        # Try to instantiate the model
        try:
            logger.debug(
                "MongoDB find_by_fields: Successfully retrieved document from '%s', instantiating model",
                collection_name
            )
            return model_class(**doc_dict)
        except Exception as e:
            # Pydantic validation errors
            logger.error("MongoDB find_by_fields model instantiation FAILED:\n  Collection: '%s'\n  Fields: %s\n  Model class: %s\n  Document data keys: %s\n  Error type: %s\n  Error: %s", collection_name, fields, model_class.__name__, list(doc_dict.keys()), type(e).__name__, e)
            raise RuntimeError(
                f"Failed to instantiate {model_class.__name__} from MongoDB document in '{collection_name}': "
                f"{type(e).__name__}: {str(e)}"
            ) from e

    async def find(
        self,
        collection: str,
        query: Dict[str, Any],
        model_class: Optional[Type[T]] = None,
        user_id: Optional[str] = None,
        is_canonical: bool = False,
        limit: Optional[int] = None,
    ) -> List[T]:
        """
        Find documents matching a query filter in MongoDB.

        Args:
            collection: Collection name
            query: Dictionary of field names and values to match (supports MongoDB operators like $all)
            model_class: Pydantic model class to deserialize into
            user_id: User ID to filter by (optional)
            is_canonical: Ignored for MongoDB
            limit: Maximum number of documents to return

        Returns:
            List of matching document instances

        Raises:
            RuntimeError: If MongoDB is not available or query fails
        """
        if is_canonical:
            return []

        db = await self._ensure_db()
        if db is None:
            raise RuntimeError(
                f"MongoDB database not available for collection '{collection}'. "
                f"Cannot query runtime data without MongoDB connection."
            )

        collection_name = self._get_collection_name(collection, is_canonical)

        # Add user_id to query if provided
        mongo_query = dict(query)
        if user_id:
            mongo_query["user_id"] = user_id

        logger.debug("MongoDB find: collection='%s', query=%s, limit=%s", collection_name, mongo_query, limit)

        try:
            cursor = db[collection_name].find(mongo_query)

            if limit:
                cursor = cursor.limit(limit)

            documents = []
            async for doc_dict in cursor:
                # Remove MongoDB _id field
                doc_dict.pop("_id", None)
                try:
                    documents.append(model_class(**doc_dict))
                except Exception as e:
                    logger.error(
                        "MongoDB find: Failed to instantiate %s from document in '%s': %s: %s",
                        model_class.__name__, collection_name, type(e).__name__, e
                    )
                    logger.debug("  Document data keys: %s", list(doc_dict.keys()))
                    continue

            logger.debug("MongoDB find: Retrieved %s documents from '%s'", len(documents), collection_name)
            return documents

        except Exception as e:
            logger.error("MongoDB find query FAILED:\n  Collection: '%s'\n  Query: %s\n  Database: %s\n  Error type: %s\n  Error: %s", collection_name, mongo_query, _get_db_name(db), type(e).__name__, e)
            raise RuntimeError(
                f"MongoDB query failed for collection '{collection_name}': {type(e).__name__}: {str(e)}"
            ) from e
