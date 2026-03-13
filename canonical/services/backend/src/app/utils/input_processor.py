"""
Input Processor Module for RAG Context Management

This module handles processing user input with priority-based RAG context:
1. Priority 1: Attached files from UI (highest priority)
2. Priority 2: File references using #caminho/do/arquivo syntax
3. Priority 3: General RAG search across BASE_DIR

Technical naming: All functions and variables in English.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from ..config import BASE_DIR

logger = logging.getLogger(__name__)

# Regex pattern for file references: #caminho/do/arquivo.ext
FILE_REFERENCE_PATTERN = r"#([\w\-./]+\.\w+)"

# Default number of RAG results to retrieve
DEFAULT_RAG_K = 5


def extract_file_references(message: str) -> List[str]:
    """
    Extract file references from user message.

    File references follow the pattern: #caminho/do/arquivo.ext

    Args:
        message: User's message

    Returns:
        List of file paths referenced (without # prefix)

    Example:
        >>> extract_file_references("Check #docs/README.md and #backend/app/config.py")
        ['docs/README.md', 'backend/app/config.py']
    """
    matches = re.findall(FILE_REFERENCE_PATTERN, message)
    return matches


def remove_file_references(message: str) -> str:
    """
    Remove file reference markers from message.

    Args:
        message: User's message with file references

    Returns:
        Message with file references removed

    Example:
        >>> remove_file_references("Check #docs/README.md for info")
        'Check  for info'
    """
    return re.sub(FILE_REFERENCE_PATTERN, "", message)


def load_file_content(file_path: str) -> Optional[str]:
    """
    Load content of a local file.

    Uses file_ops_router logic for file reading.

    Args:
        file_path: Relative path from BASE_DIR

    Returns:
        File content as string, or None if loading failed
    """
    try:
        full_path = BASE_DIR / file_path

        if not full_path.exists():
            logger.warning("File not found: %s", file_path)
            return None

        if not full_path.is_file():
            logger.warning("Path is not a file: %s", file_path)
            return None

        # Try to read as text
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info("Loaded file: %s (%s chars)", file_path, len(content))
            return content
        except UnicodeDecodeError:
            logger.warning("Cannot read binary file: %s", file_path)
            return None

    except Exception as e:
        logger.error("Error loading file %s: %s", file_path, e)
        return None


def process_attached_files(
    attached_files: List[Dict[str, Any]],
    user_message: str,
    vectorstore: Optional[Chroma] = None,
    k: int = DEFAULT_RAG_K,
) -> List[Document]:
    """
    Process attached files from UI (Priority 1).

    For each attached file:
    1. Load the file content
    2. Perform RAG search in vector store using user_message as query
    3. Return relevant chunks from those files

    Args:
        attached_files: List of dicts with file info (e.g., [{'path': '...', 'content': '...'}])
        user_message: User's message for context
        vectorstore: ChromaDB vector store (optional)
        k: Number of documents to retrieve per file

    Returns:
        List of Document objects with relevant content

    Note:
        If vectorstore is None, returns the full file contents as documents.
        Expected format for attached_files:
        [
            {'path': 'relative/path/to/file.txt', 'content': 'file content'},
            ...
        ]
    """
    context_documents = []

    if not attached_files:
        return context_documents

    logger.info("Processing %s attached file(s) (Priority 1)", len(attached_files))

    for file_info in attached_files:
        file_path = file_info.get("path", "")
        file_content = file_info.get("content")

        if not file_content and file_path:
            # Try to load from path
            file_content = load_file_content(file_path)

        if not file_content:
            logger.warning("No content for attached file: %s", file_path)
            continue

        if vectorstore:
            # Perform RAG search focused on this file
            try:
                # Search with filter for this specific file
                results = vectorstore.similarity_search(
                    query=user_message,
                    k=k,
                    filter={"source": file_path} if file_path else None,
                )

                if results:
                    logger.info("Found %s relevant chunks from %s", len(results), file_path)
                    context_documents.extend(results)
                else:
                    # If no results from RAG, include file content directly
                    logger.info("No RAG results for %s, using full content", file_path)
                    doc = Document(
                        page_content=file_content[
                            :2000
                        ],  # Limit to avoid token overflow
                        metadata={"source": file_path, "type": "attached_file"},
                    )
                    context_documents.append(doc)

            except Exception as e:
                logger.error("Error in RAG search for %s: %s", file_path, e)
                # Fall back to direct content
                doc = Document(
                    page_content=file_content[:2000],
                    metadata={"source": file_path, "type": "attached_file"},
                )
                context_documents.append(doc)
        else:
            # No vector store, just return content
            doc = Document(
                page_content=file_content[:2000],
                metadata={"source": file_path, "type": "attached_file"},
            )
            context_documents.append(doc)

    logger.info("Priority 1: Retrieved %s document(s) from attached files", len(context_documents))
    return context_documents


def process_file_references(
    file_paths: List[str],
    user_message: str,
    vectorstore: Optional[Chroma] = None,
    k: int = DEFAULT_RAG_K,
) -> List[Document]:
    """
    Process file references from message (Priority 2).

    For each referenced file:
    1. Load the file content
    2. Perform RAG search in vector store using user_message as query
    3. Return relevant chunks from those files

    Args:
        file_paths: List of file paths referenced in message
        user_message: User's message for context
        vectorstore: ChromaDB vector store (optional)
        k: Number of documents to retrieve per file

    Returns:
        List of Document objects with relevant content
    """
    context_documents = []

    if not file_paths:
        return context_documents

    logger.info("Processing %s file reference(s) (Priority 2)", len(file_paths))

    for file_path in file_paths:
        # Load file content
        file_content = load_file_content(file_path)

        if not file_content:
            logger.warning("Could not load referenced file: %s", file_path)
            continue

        if vectorstore:
            # Perform RAG search focused on this file
            try:
                results = vectorstore.similarity_search(
                    query=user_message, k=k, filter={"source": file_path}
                )

                if results:
                    logger.info("Found %s relevant chunks from %s", len(results), file_path)
                    context_documents.extend(results)
                else:
                    # If no results, include file content directly
                    logger.info("No RAG results for %s, using full content", file_path)
                    doc = Document(
                        page_content=file_content[:2000],
                        metadata={"source": file_path, "type": "file_reference"},
                    )
                    context_documents.append(doc)

            except Exception as e:
                logger.error("Error in RAG search for %s: %s", file_path, e)
                # Fall back to direct content
                doc = Document(
                    page_content=file_content[:2000],
                    metadata={"source": file_path, "type": "file_reference"},
                )
                context_documents.append(doc)
        else:
            # No vector store, just return content
            doc = Document(
                page_content=file_content[:2000],
                metadata={"source": file_path, "type": "file_reference"},
            )
            context_documents.append(doc)

    logger.info("Priority 2: Retrieved %s document(s) from file references", len(context_documents))
    return context_documents


def process_general_rag_search(
    user_message: str, vectorstore: Optional[Chroma] = None, k: int = DEFAULT_RAG_K
) -> List[Document]:
    """
    Perform general RAG search across BASE_DIR (Priority 3).

    Args:
        user_message: User's message as search query
        vectorstore: ChromaDB vector store (required)
        k: Number of documents to retrieve

    Returns:
        List of Document objects with relevant content
    """
    context_documents = []

    if not vectorstore:
        logger.warning("No vector store available for general RAG search")
        return context_documents

    logger.info("Performing general RAG search (Priority 3)")

    try:
        # General similarity search without filters
        results = vectorstore.similarity_search(query=user_message, k=k)

        if results:
            logger.info("Found %s relevant chunks from general search", len(results))
            context_documents.extend(results)
        else:
            logger.info("No results from general RAG search")

    except Exception as e:
        logger.error("Error in general RAG search: %s", e)

    logger.info("Priority 3: Retrieved %s document(s) from general search", len(context_documents))
    return context_documents


def process_user_input(
    user_message: str,
    attached_files: Optional[List[Dict[str, Any]]] = None,
    vectorstore: Optional[Chroma] = None,
    k: int = DEFAULT_RAG_K,
) -> Tuple[str, List[Document]]:
    """
    Process user input with priority-based RAG context.

    Priority order:
    1. Attached files from UI (highest)
    2. File references using #caminho/do/arquivo syntax
    3. General RAG search across BASE_DIR

    Args:
        user_message: User's message
        attached_files: List of attached files from UI (optional)
        vectorstore: ChromaDB vector store (optional)
        k: Number of documents to retrieve per search

    Returns:
        Tuple of (processed_message, context_documents)
        - processed_message: Message with file references removed
        - context_documents: List of relevant Document objects

    Example:
        >>> message = "Analyze #docs/README.md"
        >>> processed_msg, docs = process_user_input(message, vectorstore=vs)
        >>> print(processed_msg)  # "Analyze "
        >>> print(len(docs))  # Number of relevant chunks
    """
    context_documents = []

    # Priority 1: Attached files
    if attached_files:
        logger.info("Priority 1: Processing attached files")
        attached_docs = process_attached_files(
            attached_files=attached_files,
            user_message=user_message,
            vectorstore=vectorstore,
            k=k,
        )
        context_documents.extend(attached_docs)

    # Priority 2: File references (only if no attached files)
    if not attached_files:
        file_references = extract_file_references(user_message)

        if file_references:
            logger.info("Priority 2: Processing %s file reference(s)", len(file_references))
            ref_docs = process_file_references(
                file_paths=file_references,
                user_message=user_message,
                vectorstore=vectorstore,
                k=k,
            )
            context_documents.extend(ref_docs)

            # Remove file references from message
            user_message = remove_file_references(user_message).strip()

    # Priority 3: General RAG search (if no higher priority context)
    if not context_documents and vectorstore:
        logger.info("Priority 3: Performing general RAG search")
        general_docs = process_general_rag_search(
            user_message=user_message, vectorstore=vectorstore, k=k
        )
        context_documents.extend(general_docs)

    logger.info("Input processing complete: %s context document(s) retrieved", len(context_documents))

    return user_message, context_documents


def format_context_for_prompt(context_documents: List[Document]) -> str:
    """
    Format context documents for LLM prompt with improved structure.

    Args:
        context_documents: List of Document objects

    Returns:
        Formatted string with document contents, including clear separators and metadata.

    Example:
        >>> docs = [Document(page_content="...", metadata={'source': 'file.txt'})]
        >>> context = format_context_for_prompt(docs)
    """
    if not context_documents:
        return "No relevant context found."

    formatted_parts = []

    for i, doc in enumerate(context_documents, 1):
        source = doc.metadata.get("source", "unknown")
        content = doc.page_content.strip()

        formatted_parts.append(
            f"\n=== Document {i} ===\nSource: {source}\nContent:\n{content}\n"
        )

    return "\n".join(formatted_parts)


def segment_file_content(file_path: Path, max_segment_size: int = 4000) -> List[str]:
    """
    Segment file content for direct inclusion in Ollama prompts.

    This function reads a file and splits it into manageable segments
    that can be included directly in the prompt for LLMs like Ollama
    that don't have native file upload APIs.

    Args:
        file_path: Path to the file to segment
        max_segment_size: Maximum size of each segment in characters

    Returns:
        List of content segments

    Example:
        >>> segments = segment_file_content(BASE_DIR / "README.md", max_segment_size=3000)
        >>> for i, segment in enumerate(segments):
        ...     print(f"Segment {i+1}: {len(segment)} chars")
    """
    segments = []

    try:
        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # If content is small enough, return as single segment
        if len(content) <= max_segment_size:
            return [content]

        # Split by lines to preserve structure
        lines = content.split("\n")
        current_segment = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for newline

            # If adding this line would exceed max size, start new segment
            if current_size + line_size > max_segment_size and current_segment:
                segments.append("\n".join(current_segment))
                current_segment = []
                current_size = 0

            current_segment.append(line)
            current_size += line_size

        # Add final segment if not empty
        if current_segment:
            segments.append("\n".join(current_segment))

        logger.info("Segmented %s into %s segments", file_path, len(segments))
        return segments

    except UnicodeDecodeError:
        logger.warning("Cannot segment binary file: %s", file_path)
        return []
    except Exception as e:
        logger.error("Error segmenting file %s: %s", file_path, e)
        return []
