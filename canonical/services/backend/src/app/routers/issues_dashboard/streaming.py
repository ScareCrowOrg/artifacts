"""
Server-Sent Events (SSE) streaming functionality for Issues Dashboard.

Provides real-time streaming endpoints for:
- General event bus events (cell state changes, fragments, etc.)
- Individual cell fragment streaming via Redis
- All active cells fragment streaming via Redis pattern subscription

Backward compatibility shim that re-exports from modularized streaming_handlers.
"""

from .streaming_handlers import (
    stream_all_active_fragments,
    stream_cell_fragments,
    stream_events,
)

# Private functions (for backward compatibility)
from .streaming_handlers.streaming_fallback import (
    stream_cell_fragments_fallback as _stream_cell_fragments_fallback,
)
from .streaming_handlers.streaming_fallback import (
    stream_pipeline_fragments_fallback as _stream_pipeline_fragments_fallback,
)

__all__ = [
    "stream_events",
    "stream_cell_fragments",
    "stream_all_active_fragments",
    "_stream_cell_fragments_fallback",
    "_stream_pipeline_fragments_fallback",
]
