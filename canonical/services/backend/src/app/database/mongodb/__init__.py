"""
MongoDB module for ScareVerse - Runtime data persistence.

Provides async MongoDB operations compatible with JSONDatabase interface.
Enables transparent migration from file-based to MongoDB storage for runtime data.

Usage:
    from backend.app.database.mongodb import MongoDBOperations, get_mongodb_client

    # Initialize operations
    ops = MongoDBOperations()

    # Insert document
    doc_id = await ops.insert("cells", celula_model)

    # Find document
    celula = await ops.find_one("cells", doc_id, Cell)
"""

from .client import (
    close_mongodb_client,
    get_mongodb_client,
    get_mongodb_database,
    reset_mongodb_client,
)
from .operations import MongoDBOperations

__all__ = [
    "MongoDBOperations",
    "get_mongodb_client",
    "get_mongodb_database",
    "close_mongodb_client",
    "reset_mongodb_client",
]
