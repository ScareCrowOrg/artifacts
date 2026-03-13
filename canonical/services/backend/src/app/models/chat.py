"""
Chat models for AI chat processing.

Models for chat messages, attachments, and chat request/response handling.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Individual message in chat history."""

    role: Literal["user", "assistant"] = Field(
        ..., description="Message role (user or assistant)"
    )
    content: str = Field(..., description="Message content")


class ChatAttachment(BaseModel):
    """Attachment sent with chat message."""

    name: str = Field(..., description="Attachment name (e.g., file.py, cell 1)")
    content: str = Field(..., description="Attachment content")
    type: Optional[str] = Field(
        default="text", description="Attachment type (text, code, etc.)"
    )


class ProcessChatIntentRequest(BaseModel):
    """Request to process user intent via AI chat."""

    purpose: str = Field(..., description="User intention in natural language")
    assignee_id: Optional[str] = Field(
        default=None,
        description="UUID of the responsible user (deprecated: use authentication instead)",
    )
    history: Optional[List[ChatMessage]] = Field(
        default=None, description="Conversation history"
    )
    model: Optional[str] = Field(
        default="mistral",
        description="AI model to use (ollama: mistral, deepseek, phi; gemini: gemini)",
    )
    classify_intent: bool = Field(
        default=True,
        description="Whether to classify intent and execute actions (create cells, etc.) or just converse",
    )
    attachments: Optional[List[ChatAttachment]] = Field(
        default=None, description="Attachments sent with message (files, cells, etc.)"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Thread ID from Assistants API (OpenAI) for conversation continuation",
    )
    assistant_id: Optional[str] = Field(
        default=None, description="Assistant ID from Assistants API (OpenAI) for reuse"
    )
    use_rag: bool = Field(
        default=False,
        description="Enable RAG (Retrieval-Augmented Generation) context retrieval for enhanced responses",
    )
    selected_collections: Optional[List[str]] = Field(
        default_factory=list,
        description=(
            "CRITICAL: Selected RAG collections to search (e.g., ['scareverse_docs', 'scareverse_code']). "
            "RAG is ONLY executed if this list contains at least one collection name. "
            "If empty list [] (default when not provided), None, or omitted, RAG is DISABLED. "
            "NO fallback to 'all collections' will occur under ANY circumstances."
        ),
    )
    enable_tracing: bool = Field(
        default=False,
        description="Enable detailed conversation tracing for RAG pipeline observability. Creates structured trace cells capturing pipeline stages (RAG retrieval, query expansion, LLM calls, etc.)",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="Conversation identifier for session management. Used to build session_id for Open Interpreter and other stateful providers.",
    )


class ProcessChatIntentResponse(BaseModel):
    """Response from processing intent via chat."""

    response: str = Field(..., description="AI response to the user")
    cell: Optional[Dict[str, Any]] = Field(
        None, description="Created cell, if applicable"
    )
    thread_id: Optional[str] = Field(
        None,
        description="Thread ID from Assistants API (OpenAI) for conversation continuation",
    )
    assistant_id: Optional[str] = Field(
        None, description="Assistant ID from Assistants API (OpenAI) for reuse"
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation ID for trace retrieval (only available when enable_tracing=true)",
    )
