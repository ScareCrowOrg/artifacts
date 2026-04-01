# Example Cell — Backend

Python backend for the Example Cell, providing a minimal reference implementation of the `execute_cell` pattern.

## Purpose

This package demonstrates the canonical backend structure for a ScareVerse cell. It is the **starting point** for developers creating new cell types. Copy this directory, rename it, and replace the placeholder logic in `scripts/main.py` with your cell's actual execution logic.

## Index

### Files

| File | Description |
|------|-------------|
| `__init__.py` | Python package marker |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `scripts/` | `main.py` — `execute_cell()` reference implementation accepting `message` and `counter` fields |
| `tests/` | `test_main.py` — unit tests demonstrating the test pattern for cell backends |

## Reference Implementation

```python
# scripts/main.py
def execute_cell(cell_data: dict) -> dict:
    """
    Minimal cell execution:
    - Reads 'message' and 'counter' from cell_data
    - Returns them with an incremented counter
    """
    message = cell_data.get("message", "Hello, World!")
    counter = cell_data.get("counter", 0)
    return {
        "output": message,
        "counter": counter + 1,
        "status": "success",
    }
```

## How to Use as a Template

1. Copy the `example/` directory: `cp -r example/ my-new-cell/`
2. Rename the backend package in `__init__.py`
3. Replace the logic in `scripts/main.py` with your cell's behavior
4. Update `tests/test_main.py` to cover your new logic
5. Register the cell type by creating/updating `type.json`

## Running Tests

```bash
pytest artifacts/canonical/cell_types/example/backend/tests/ -v
```

## Related Documentation

- [Example Cell Root](../) - Full cell overview and template guidance
- [Example Cell Frontend](../frontend/) - Vue frontend template
- [Shared Types](../../../../shared/types/) - `BaseCell` interface
- [Adding New Cell Type](../../../../../docs/official/ADDING_NEW_CELL_TYPE.md) - Official guide
