"""
Data Models package.

This package contains all Pydantic models and schemas organized by domain.

All models are re-exported from this module to maintain backward compatibility
with existing imports: `from app.models import User, Cell, ...`
"""

# Base models and enums
from .adapters import BookAdapter, CellAdapter, NotebookItemAdapter

# Agent models
from .agents import Agent, AgentType

# Artifact models
from .artifacts import (
    ArtifactContent,
    CanonicalArtifact,
    ExecutionResult,
    InstantiatedArtifact,
    Metadata,
)
from .base import AIModelProvider, ArtifactState, BookType, CellStatus, generate_uuid

# Content models
from .content import (
    AddCellToBookRequest,
    Book,
    Cell,
    CellRunRequest,
    CreateBookRequest,
    CreateCellRequest,
    DiscoveryMetadata,
    ExecuteCellRequest,
    ExecuteEphemeralCellRequest,
    Fragment,
    NotebookItemType,
    Scripts,
    UpdateCellRequest,
)

# Interfaces and Adapters
from .interfaces import IPipelineExecutable

# User models
from .users import (
    GlobalPreferences,
    Mascot,
    RegisterUserRequest,
    UpdateUserProfileRequest,
    User,
)

# PAT and Platform Node models
from .tokens import (
    AVAILABLE_SCOPES,
    CreatePATRequest,
    CreatePATResponse,
    NodeSummary,
    PATSummary,
    PersonalAccessToken,
    PlatformNode,
    RegisterNodeRequest,
)

# Backward compatibility aliases for artifact models
Metadados = Metadata
ConteudoArtefato = ArtifactContent
ArtefatoCanonico = CanonicalArtifact
ResultadoExecucao = ExecutionResult
ArtefatoInstanciado = InstantiatedArtifact

# Chat models
from .chat import (
    ChatAttachment,
    ChatMessage,
    ProcessChatIntentRequest,
    ProcessChatIntentResponse,
)

# Backward compatibility aliases for chat models
MensagemChat = ChatMessage
AnexoChat = ChatAttachment
ProcessarIntencaoChatRequest = ProcessChatIntentRequest
ProcessarIntencaoChatResponse = ProcessChatIntentResponse

# Session models
# Auth models
# NOTE: Authentication models (RegisterPasswordRequest, LoginPasswordRequest, etc)
# were moved to CentralHub as part of PR #2538 (Complete Authentication Strangling)
# Backend no longer handles password authentication - all auth flows are in CentralHub
# AI model configuration
from .ai_models import AIModel, CreateAIModelRequest, UpdateAIModelRequest

# Cell Factory models
from .cell_factory import (
    ActionPlan,
    ActionStep,
    CellGenerationRequest,
    CellGenerationResponse,
    CellPromotionRequest,
    CellPromotionResponse,
    ConversationMessage,
    DynamicRef,
    EnrichedPrompt,
    GenerationMetadata,
    RAGContext,
    SandboxExecutionState,
    UnclassifiedCellData,
)

# Event Bus models
from .event_bus import (
    ErrorResponse,
    EventTopic,
    FileAccessRequest,
    FileAccessResponse,
    HeartbeatEvent,
    MessageEnvelope,
)

# Execution models
from .execution_models import ExecutionRecord

# Config models
from .oauth_config import OAuthConfiguration, UpdateOAuthConfigRequest
from .sessions import CreateSessionRequest, CreateSessionResponse, Session

# Export all models
__all__ = [
    # Base
    "generate_uuid",
    "CellStatus",
    "BookType",
    "ArtifactState",
    "AIModelProvider",
    # Users
    "GlobalPreferences",
    "Mascot",
    "User",
    "RegisterUserRequest",
    "UpdateUserProfileRequest",
    # PAT / Platform Nodes
    "AVAILABLE_SCOPES",
    "PersonalAccessToken",
    "CreatePATRequest",
    "CreatePATResponse",
    "PATSummary",
    "PlatformNode",
    "RegisterNodeRequest",
    "NodeSummary",
    # Content
    "Scripts",
    "DiscoveryMetadata",
    "NotebookItemType",
    "Fragment",
    "Cell",
    "Book",
    "CreateCellRequest",
    "CreateBookRequest",
    "AddCellToBookRequest",
    "ExecuteCellRequest",
    "ExecuteEphemeralCellRequest",
    "UpdateCellRequest",
    "CellRunRequest",
    # Interfaces and Adapters
    "IPipelineExecutable",
    "NotebookItemAdapter",
    "CellAdapter",
    "BookAdapter",
    # Agents
    "AgentType",
    "Agent",
    # Artifacts
    "Metadata",
    "ArtifactContent",
    "CanonicalArtifact",
    "ExecutionResult",
    "InstantiatedArtifact",
    # Backward compatibility
    "Metadados",
    "ConteudoArtefato",
    "ArtefatoCanonico",
    "ResultadoExecucao",
    "ArtefatoInstanciado",
    # Chat
    "ChatMessage",
    "ChatAttachment",
    "ProcessChatIntentRequest",
    "ProcessChatIntentResponse",
    # Backward compatibility
    "MensagemChat",
    "AnexoChat",
    "ProcessarIntencaoChatRequest",
    "ProcessarIntencaoChatResponse",
    # Sessions
    "Session",
    "CreateSessionRequest",
    "CreateSessionResponse",
    # Config
    "OAuthConfiguration",
    "UpdateOAuthConfigRequest",
    # AI Models
    "AIModel",
    "CreateAIModelRequest",
    "UpdateAIModelRequest",
    # Execution
    "ExecutionRecord",
    # Cell Factory
    "DynamicRef",
    "GenerationMetadata",
    "SandboxExecutionState",
    "UnclassifiedCellData",
    "CellPromotionRequest",
    "CellPromotionResponse",
    "CellGenerationRequest",
    "CellGenerationResponse",
    "ConversationMessage",
    "RAGContext",
    "EnrichedPrompt",
    "ActionStep",
    "ActionPlan",
    # Event Bus
    "EventTopic",
    "MessageEnvelope",
    "FileAccessRequest",
    "FileAccessResponse",
    "ErrorResponse",
    "HeartbeatEvent",
]
