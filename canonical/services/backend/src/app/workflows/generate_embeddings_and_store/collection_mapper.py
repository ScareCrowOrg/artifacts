"""
ChromaDB Collection Mapping

Determines appropriate ChromaDB collection names based on file types.
This mapping strategy enables multi-collection retrieval in the future,
allowing for targeted searches based on content type.
"""

import logging

logger = logging.getLogger(__name__)


def get_collection_name_from_file_type(file_type: str) -> str:
    """
    Determine ChromaDB collection name based on file type.

    This mapping strategy enables multi-collection retrieval in the future,
    allowing for targeted searches based on content type.

    Args:
        file_type: Type of the file (e.g., 'markdown', 'python', 'pdf')

    Returns:
        ChromaDB collection name for this file type

    Collection Strategy:
        - scareverse_docs: Documentation and text-based content
        - scareverse_code: Source code files
        - scareverse_config: Configuration and structured data files
    """
    file_type_lower = file_type.lower()

    # Documentation and text files
    if file_type_lower in ["markdown", "md", "text", "txt", "pdf", "rst", "adoc"]:
        return "scareverse_docs"

    # Source code files
    if file_type_lower in [
        "python",
        "py",
        "javascript",
        "js",
        "typescript",
        "ts",
        "java",
        "cpp",
        "c",
        "go",
        "rust",
        "rs",
        "shell",
        "sh",
        "bash",
        "jsx",
        "tsx",
        "cs",
        "hpp",
        "h",
    ]:
        return "scareverse_code"

    # Configuration and data files
    if file_type_lower in ["json", "yaml", "yml", "toml", "xml", "ini", "conf", "cfg"]:
        return "scareverse_config"

    # Default to docs collection
    logger.warning("Unknown file type '%s', defaulting to scareverse_docs collection", file_type)
    return "scareverse_docs"


def get_embedding_model_for_collection(collection_name: str) -> str:
    """
    Map collection name to appropriate embedding model.

    Args:
        collection_name: Name of the ChromaDB collection

    Returns:
        Embedding model ID for this collection
    """
    collection_to_model = {
        "scareverse_docs": "mistral",
        "scareverse_code": "deepseek-coder",
        "scareverse_config": "deepseek-coder",
        "scareverse_md": "mistral",
        "scareverse_json": "deepseek-coder",
        "scareverse_yml": "deepseek-coder",
    }

    return collection_to_model.get(collection_name, "mistral")
