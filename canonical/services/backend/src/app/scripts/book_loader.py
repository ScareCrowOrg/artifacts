"""
Helper functions for loading Book definitions from JSON files.

This module provides utilities to load and process Book definitions
from the canonical artifacts directory structure.

Technical naming: All functions and variables in English (Rule 4.3).
"""

import json
import logging
from pathlib import Path
from typing import List

from app.database import db
from app.models import Book, BookType, NotebookItemType

logger = logging.getLogger(__name__)


async def load_books_from_directory(
    books_dir: Path, book_type_id: str = "book-type-generic-v1"
) -> List[Book]:
    """
    Load Book instances from JSON files in a directory.

    Args:
        books_dir: Path to directory containing Book JSON files
        book_type_id: Default NotebookItemType ID for books

    Returns:
        List of created/existing Book instances
    """
    books_data = []

    if not books_dir.exists():
        logger.warning("Directory not found: %s", books_dir)
        return []

    for json_file in books_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                spec = json.load(f)

            # Check if book already exists
            book_id = spec.get("id")
            if not book_id:
                logger.warning("Book '%s' without ID, skipping...", json_file.name)
                continue

            existing_book = await db.find_one("books", book_id, Book, is_canonical=True)

            if existing_book:
                logger.info("Book '%s' already exists: %s", existing_book.name, existing_book.id)
                # Check if any field actually changed before updating
                updates = {
                    "name": spec.get("name", existing_book.name),
                    "description": spec.get("description", existing_book.description),
                    "notebook_item_type_id": spec.get(
                        "notebook_item_type_id", book_type_id
                    ),
                    "is_canonical": spec.get("is_canonical", True),
                    "is_canonical_system_book": spec.get(
                        "is_canonical_system_book", False
                    ),
                }
                # Only update if there are actual content changes (ignore timestamp fields)
                has_changes = any(
                    updates.get(key) != getattr(existing_book, key, None)
                    for key in updates.keys()
                    if key not in {"created_at", "updated_at", "createdAt", "updatedAt"}
                )
                if has_changes:
                    await db.update("books", book_id, updates, is_canonical=True)
                    books_data.append(
                        await db.find_one("books", book_id, Book, is_canonical=True)
                    )
                else:
                    logger.debug("Book '%s' content unchanged, skipping update", existing_book.name)
                    books_data.append(existing_book)
            else:
                # Create new book from JSON spec
                book = await create_book_from_spec(spec, book_type_id)
                await db.insert("books", book, current_user=SYSTEM_USER)
                logger.info("Book '%s' created: %s", book.name, book.id)
                books_data.append(book)
        except Exception as e:
            logger.error("Error processing Book '%s': %s", json_file.name, e)

    return books_data


async def create_book_from_spec(spec: dict, default_book_type_id: str) -> Book:
    """
    Create a Book instance from a JSON specification.

    Args:
        spec: Dictionary loaded from JSON file
        default_book_type_id: Default NotebookItemType ID for books

    Returns:
        Book instance
    """
    book_data = {
        "id": spec.get("id"),
        "assignee_id": spec.get("assignee_id", "system"),
        "notebook_item_type_id": spec.get(
            "notebook_item_type_id", default_book_type_id
        ),
        "name": spec.get("name", "Book Without Name"),
        "description": spec.get("description", ""),
        "type": BookType[spec.get("type", spec.get("tipo", "VOLATILE"))],
        "purpose": spec.get("purpose", spec.get("intencao", "")),
        "cells": spec.get("cells", []),
        "is_canonical": spec.get("is_canonical", True),
        "is_canonical_system_book": spec.get("is_canonical_system_book", False),
    }

    book = Book(**book_data)

    # Apply default_initial_data from NotebookItemType if exists
    book_type = await db.find_one(
        "notebook_item_types",
        book_data["notebook_item_type_id"],
        NotebookItemType,
        is_canonical=True,
    )
    if book_type and book_type.default_initial_data:
        # Merge default_initial_data into initial_data
        for key, value in book_type.default_initial_data.items():
            if key not in book.initial_data:
                book.initial_data[key] = value

    # Apply default_refs from NotebookItemType if exists
    if book_type and book_type.default_refs:
        # Merge default_refs into refs
        for ref_type, ref_list in book_type.default_refs.items():
            if ref_type not in book.refs:
                book.refs[ref_type] = ref_list

    return book
