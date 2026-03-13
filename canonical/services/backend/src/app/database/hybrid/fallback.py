"""
Fallback and Backward Compatibility Layer for HybridDatabase.

DEPRECATED: These synchronous methods bypass MongoDB enforcement.
Use async methods instead. Synchronous methods will be removed in future versions.
"""

import logging
import warnings
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Import RUNTIME_COLLECTIONS to check for violations
from .collections import RUNTIME_COLLECTIONS


class FallbackMixin:
    """
    Mixin providing fallback and backward compatibility methods.

    DEPRECATED: These synchronous methods bypass MongoDB enforcement for runtime data.
    They should only be used for canonical data or during migration period.
    Use async methods (insert, find_one, update, delete) instead.
    """

    def insert_sync(
        self,
        collection: str,
        document: BaseModel,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> Optional[str]:
        """
        Synchronous insert (backward compatibility).

        DEPRECATED: This method bypasses MongoDB enforcement.
        Use async insert() instead.

        Args:
            collection: Collection name
            document: Pydantic model instance to insert
            user_id: User ID (for runtime data)
            session_id: Session ID (for runtime data)
            is_canonical: Whether this is canonical data

        Returns:
            Document ID or None if insert failed

        Raises:
            RuntimeError: If attempting to insert runtime data synchronously (non-test env)
        """
        # Apply legacy adapter to convert collection names
        collection, document, _ = self._apply_legacy_adapter(collection, document)

        # Check if this is a runtime collection (violates MongoDB-only policy)
        if not is_canonical and collection in RUNTIME_COLLECTIONS:
            # Allow in test environment for backward compatibility
            if not self.is_test_env:
                raise RuntimeError(
                    f"DEPRECATED: Synchronous insert attempted for runtime collection '{collection}'. "
                    f"Runtime data MUST use async methods and MongoDB storage. "
                    f"Use 'db.insert()' instead of 'db.insert_sync()'."
                )

        warnings.warn(
            f"insert_sync() is deprecated. Use async insert() instead. "
            f"Collection: {collection}, is_canonical: {is_canonical}",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning("DEPRECATED: Using synchronous insert for %s - MongoDB operations require async", collection)

        return self._file_db.insert(
            collection=collection,
            document=document,
            user_id=user_id,
            session_id=session_id,
            is_canonical=is_canonical,
        )

    def find_one_sync(
        self,
        collection: str,
        doc_id: str,
        model_class: Optional[Type[T]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Synchronous find_one (backward compatibility).

        DEPRECATED: This method bypasses MongoDB enforcement.
        Use async find_one() instead.

        Args:
            collection: Collection name
            doc_id: Document ID
            model_class: Pydantic model class for deserialization
            user_id: User ID (for runtime data)
            session_id: Session ID (for runtime data)
            is_canonical: Whether this is canonical data

        Returns:
            Document instance or None if not found

        Raises:
            RuntimeError: If attempting to query runtime data synchronously (non-test env)
        """
        if not is_canonical and collection in RUNTIME_COLLECTIONS:
            # Allow in test environment for backward compatibility
            if not self.is_test_env:
                raise RuntimeError(
                    f"DEPRECATED: Synchronous find_one attempted for runtime collection '{collection}'. "
                    f"Runtime data MUST use async methods and MongoDB storage. "
                    f"Use 'db.find_one()' instead of 'db.find_one_sync()'."
                )

        warnings.warn(
            f"find_one_sync() is deprecated. Use async find_one() instead. "
            f"Collection: {collection}",
            DeprecationWarning,
            stacklevel=2,
        )

        return self._file_db.find_one(
            collection=collection,
            doc_id=doc_id,
            model_class=model_class,
            user_id=user_id,
            session_id=session_id,
            is_canonical=is_canonical,
        )

    def find_many_sync(
        self,
        collection: str,
        model_class: Optional[Type[T]] = None,
        user_id: Optional[str] = None,
        is_canonical: bool = False,
        limit: Optional[int] = None,
    ) -> list:
        """
        Synchronous find_many (backward compatibility).

        DEPRECATED: This method bypasses MongoDB enforcement.
        Use async find_many() instead.

        Args:
            collection: Collection name
            model_class: Pydantic model class for deserialization
            user_id: User ID (for runtime data)
            is_canonical: Whether this is canonical data
            limit: Maximum number of documents to return

        Returns:
            List of document instances

        Raises:
            RuntimeError: If attempting to query runtime data synchronously (non-test env)
        """
        if not is_canonical and collection in RUNTIME_COLLECTIONS:
            # Allow in test environment for backward compatibility
            if not self.is_test_env:
                raise RuntimeError(
                    f"DEPRECATED: Synchronous find_many attempted for runtime collection '{collection}'. "
                    f"Runtime data MUST use async methods and MongoDB storage. "
                    f"Use 'db.find_many()' instead of 'db.find_many_sync()'."
                )

        warnings.warn(
            f"find_many_sync() is deprecated. Use async find_many() instead. "
            f"Collection: {collection}",
            DeprecationWarning,
            stacklevel=2,
        )

        return self._file_db.find_many(
            collection=collection,
            model_class=model_class,
            user_id=user_id,
            is_canonical=is_canonical,
            limit=limit,
        )

    def update_sync(
        self,
        collection: str,
        doc_id: str,
        updates: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> bool:
        """
        Synchronous update (backward compatibility).

        DEPRECATED: This method bypasses MongoDB enforcement.
        Use async update() instead.

        Args:
            collection: Collection name
            doc_id: Document ID
            updates: Dictionary of field updates
            user_id: User ID (for runtime data)
            session_id: Session ID (for runtime data)
            is_canonical: Whether this is canonical data

        Returns:
            True if update successful, False otherwise

        Raises:
            RuntimeError: If attempting to update runtime data synchronously (non-test env)
        """
        if not is_canonical and collection in RUNTIME_COLLECTIONS:
            # Allow in test environment for backward compatibility
            if not self.is_test_env:
                raise RuntimeError(
                    f"DEPRECATED: Synchronous update attempted for runtime collection '{collection}'. "
                    f"Runtime data MUST use async methods and MongoDB storage. "
                    f"Use 'db.update()' instead of 'db.update_sync()'."
                )

        warnings.warn(
            f"update_sync() is deprecated. Use async update() instead. "
            f"Collection: {collection}",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning("DEPRECATED: Using synchronous update for %s - MongoDB operations require async", collection)

        return self._file_db.update(
            collection=collection,
            doc_id=doc_id,
            updates=updates,
            user_id=user_id,
            session_id=session_id,
            is_canonical=is_canonical,
        )

    def delete_sync(
        self,
        collection: str,
        doc_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> bool:
        """
        Synchronous delete (backward compatibility).

        DEPRECATED: This method bypasses MongoDB enforcement.
        Use async delete() instead.

        Args:
            collection: Collection name
            doc_id: Document ID
            user_id: User ID (for runtime data)
            session_id: Session ID (for runtime data)
            is_canonical: Whether this is canonical data

        Returns:
            True if delete successful, False otherwise

        Raises:
            RuntimeError: If attempting to delete runtime data synchronously (non-test env)
        """
        if not is_canonical and collection in RUNTIME_COLLECTIONS:
            # Allow in test environment for backward compatibility
            if not self.is_test_env:
                raise RuntimeError(
                    f"DEPRECATED: Synchronous delete attempted for runtime collection '{collection}'. "
                    f"Runtime data MUST use async methods and MongoDB storage. "
                    f"Use 'db.delete()' instead of 'db.delete_sync()'."
                )

        warnings.warn(
            f"delete_sync() is deprecated. Use async delete() instead. "
            f"Collection: {collection}",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning("DEPRECATED: Using synchronous delete for %s - MongoDB operations require async", collection)

        return self._file_db.delete(
            collection=collection,
            doc_id=doc_id,
            user_id=user_id,
            session_id=session_id,
            is_canonical=is_canonical,
        )

    def find_by_field_sync(
        self,
        collection: str,
        field: str,
        value: Any,
        model_class: Optional[Type[T]] = None,
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Synchronous find_by_field (backward compatibility).

        DEPRECATED: This method bypasses MongoDB enforcement.
        Use async find_by_field() instead.

        Args:
            collection: Collection name
            field: Field name to search
            value: Field value to match
            model_class: Pydantic model class for deserialization
            is_canonical: Whether this is canonical data

        Returns:
            First matching document or None

        Raises:
            RuntimeError: If attempting to query runtime data synchronously (non-test env)
        """
        if not is_canonical and collection in RUNTIME_COLLECTIONS:
            # Allow in test environment for backward compatibility
            if not self.is_test_env:
                raise RuntimeError(
                    f"DEPRECATED: Synchronous find_by_field attempted for runtime collection '{collection}'. "
                    f"Runtime data MUST use async methods and MongoDB storage. "
                    f"Use 'db.find_by_field()' instead of 'db.find_by_field_sync()'."
                )

        warnings.warn(
            f"find_by_field_sync() is deprecated. Use async find_by_field() instead. "
            f"Collection: {collection}",
            DeprecationWarning,
            stacklevel=2,
        )

        return self._file_db.find_by_field(
            collection=collection,
            field=field,
            value=value,
            model_class=model_class,
            is_canonical=is_canonical,
        )

    def find(
        self,
        collection: str,
        query: Dict[str, Any],
        model_class: Optional[Type[T]] = None,
        user_id: Optional[str] = None,
        is_canonical: bool = False,
        limit: Optional[int] = None,
    ) -> list:
        """
        Synchronous find (backward compatibility).

        DEPRECATED: This method bypasses MongoDB enforcement.
        Use async find() instead.

        Args:
            collection: Collection name
            query: Query dictionary with field filters
            model_class: Pydantic model class for deserialization
            user_id: User ID (for runtime data)
            is_canonical: Whether this is canonical data
            limit: Maximum number of documents to return

        Returns:
            List of matching documents

        Raises:
            RuntimeError: If attempting to query runtime data synchronously (non-test env)
        """
        if not is_canonical and collection in RUNTIME_COLLECTIONS:
            # Allow in test environment for backward compatibility
            if not self.is_test_env:
                raise RuntimeError(
                    f"DEPRECATED: Synchronous find attempted for runtime collection '{collection}'. "
                    f"Runtime data MUST use async methods and MongoDB storage. "
                    f"Use 'db.find()' (async) instead of 'db.find_sync()'."
                )

        warnings.warn(
            f"find() is deprecated. Use async find() instead. Collection: {collection}",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning("DEPRECATED: Using synchronous find for %s - MongoDB operations require async", collection)

        return self._file_db.find(
            collection=collection,
            query=query,
            model_class=model_class,
            user_id=user_id,
            is_canonical=is_canonical,
            limit=limit,
        )

    def get_config(self, config_key: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration from file-based storage.

        Args:
            config_key: Configuration key

        Returns:
            Configuration dictionary or None
        """
        return self._file_db.get_config(config_key)

    def set_config(self, config_key: str, config_data: Dict[str, Any]) -> bool:
        """
        Set configuration in file-based storage.

        Args:
            config_key: Configuration key
            config_data: Configuration dictionary

        Returns:
            True if set successful
        """
        return self._file_db.set_config(config_key, config_data)
