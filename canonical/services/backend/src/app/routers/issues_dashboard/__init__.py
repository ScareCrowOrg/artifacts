"""
Issues Dashboard module - Reactive monitoring for the issues-queue.

This module provides API endpoints and utilities for:
- Monitoring and managing cells in the issues-queue
- Real-time streaming via Server-Sent Events (SSE)
- Orchestrator control (start/stop monitoring, pause/resume processing)
- Triggering ingest and processing operations
"""

from .helpers import (
    get_cell_by_id,
    get_filtered_cells_and_counts,
    get_orchestrator_or_raise,
    trigger_ingest_script,
)
from .models import (
    IssueCounts,
    MonitoringControlResponse,
    MonitoringStatusResponse,
    PaginatedResponse,
    ProcessingControlResponse,
    ProcessingStatusResponse,
    ProcessPendingCellsResponse,
    TriggerIngestRequest,
    TriggerIngestResponse,
)
from .streaming import stream_all_active_fragments, stream_cell_fragments, stream_events

__all__ = [
    # Models
    "IssueCounts",
    "PaginatedResponse",
    "TriggerIngestRequest",
    "TriggerIngestResponse",
    "ProcessPendingCellsResponse",
    "MonitoringStatusResponse",
    "MonitoringControlResponse",
    "ProcessingStatusResponse",
    "ProcessingControlResponse",
    # Streaming functions
    "stream_events",
    "stream_cell_fragments",
    "stream_all_active_fragments",
    # Helper functions
    "get_filtered_cells_and_counts",
    "get_cell_by_id",
    "trigger_ingest_script",
    "get_orchestrator_or_raise",
]
