# Content Explorer Cell – Backend

## Purpose

Python backend for the **Content Explorer Cell**. Provides server-side logic for browsing and filtering content assets by type.

## Content Index

| Directory | Description |
|-----------|-------------|
| [`scripts/`](./scripts/) | `main.py` — entry point for ephemeral execution; composes ContentTypeManager and ContentManager logic |
| [`tests/`](./tests/) | `test_main.py` — backend unit tests |

## Related

- [`../`](../) — Content Explorer Cell root
- [`../../content-manager-cell/`](../../content-manager-cell/) — Asset management (delete, update)
- [`../../content-type-manager-cell/`](../../content-type-manager-cell/) — Content type discovery
