"""
Intelligent Chunking Module

This module handles intelligent text chunking using file-type-specific strategies.
It dispatches to specialized chunkers based on file type.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def _is_frontend_js_file(file_path: Path, file_type: str) -> bool:
    """
    Determine if a JS/TS file is part of the Vue.js frontend.

    Checks if the file is in frontend-specific directories:
    - cockpit-vue/src/composables/
    - cockpit-vue/src/stores/
    - cockpit-vue/src/components/
    - cockpit/src/composables/
    - cockpit/src/stores/

    Args:
        file_path: Path to the file
        file_type: File type ('js' or 'ts')

    Returns:
        True if file is a Vue.js frontend file
    """
    if file_type not in ["js", "ts"]:
        return False

    path_str = str(file_path).lower()
    frontend_patterns = [
        "cockpit-vue/src/composables",
        "cockpit-vue/src/stores",
        "cockpit-vue/src/components",
        "cockpit/src/composables",
        "cockpit/src/stores",
    ]

    return any(pattern in path_str for pattern in frontend_patterns)


def chunk_text_intelligent(
    content: str,
    file_path: Path,
    file_type: str,
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split text into chunks using intelligent, file-type-specific strategies.

    This function dispatches to specialized chunkers based on file type:
    - Markdown: Semantic chunking with MarkdownHeaderTextSplitter
    - Python: AST-based chunking with docstring extraction
    - YAML/JSON/ENV: Structured chunking
    - Other: Generic RecursiveCharacterTextSplitter

    Args:
        content: Text to chunk
        file_path: Source file path
        file_type: Type of the file
        document_id: Unique document identifier
        chunk_size: Maximum size of each chunk
        chunk_overlap: Number of characters to overlap between chunks

    Returns:
        Tuple of (doc_chunks, code_chunks) - both are lists of dicts with 'text' and 'metadata'
    """
    try:
        from ..chunking_strategies import (
            chunk_configuration_file,
            chunk_markdown,
            chunk_python_code,
        )
        from ..vue_chunking_strategies import chunk_vue_code

        file_type_lower = file_type.lower()
        doc_chunks = []
        code_chunks = []

        # Markdown files: semantic chunking for documentation
        if file_type_lower in ["md", "markdown"]:
            doc_chunks = chunk_markdown(
                content, file_path, document_id, chunk_size, chunk_overlap
            )
            logger.info("Markdown chunking produced %s doc chunks", len(doc_chunks))

        # Python files: AST-based chunking with docstring extraction
        elif file_type_lower in ["py", "python"]:
            code_chunks, extracted_doc_chunks = chunk_python_code(
                content, file_path, document_id
            )
            doc_chunks.extend(extracted_doc_chunks)
            logger.info(
                "Python chunking produced %s code chunks and %s doc chunks",
                len(code_chunks), len(extracted_doc_chunks)
            )

        # Configuration files: structured chunking
        elif file_type_lower in ["yaml", "yml", "json", "env"]:
            config_chunks = chunk_configuration_file(
                content, file_path, document_id, file_type_lower
            )
            code_chunks.extend(config_chunks)
            logger.info("Configuration chunking produced %s code chunks", len(config_chunks))

        # Vue.js files: specialized chunking for SFCs, composables, and Pinia stores
        elif file_type_lower == "vue" or _is_frontend_js_file(
            file_path, file_type_lower
        ):
            code_chunks, extracted_doc_chunks = chunk_vue_code(
                content, file_path, document_id, file_type_lower
            )
            doc_chunks.extend(extracted_doc_chunks)
            logger.info(
                "Vue.js chunking produced %s code chunks and %s doc chunks",
                len(code_chunks), len(extracted_doc_chunks)
            )

        # Other code files: treat as code with simple chunking
        elif file_type_lower in [
            "js",
            "ts",
            "jsx",
            "tsx",
            "java",
            "cpp",
            "c",
            "go",
            "rs",
            "sh",
            "bash",
        ]:
            # Use generic text splitter but target code collection
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            text_chunks = splitter.split_text(content)

            for idx, chunk_content in enumerate(text_chunks):
                code_chunks.append(
                    {
                        "text": chunk_content,
                        "metadata": {
                            "chunk_id": str(idx),
                            "document_id": document_id,
                            "source": str(file_path),
                            "file_type": file_type_lower,
                            "chunk_index": idx,
                            "char_count": len(chunk_content),
                            "embedding_model_id": "deepseek-coder",
                            "target_collection": "scareverse_code",
                        },
                    }
                )
            logger.info("Generic code chunking produced %s code chunks", len(code_chunks))

        # Documentation files: treat as documentation with simple chunking
        elif file_type_lower in ["txt", "rst", "adoc", "pdf"]:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            text_chunks = splitter.split_text(content)

            for idx, chunk_content in enumerate(text_chunks):
                doc_chunks.append(
                    {
                        "text": chunk_content,
                        "metadata": {
                            "chunk_id": str(idx),
                            "document_id": document_id,
                            "source": str(file_path),
                            "file_type": file_type_lower,
                            "chunk_index": idx,
                            "char_count": len(chunk_content),
                            "embedding_model_id": "mistral",
                            "target_collection": "scareverse_docs",
                        },
                    }
                )
            logger.info("Generic doc chunking produced %s doc chunks", len(doc_chunks))

        else:
            # Unknown type: default to documentation
            logger.warning("Unknown file type '%s', defaulting to documentation chunking", file_type)
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            text_chunks = splitter.split_text(content)

            for idx, chunk_content in enumerate(text_chunks):
                doc_chunks.append(
                    {
                        "text": chunk_content,
                        "metadata": {
                            "chunk_id": str(idx),
                            "document_id": document_id,
                            "source": str(file_path),
                            "file_type": file_type_lower,
                            "chunk_index": idx,
                            "char_count": len(chunk_content),
                            "embedding_model_id": "mistral",
                            "target_collection": "scareverse_docs",
                        },
                    }
                )
            logger.info("Default chunking produced %s doc chunks", len(doc_chunks))

        return doc_chunks, code_chunks

    except ImportError as e:
        logger.error("Failed to import chunking strategies: %s", e)
        raise
