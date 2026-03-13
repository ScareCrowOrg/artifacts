"""
Pydantic models for Issues Dashboard API.

Defines request and response models for:
- Paginated cell listings
- Ingest trigger operations
- Processing control
- Monitoring control
- Status reporting
"""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class IssueCounts(BaseModel):
    """Issue counts by status."""

    pendente: int = 0
    executando: int = 0
    finalizado: int = 0
    erro: int = 0


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response model."""

    items: List[T]
    total_items: int
    total_pages: int
    current_page: int
    items_per_page: int
    issue_counts: Optional[IssueCounts] = None


class TriggerIngestRequest(BaseModel):
    """Request model for triggering ingest.py."""

    source_dir: Optional[str] = None
    dry_run: bool = False


class TriggerIngestResponse(BaseModel):
    """Response model for ingest trigger."""

    status: str
    message: str
    command: str


class ProcessPendingCellsResponse(BaseModel):
    """Response model for processing pending cells."""

    status: str
    message: str
    pending_count: int


class MonitoringStatusResponse(BaseModel):
    """Response model for monitoring status."""

    active: bool
    polling_interval: int
    max_concurrent_cells: int
    task_running: bool


class MonitoringControlResponse(BaseModel):
    """Response model for monitoring control actions."""

    status: str
    message: str


class ProcessingStatusResponse(BaseModel):
    """Response model for processing status."""

    paused: bool


class ProcessingControlResponse(BaseModel):
    """Response model for processing control actions."""

    status: str
    message: str
