"""
Base models, enums, and utility functions.

Common types and utilities used across all model modules.
"""

import uuid
from enum import Enum


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class CellStatus(str, Enum):
    """Cell execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    OBSOLETE = "obsolete"
    DELETED = "deleted"


class BookType(str, Enum):
    """Book type in the system."""

    VOLATILE = "VOLATILE"
    MASTER = "MASTER"


class ArtifactState(str, Enum):
    """Artifact execution state."""

    EXECUTED = "executed"
    PENDING = "pending"
    ERROR = "error"


class AIModelProvider(str, Enum):
    INTERPRETER = "interpreter"
    AIDER = "aider"
    """AI model provider."""
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    GROQ = "groq"
