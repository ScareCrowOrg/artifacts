# Example Cell – Backend Tests

## Purpose

Reference test implementation for the **Example Cell** backend — demonstrates the standard test pattern for cell backend testing.

## Content Index

| File | Description |
|------|-------------|
| [`test_main.py`](./test_main.py) | Reference test — shows how to test `execute_cell()` with mocked dependencies, assertion patterns, and error case coverage |

## Usage as Reference

```python
# Pattern for testing cell backends
import pytest
from scripts.main import execute_cell

async def test_execute_cell_success():
    result = await execute_cell({"action": "example"}, user_id="test-user")
    assert result["status"] == "success"
```

## Related

- [`../scripts/main.py`](../scripts/main.py) — The module being tested
