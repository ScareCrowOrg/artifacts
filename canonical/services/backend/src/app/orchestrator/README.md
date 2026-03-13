---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - architecture
  - database
  - services
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Orchestrator Module

## Index

### Files
- `__init__.py` - Public API exports and module initialization
- `core.py` - Main Orchestrator class implementation
- `helpers.py` - Helper functions for cell conversion and data handling
- `instance.py` - Global orchestrator instance management
- `state.py` - State definitions for LangGraph workflows
- `file_processing.py` - File handling and processing utilities

### Subdirectories
- [langgraph/](./langgraph/) - LangGraph-based chat orchestration implementation

## Overview

The Orchestrator module manages the execution of cell workflows in the ScareVerse system. It monitors the issues-queue for pending cells, executes workflows using LangGraph, and manages cell state transitions.

**Nota sobre fragmentos:**
Os fragmentos de uma célula (`fragmentos`) agora são representados por strings livres, podendo conter qualquer formato textual, log, resultado ou memória. Não são mais instâncias rígidas de um modelo Pydantic, permitindo flexibilidade total para registro de execuções e histórico.

## Module Structure

```
orchestrator/
├── __init__.py          # Public API exports (60 lines)
├── core.py             # Main Orchestrator class (798 lines)
├── helpers.py          # Helper functions (154 lines)
├── instance.py         # Global instance management (73 lines)
├── state.py            # State definitions for LangGraph (47 lines)
├── file_processing.py  # File handling utilities (146 lines)
├── langgraph/          # LangGraph chat orchestration (modularized)
│   ├── __init__.py                    # Public API exports (28 lines)
│   ├── langgraph_chat_flow.py         # Main LangGraph flow (277 lines)
│   ├── langgraph_state.py             # OrchestratorState definition (35 lines)
│   ├── intention_classifier_node.py   # Intention classification (42 lines)
│   ├── action_executor.py             # Action execution (101 lines)
│   ├── response_generator.py          # Response generation (203 lines)
│   ├── file_processor.py              # File processing (144 lines)
│   ├── function_calling.py            # Function calling (98 lines)
│   ├── history_manager.py             # History management (123 lines)
│   ├── instruction_receiver.py        # Instruction reception (166 lines)
│   └── README.md                      # Documentation (347 lines)
└── README.md           # This file
```

**Total**: 2,842 lines (includes new langgraph chat orchestration module)

## Files

### `__init__.py` (60 lines)
Exports the public API of the orchestrator module.

**Exports:**
- `Orchestrator` - Main orchestrator class
- `set_orchestrator_instance`, `get_orchestrator_instance` - Instance management
- `celula_to_pipeline_item`, `update_celula_from_pipeline_item` - Conversion helpers
- `publish_fragment_to_redis`, `publish_pipeline_fragments` - Redis publishing
- `OrchestratorState` - State type definition
- File processing utilities

### `core.py` (798 lines)
Main orchestrator class with workflow execution logic.

**Key Components:**
- `Orchestrator` class
   - Initialization and configuration
   - Cell workflow execution (custom graphs, YAML workflows, LangGraph)
   - State management and database updates
   - Monitoring control (start, stop, pause, resume)
   - Manual trigger support
   - Registro de fragmentos: agora como lista de strings livres, cada entrada pode ser texto, log, resultado, etc.

**Key Methods:**
- `execute_cell_workflow(cell_id)` - Execute workflow for a specific cell
- `get_pending_cells()` - Retrieve pending cells from issues-queue
- `update_cell_state(cell_id, new_state, ...)` - Update cell state in database
- `start_monitoring()`, `stop_monitoring()` - Control monitoring loop
- `pause_processing()`, `resume_processing()` - Pause/resume cell processing
- `force_process_pending_issues()` - Manual trigger for immediate processing

### `helpers.py` (154 lines)
Helper functions for conversions and Redis publishing.

