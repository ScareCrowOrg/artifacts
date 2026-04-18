# Log Toggle Cell – Backend Scripts

## Purpose

Entry point for the **Log Toggle Cell** backend — enables dynamic enabling/disabling of logging for specific services without restarting them.

## Content Index

| File | Description |
|------|-------------|
| [`__init__.py`](./__init__.py) | Package marker |
| [`main.py`](./main.py) | `execute_cell()` — `enable-log`, `disable-log`, `list-logs`, `get-status` actions; updates log level via Backend's logging configuration API |

## Related

- [`../`](../) — Log Toggle Cell backend root
- [`../tests/`](../tests/) — Backend unit tests
