# Xterm Terminal Cell – Backend Tests

## Purpose

Unit tests for the Xterm Terminal Cell backend.

## Content Index

| File | Description |
|------|-------------|
| [`test_main.py`](./test_main.py) | Tests for PTY spawning, WebSocket message handling, resize events, process cleanup |

## How to Run

```bash
cd backend
pytest artifacts/canonical/cell_types/xterm-terminal-cell/backend/tests/ -v
```

## Related

- [`../scripts/main.py`](../scripts/main.py) — The module being tested
