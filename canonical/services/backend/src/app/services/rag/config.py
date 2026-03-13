"""
RAG Configuration - Constants and settings for RAG service.

This module centralizes RAG-specific configuration including:
- Default parameters
- Collection-to-embedding model mapping
- Configuration constants

Technical naming: All variables in English.
"""

# Default RAG configuration
DEFAULT_RAG_K = 5
OPENAI_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# Collection to embedding model mapping
# Maps ChromaDB collection names to their corresponding embedding models
COLLECTION_TO_EMBEDDING_MODEL = {
    "scareverse_docs": "mistral",  # Documentation uses Mistral
    "scareverse_code": "deepseek-coder",  # Code uses DeepSeek Coder
    "scareverse_config": "deepseek-coder",  # Config uses DeepSeek Coder
    "scareverse_md": "mistral",  # Markdown uses Mistral
    "scareverse_json": "deepseek-coder",  # JSON uses DeepSeek Coder
    "scareverse_yml": "deepseek-coder",  # YAML uses DeepSeek Coder
}

# Available collection names for validation
AVAILABLE_COLLECTION_NAMES = [
    "scareverse_docs",
    "scareverse_code",
    "scareverse_config",
    "scareverse_md",
    "scareverse_json",
    "scareverse_yml",
]
