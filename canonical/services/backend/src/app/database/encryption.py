"""
Encryption utilities for sensitive data in JSONDatabase.

Handles encryption/decryption of sensitive fields (e.g., API keys) in documents.
Uses ENCRYPTION_KEY environment variable for symmetric encryption.
"""

import logging
from typing import Any, Dict

from ..crypto_utils import decrypt_value, encrypt_value, is_encryption_configured

logger = logging.getLogger(__name__)


def encrypt_sensitive_fields(
    collection: str, doc_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Encrypt sensitive fields in a document before saving.

    Args:
        collection: Collection name
        doc_dict: Document dictionary

    Returns:
        Document dictionary with encrypted sensitive fields
    """
    # Only encrypt for ai_models collection
    logger.debug("Processing collection for encryption: %s", collection)

    if collection != "ai_models":
        return doc_dict

    logger.debug("Collection is ai_models, attempting encryption: %s", collection)
    # Check if encryption is configured
    if not is_encryption_configured():
        logger.warning("ENCRYPTION_KEY not configured - apiKey will not be encrypted")
        return doc_dict

    logger.debug("ENCRYPTION_KEY configured for collection: %s, doc_id: %s", collection, doc_dict.get('id'))
    # Encrypt apiKey field if present
    if "apiKey" in doc_dict and doc_dict["apiKey"]:
        logger.debug("Found apiKey to encrypt in collection: %s", collection)
        try:
            doc_dict["apiKey"] = encrypt_value(doc_dict["apiKey"])
            logger.debug("Encrypted apiKey for document %s", doc_dict.get('id'))
        except Exception as e:
            logger.error("Failed to encrypt apiKey: %s", e)
            raise ValueError(f"Failed to encrypt apiKey: {e}") from e

    return doc_dict


def decrypt_sensitive_fields(
    collection: str, doc_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Decrypt sensitive fields in a document after loading.

    Args:
        collection: Collection name
        doc_dict: Document dictionary

    Returns:
        Document dictionary with decrypted sensitive fields
    """

    # Only decrypt for ai_models collection
    if collection != "ai_models":
        return doc_dict

    # Check if encryption is configured
    if not is_encryption_configured():
        logger.warning("ENCRYPTION_KEY not configured - apiKey cannot be decrypted")
        return doc_dict

    # Decrypt apiKey field if present
    if "apiKey" in doc_dict and doc_dict["apiKey"]:
        try:
            doc_dict["apiKey"] = decrypt_value(doc_dict["apiKey"])
            logger.debug("Decrypted apiKey for document %s", doc_dict.get('id'))
        except Exception as e:
            logger.warning(
                f"Failed to decrypt apiKey for document {doc_dict.get('id')}: {e}. "
                "This may indicate key rotation, data corruption, or wrong ENCRYPTION_KEY. "
                "Setting apiKey to None."
            )
            # Set to None to allow system to continue but signal problem
            doc_dict["apiKey"] = None

    return doc_dict
