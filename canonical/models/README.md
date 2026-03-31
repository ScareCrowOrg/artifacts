# Canonical Models

Python data models that define core domain types shared across the ScareVerseLab
platform. These models serve as the authoritative source of truth for data structures
used in workers, cells, and backend services.

## Purpose

Provides importable Python model definitions so that all platform components
reference the same canonical data contracts without duplicating schema logic.

## Content Index

| File | Description |
|------|-------------|
| `__init__.py` | Package initialisation; re-exports public model classes |
| `job_type.py` | `JobType` enum/model defining the supported job categories (e.g. image generation, LLM inference, background removal) |

## Related Documentation

- [Canonical Artifacts](../README.md) — parent canonical directory
- [Workers](../workers/) — workers that consume these job-type models
- [Canonical Permissions](../permissions/) — RBAC permission definitions
