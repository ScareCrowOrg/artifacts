"""
DEPRECATED: This module has been modularized for RULESET compliance.

This file now serves as a compatibility shim. Please update your imports to use:

    from app.orchestrator.langgraph import ChatOrchestrator, get_orchestrator, OrchestratorState

The original langgraph_orchestrator.py (839 lines) has been refactored into modular
components under app/orchestrator/langgraph/ to comply with RULESET.md Rule 1.1
(500-line file size limit).

New structure:
    backend/app/orchestrator/langgraph/
    ├── __init__.py                    # Public API exports (28 lines)
    ├── flow.py                        # Main LangGraph flow (277 lines)
    ├── state.py                       # OrchestratorState definition (35 lines)
    ├── intention_classifier_node.py   # Intention classification (42 lines)
    ├── action_executor.py             # Action execution (101 lines)
    ├── response_generator.py          # Response generation (203 lines)
    ├── file_processor.py              # File processing (144 lines)
    ├── function_calling.py            # Function calling (98 lines)
    ├── history_manager.py             # History management (123 lines)
    ├── instruction_receiver.py        # Instruction reception (166 lines)
    └── README.md                      # Documentation (347 lines)

All files are now under 500 lines, complying with RULESET.md.

For migration guide and documentation, see:
    backend/app/orchestrator/langgraph/README.md

This compatibility shim will be removed in a future release.
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "Importing from 'app.langgraph_orchestrator' is deprecated. "
    "Please update to 'from app.orchestrator.langgraph import ...' instead. "
    "This compatibility shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from new location for backward compatibility
from .orchestrator.langgraph import (
    ChatOrchestrator,
    OrchestratorState,
    get_orchestrator,
)

__all__ = ["ChatOrchestrator", "get_orchestrator", "OrchestratorState"]