**Functions:**
- `celula_to_pipeline_item(cell, agent_data)` - Convert Celula to PipelineItem
- `update_celula_from_pipeline_item(cell_id, item)` - Update cell from PipelineItem
- `publish_fragment_to_redis(cell_id, fragment)` - Publish single fragment to Redis
- `publish_pipeline_fragments(item, since_fragment_id)` - Publish new fragments to Redis
- `set_redis_client(client)` - Configure Redis client for publishing

### `instance.py` (73 lines)
Global instance management and entry point.

**Functions:**
- `set_orchestrator_instance(orchestrator)` - Set global orchestrator instance
- `get_orchestrator_instance()` - Get global orchestrator instance
- `main()` - Entry point for running the orchestrator

### `state.py` (47 lines)
State definitions for the LangGraph orchestrator.

**Types:**
- `OrchestratorState` - TypedDict defining the state structure for chat orchestration

### `file_processing.py` (146 lines)
File handling utilities for the orchestrator.

**Functions:**
- `process_attached_files(...)` - Process files attached from UI
- `get_segmented_content_for_ollama(...)` - Get segmented content for Ollama
- `get_file_ids_for_llm(...)` - Get file IDs for LLM context

### `langgraph/` (Submodule)
LangGraph-based chat orchestration for ScareVerse. This is a separate modular system that implements a state graph for processing user chat messages with intention classification, action execution, and response generation.

**See:** [langgraph/README.md](./langgraph/README.md) for detailed documentation.

**Key Features:**
- **Intention Classification** - Automatically classifies user intentions (CONVERSAR, CRIAR, EXECUTAR, REFLETIR, DEPURAR)
- **Action Execution** - Creates or executes cells based on intentions
- **RAG Integration** - Retrieves relevant documents from vector store
- **Conversational Memory** - Maintains conversation history across sessions
- **Chat History Summarization** - Automatically summarizes long conversations
- **Function Calling** - On-demand document access via OpenAI function calling
- **File Attachment Processing** - Handles files differently based on target LLM

**Public API:**
```python
from app.orchestrator.langgraph import ChatOrchestrator, get_orchestrator

orchestrator = get_orchestrator()
result = orchestrator.process(
    mensagem="Crie uma célula para sistema de login",
    responsavel_id="user123",
    use_rag=True,
    use_memory=True,
    session_id="session_abc"
)
```

**Compliance:** All files in the langgraph submodule are under 500 lines, complying with RULESET.md Rule 1.1.

## Usage

### Basic Import

```python
from app.orchestrator import Orchestrator

# Create orchestrator instance
orchestrator = Orchestrator()

# Execute workflow for a specific cell
orchestrator.execute_cell_workflow("cell-id-123")
```

### As a Module

```bash
# Run the orchestrator monitoring loop
python -m backend.app.orchestrator
```

### With FastAPI Integration

```python
from app.orchestrator import (
    Orchestrator,
    set_orchestrator_instance,
    get_orchestrator_instance
)

# Initialize at startup
orchestrator = Orchestrator()
set_orchestrator_instance(orchestrator)

# Start monitoring
orchestrator.start_monitoring()

# Later, get instance from anywhere
orch = get_orchestrator_instance()
if orch:
    orch.force_process_pending_issues()
```

### Helper Functions

```python
from app.orchestrator import (
    celula_to_pipeline_item,
    update_celula_from_pipeline_item,
    publish_fragment_to_redis
)

# Convert cell to pipeline item
pipeline_item = celula_to_pipeline_item(cell, agent_data)

# Update cell from pipeline result
update_celula_from_pipeline_item(cell_id, result_item)

# Publish fragment to Redis for streaming
publish_fragment_to_redis(cell_id, fragment)
```

## Workflow Execution Priorities

The orchestrator executes workflows in the following priority order:

1. **Custom Graph with execute() function** (Python modules)
   - Checks `cell_type.python_refs` for files ending in `*graph.py`
   - If found, tries to import and call `execute(pipeline_item)`
   - Most flexible, direct PipelineItem manipulation

2. **Custom LangGraph** (Python modules)
   - Loads custom graph from `*graph.py` files
   - Executes with custom state structure
   - Fallback if no `execute()` function found

