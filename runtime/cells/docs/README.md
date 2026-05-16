# Runtime Cells Documentation

This directory contains reference documentation for the ScareVerse runtime cell system, including schema definitions and quick reference guides for sandbox cells.

## Index

### Files

- [`SCHEMA.md`](./SCHEMA.md) — Pydantic schema definition for `Celula` (Runtime Cell / `NotebookItem`), including new and legacy fields, persistence via `JSONDatabase`, and execution via `PipelineItem`.
- [`SANDBOX_CELL_QUICK_REF.md`](./SANDBOX_CELL_QUICK_REF.md) — Quick reference for the extended sandbox cell system with dynamic runtime, advanced metadata, and lifecycle control.

## Overview

The runtime cells documentation covers the data models and operational patterns used by `NotebookItem` instances in the ScareVerse backend. These documents serve as a canonical reference for:

- **Cell schemas**: Field definitions, type constraints, legacy field mapping
- **Sandbox cells**: Runtime lifecycle, metadata extensions, dynamic type support

## Related Documentation

- [Runtime Cells Parent](../) — Parent directory for runtime cells
- [Backend Architecture](../../../../docs/) — Top-level project documentation
