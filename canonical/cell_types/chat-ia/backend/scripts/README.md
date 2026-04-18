# Chat IA Cell – Backend Scripts

## Purpose

Entry point for the **Chat IA Cell** backend using the `execute-ephemeral` pattern. Routes chat requests to either direct LLM or orchestrator based on intention classification.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`main.py`](./main.py) | `execute_cell()` async function — validates input, normalizes parameters, routes to `chat_router.py` logic; supports direct LLM and orchestrator modes |

## Architecture

```
execute-ephemeral request
    ↓
main.py::execute_cell()
    ↓ (classify intention)
    ├─ Direct LLM path (simple chat)
    └─ Orchestrator path (tool use / agent mode)
```

## Related

- [`../`](../) — Chat IA Cell backend root (service registration, health checks)
- [`../tests/`](../tests/) — Backend unit tests
