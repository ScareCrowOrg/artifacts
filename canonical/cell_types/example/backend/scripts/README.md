# Example Cell – Backend Scripts

## Purpose

Reference implementation scripts for the **Example Cell** — demonstrates the standard backend script pattern for cell execution.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`main.py`](./main.py) | `execute_cell()` — minimal reference implementation showing the expected function signature, input validation, and response format |

## Usage as Reference

When creating a new cell backend, copy this structure:

```python
async def execute_cell(cell_data: dict, user_id: str = None) -> dict:
    # 1. Validate inputs
    # 2. Execute logic
    # 3. Return standardized response
    return {"status": "success", "data": {...}}
```

## Related

- [`../`](../) — Example Cell backend root
- [`../tests/`](../tests/) — How to write backend tests
