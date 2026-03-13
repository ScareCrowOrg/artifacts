"""
CRUD operations for JSONDatabase.

Provides insert, find, update, delete operations for JSON document storage.
Handles document serialization/deserialization with Pydantic models.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from .encryption import decrypt_sensitive_fields, encrypt_sensitive_fields

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class CRUDOperations:
    """
    CRUD operations mixin for JSONDatabase.

    Provides methods for creating, reading, updating, and deleting documents.
    """

    def insert(
        self,
        collection: str,
        document: BaseModel,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> str:
        """
        Insert a document into a collection.

        Args:
            collection: Collection name
            document: Pydantic model instance to insert
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            Document ID
        """
        doc_dict = document.model_dump(mode="json")
        doc_id = doc_dict.get("id")

        if not doc_id:
            raise ValueError("Document must have an 'id' field")

        # Encrypt sensitive fields before saving
        doc_dict = encrypt_sensitive_fields(collection, doc_dict)

        doc_path = self._get_document_path(
            collection, doc_id, user_id, session_id, is_canonical
        )

        # Write document with explicit error handling
        try:
            with open(doc_path, "w", encoding="utf-8") as f:
                json.dump(doc_dict, f, indent=2, ensure_ascii=False, default=str)
            return doc_id
        except PermissionError as pe:
            logger.error("PermissionError: Cannot write document %s to %s: %s", doc_id, doc_path, pe)
            raise
        except Exception as e:
            logger.error("Error writing document %s to %s: %s", doc_id, doc_path, e)
            raise

    def find_one(
        self,
        collection: str,
        doc_id: str,
        model_class: Type[T],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by ID.

        Args:
            collection: Collection name
            doc_id: Document ID
            model_class: Pydantic model class to deserialize into
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            Document instance or None if not found
        """
        doc_path = self._get_document_path(
            collection, doc_id, user_id, session_id, is_canonical
        )

        try:
            with open(doc_path, "r", encoding="utf-8") as f:
                doc_dict = json.load(f)

            # Decrypt sensitive fields after loading
            doc_dict = decrypt_sensitive_fields(collection, doc_dict)

            return model_class(**doc_dict)
        except Exception as e:
            logger.error("Error loading document %s: %s", doc_id, e, exc_info=True)
            return None

    def update(
        self,
        collection: str,
        doc_id: str,
        updates: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> bool:
        """
        Update a document.

        Args:
            collection: Collection name
            doc_id: Document ID
            updates: Dictionary of fields to update
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            True if updated, False if not found
        """
        doc_path = self._get_document_path(
            collection, doc_id, user_id, session_id, is_canonical
        )

        try:
            # Read current document
            with open(doc_path, "r", encoding="utf-8") as f:
                doc_dict = json.load(f)

            # Store original for comparison
            original_dict = dict(doc_dict)

            # Encrypt sensitive fields in updates before applying
            updates = encrypt_sensitive_fields(collection, updates)

            # Apply updates
            doc_dict.update(updates)

            # Check if anything actually changed (excluding timestamp)
            has_changes = original_dict != doc_dict

            if not has_changes:
                logger.debug("No changes detected for document %s, skipping update", doc_id)
                return True

            # Update timestamp only if there are actual changes
            doc_dict["dataAtualizacao"] = datetime.utcnow().isoformat()

            # Write back
            with open(doc_path, "w", encoding="utf-8") as f:
                json.dump(doc_dict, f, indent=2, ensure_ascii=False, default=str)

            logger.info("Updated document %s in %s", doc_id, collection)
            return True
        except Exception as e:
            logger.error("Error updating document %s: %s", doc_id, e)
            return False

    def delete(
        self,
        collection: str,
        doc_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> bool:
        """
        Delete a document.

        Args:
            collection: Collection name
            doc_id: Document ID
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            True if deleted, False if not found
        """
        doc_path = self._get_document_path(
            collection, doc_id, user_id, session_id, is_canonical
        )

        try:
            doc_path.unlink()
            return True
        except Exception as e:
            logger.error("Error deleting document %s: %s", doc_id, e)
            return False

    def find_many(
        self,
        collection: str,
        model_class: Type[T],
        user_id: Optional[str] = None,
        is_canonical: bool = False,
        limit: Optional[int] = None,
    ) -> List[T]:
        """
        Find multiple documents in a collection.

        Args:
            collection: Collection name
            model_class: Pydantic model class to deserialize into
            user_id: User ID to filter by (for runtime artifacts)
            is_canonical: Whether to search canonical artifacts
            limit: Maximum number of documents to return

        Returns:
            List of document instances
        """
        collection_path = self._get_collection_path(collection, is_canonical)
        documents = []

        # Define search paths
        if user_id and not is_canonical:
            # Search in user-specific directories
            user_path = collection_path / user_id
            if user_path.exists():
                search_pattern = "**/*.json"
                json_files = list(user_path.glob(search_pattern))
            else:
                json_files = []
        else:
            # Search in collection root and all subdirectories for runtime artifacts
            if not is_canonical:
                json_files = list(collection_path.glob("**/*.json"))
            else:
                json_files = list(collection_path.glob("*.json"))

        # Load documents
        for json_file in json_files:
            if limit and len(documents) >= limit:
                break

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    doc_dict = json.load(f)

                # Decrypt sensitive fields after loading
                doc_dict = decrypt_sensitive_fields(collection, doc_dict)

                documents.append(model_class(**doc_dict))
            except Exception as e:
                logger.error("Error loading %s: %s", json_file, e, exc_info=True)
                continue

        return documents

    def find_by_field(
        self,
        collection: str,
        field: str,
        value: Any,
        model_class: Type[T],
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by a specific field value.

        Args:
            collection: Collection name
            field: Field name to search
            value: Field value to match
            model_class: Pydantic model class
            is_canonical: Whether to search canonical artifacts

        Returns:
            First matching document or None
        """
        all_docs = self.find_many(collection, model_class, is_canonical=is_canonical)

        for doc in all_docs:
            if hasattr(doc, field) and getattr(doc, field) == value:
                return doc

        return None

    def find_by_fields(
        self,
        collection: str,
        fields: Dict[str, Any],
        model_class: Type[T],
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by matching multiple field values.

        Args:
            collection: Collection name
            fields: Dictionary of field names and values to match
            model_class: Pydantic model class
            is_canonical: Whether to search canonical artifacts

        Returns:
            First matching document or None
        """
        all_docs = self.find_many(collection, model_class, is_canonical=is_canonical)

        for doc in all_docs:
            # Check if all fields match
            match = True
            for field, value in fields.items():
                if not hasattr(doc, field):
                    match = False
                    break
                doc_value = getattr(doc, field)
                # Deep comparison for nested objects
                if isinstance(value, dict) and hasattr(doc_value, "model_dump"):
                    doc_value = doc_value.model_dump()
                if doc_value != value:
                    match = False
                    break

            if match:
                return doc

        return None

    def find(
        self,
        collection: str,
        query: Dict[str, Any],
        model_class: Type[T] = None,
        user_id: Optional[str] = None,
        is_canonical: bool = False,
        limit: Optional[int] = None,
    ) -> List[T]:
        """
        Find documents matching a query filter.

        Args:
            collection: Collection name
            query: Dictionary of field names and values to match
            model_class: Pydantic model class to deserialize into
            user_id: User ID to filter by (for runtime artifacts)
            is_canonical: Whether to search canonical artifacts
            limit: Maximum number of documents to return

        Returns:
            List of matching document instances
        """
        all_docs = self.find_many(collection, model_class, user_id, is_canonical, limit)
        results = []

        for doc in all_docs:
            match = True
            for field, value in query.items():
                if not hasattr(doc, field):
                    match = False
                    break

                doc_value = getattr(doc, field)

                # Handle MongoDB query operators
                if isinstance(value, dict):
                    # Support $all operator for array matching
                    if "$all" in value:
                        required = value["$all"]
                        if isinstance(doc_value, list):
                            if not all(item in doc_value for item in required):
                                match = False
                                break
                        else:
                            match = False
                            break
                    else:
                        # Simple dict comparison
                        if doc_value != value:
                            match = False
                            break
                else:
                    # Simple value comparison
                    if doc_value != value:
                        match = False
                        break

            if match:
                results.append(doc)
                if limit and len(results) >= limit:
                    break

        return results
