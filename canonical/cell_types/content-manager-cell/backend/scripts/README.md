# Content Manager Cell – Backend Scripts

## Purpose

Backend execution scripts for the **Content Manager Cell** — handles content asset CRUD operations (upload, list, delete, update metadata).

## Content Index

| File | Description |
|------|-------------|
| [`main.py`](./main.py) | `execute_cell()` — routes to content management actions: `list`, `upload`, `delete`, `get-metadata` |
| [`storage.py`](./storage.py) | Storage abstraction layer — S3/R2 upload/download/delete operations |
| [`utils.py`](./utils.py) | Utility functions — MIME type detection, filename sanitization, metadata extraction |

## Related

- [`../`](../) — Content Manager Cell backend root
- [`../tests/`](../tests/) — Backend tests