3. **YAML Workflow File** (External files)
   - Checks `cell_type.yaml_refs` for workflow files
   - Loads and parses workflow definition from file
   - Executes using standard LangGraph workflow

4. **Inline Workflow** (Database definition)
   - Uses `cell_type.workflows['main_workflow']`
   - Executes using standard LangGraph workflow
   - Default fallback option

## State Management

Cells transition through the following states:
- `PENDENTE` (Pending) - Cell is queued for processing
- `EXECUTANDO` (Running) - Workflow is being executed
- `FINALIZADO` (Completed) - Workflow completed successfully
- `ERRO` (Error) - Workflow failed with error

## Monitoring and Control

### Monitoring Loop
- Polls issues-queue at configured interval (default: 5 seconds)
- Processes up to `max_concurrent_cells` (default: 2) in each iteration
- Can be started/stopped via API endpoints

### Manual Trigger
- `force_process_pending_issues()` triggers immediate processing
- Bypasses polling interval
- Returns count of pending cells found

### Pause/Resume
- `pause_processing()` - Pause cell processing while keeping monitoring active
- `resume_processing()` - Resume cell processing
- Useful for temporary suspension without stopping monitoring

## Configuration

Configuration is loaded from the orchestrator agent in the database:
```json
{
  "agent_specific_config": {
    "polling_interval_seconds": 5,
    "max_concurrent_cells": 2
  }
}
```

## Redis Integration

When Redis is enabled (`REDIS_ENABLED=true`), the orchestrator:
- Publishes fragments to Redis channels for real-time streaming
- Channel format: `celula:{cell_id}:fragmentos`
- Fragments are published as JSON messages

## Testing

Unit tests are located in:
- `tests/unit/backend/test_orchestrator.py` - Core orchestrator tests
- `tests/unit/backend/test_orchestrator_monitoring.py` - Monitoring tests
- `tests/integration/backend/test_orchestration_integration.py` - Integration tests

Run tests:
```bash
pytest tests/unit/backend/test_orchestrator.py -v
```

## Dependencies

- **FastAPI** - Web framework
- **Pydantic** - Data validation
- **LangGraph** - Workflow execution
- **LangChain** - AI orchestration utilities
- **Redis** (optional) - Real-time fragment streaming

## Migration Notes

This module was refactored from a single 979-line file (`backend/app/orchestrator.py`) into a modular structure. The refactoring:

✅ **Maintains backward compatibility** - All existing imports work  
✅ **Reduces main file** - From 979 to 84 lines (91% reduction)  
✅ **Improves testability** - Clear module boundaries  
✅ **Enhances maintainability** - Single-responsibility modules  
✅ **Preserves functionality** - All behavior unchanged  

### Before
```
backend/app/orchestrator.py (979 lines)
```

### After
```
backend/app/orchestrator.py (84 lines - backward compat wrapper)
backend/app/orchestrator/
├── core.py (798 lines)
├── helpers.py (154 lines)
├── instance.py (73 lines)
├── __init__.py (60 lines)
├── state.py (47 lines)
└── file_processing.py (146 lines)
```

## Backward Compatibility

The original `backend/app/orchestrator.py` file now serves as a backward compatibility wrapper that:
- Re-exports all public APIs from the modularized structure
- Maintains Redis client initialization
- Provides the same entry point for running as a module
- Ensures all existing imports continue to work

**Example - Old imports still work:**
```python
# This still works exactly as before
from app.orchestrator import Orchestrator, set_orchestrator_instance
```

## Future Improvements

If strict 500-line compliance is required for all files, `core.py` (798 lines) can be further split into:
- `workflow_execution.py` (~300 lines) - Workflow execution methods
- `monitoring.py` (~200 lines) - Monitoring and control methods
- `core.py` (~300 lines) - Main orchestrator logic (reduced)

This would bring all files under the 500-line threshold while maintaining the same functionality.

## Compliance Status

