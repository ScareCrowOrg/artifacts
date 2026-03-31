# Canonical Notebook Items

JSON schema definitions for built-in notebook item (book) types used across the
ScareVerseLab platform. These files act as canonical templates that seed the
database and drive UI discovery of supported notebook item configurations.

## Purpose

Defines the structure and metadata for specialised book types so that the platform
can register, validate, and render them consistently without hard-coding their
schemas in application code.

## Content Index

| File | Description |
|------|-------------|
| `book-conversation-traces-v1.json` | Schema for the Conversation Traces book type — stores chronological LLM interaction records |
| `book-issues-queue-v1.json` | Schema for the Issues Queue book type — tracks GitHub issues assigned to a notebook |

## Related Documentation

- [Canonical Artifacts](../README.md) — parent canonical directory
- [Canonical Roles](../roles/) — RBAC roles that govern access to notebook items
- [Runtime Cell Docs](../../runtime/cells/docs/) — runtime schema and sandbox reference