✅ **Main File**: orchestrator.py reduced from 979 to 84 lines  
⚠️ **Core Module**: core.py at 798 lines (under 800 warning threshold, above 500 target)  
✅ **Other Modules**: All under 200 lines  
✅ **Technical Naming**: English for all code  
✅ **Documentation**: Comprehensive README with examples  
✅ **Configuration**: Centralized in config.py  
✅ **Tests**: Comprehensive unit test coverage (81% overall, 7 modules at 100%)

## Testing

### Test Coverage

The orchestrator module has comprehensive test coverage targeting 90%+ as per RULESET.md:

**Coverage by Module (as of PR #8):**
- ✅ `langgraph_state.py`: **100%**
- ✅ `state.py`: **100%**
- ✅ `__init__.py`: **100%**
- ✅ `action_executor.py`: **100%**
- ✅ `intention_classifier_node.py`: **100%**
- ✅ `function_calling.py`: **100%**
- ✅ `history_manager.py`: **100%**
- ✅ `response_generator.py`: **94%**
- ✅ `instruction_receiver.py`: **85%**
- 🔄 `file_processor.py`: **71%** (in progress)
- 🔄 `langgraph_chat_flow.py`: **29%** (in progress)

### Test Location

All tests are located in `tests/unit/backend/orchestrator/`:
- `conftest.py` - Shared fixtures and mocks
- `test_action_executor.py` - Cell creation and execution tests (13 tests, 100%)
- `test_intention_classifier_node.py` - Intention classification tests (8 tests, 100%)
- `test_instruction_receiver.py` - State initialization, RAG, memory tests (19 tests, 85%)
- `test_response_generator.py` - LLM response generation tests (28 tests, 94%)
- `test_history_manager.py` - Chat history and summarization tests (11 tests, 100%)
- `test_function_calling.py` - OpenAI function calling tests (9 tests, 100%)

**Total: 88 passing tests with < 1 second execution time**

### Running Tests

```bash
# Run all orchestrator tests
pytest tests/unit/backend/orchestrator/ -v

# Run with coverage report
pytest tests/unit/backend/orchestrator/ --cov=app/orchestrator/langgraph --cov-report=term

# Run specific test file
pytest tests/unit/backend/orchestrator/test_response_generator.py -v
```

### Test Strategy

Tests follow the ARQUITETURA_TESTES.md guidelines:
- **Unit tests** for isolated business logic
- **Mocked dependencies**: RAG service, LLM services (Ollama/OpenAI/Gemini), database (mongomock)
- **Fast execution**: < 1 second for full test suite
- **High coverage**: 90%+ target for all modules
- **Comprehensive scenarios**: Happy paths, edge cases, error handling

### Mocking Approach

The test suite uses extensive mocking to avoid external dependencies:

```python
# Example: Testing response generation with mocked LLM
with patch('app.ollama_service.processar_chat_com_ollama', new_callable=AsyncMock) as mock_ollama:
    mock_ollama.return_value = "Mocked response"
    result = await retorna_resposta(state)
    assert result["resposta"] == "Mocked response"
```

**Mocked Components:**
- **RAG Service**: Mock documents with `page_content` and `metadata`
- **LLM Services**: AsyncMock for Ollama, OpenAI, Gemini
- **Database**: mongomock for MongoDB operations
- **Conversation Memory**: Mocked memory manager
- **Tracing Service**: Mocked trace recording


## See Also

- [Workflow Executor](../workflow_executor.py) - Workflow YAML parsing and execution
- [Event Bus](../event_bus.py) - Event publishing for state changes
- [Database](../database/) - Database operations
- [Models](../models.py) - Data models (Celula, Agent, TipoCelula, etc.)
- [RULESET.md](../../../../RULESET.md) - Project coding standards
- [ARQUITETURA_TESTES.md](../../../../docs/ARQUITETURA_TESTES.md) - Testing architecture

## Contributing

For questions or contributions:
- Create an issue with tag `orchestrator` or `refactoring`
- Reference this README in PRs affecting the orchestrator
- Follow the modularization guidelines in `RULESET.md`
