# Shared Artifacts

Cross-cutting utilities, composables, configuration helpers, and services shared
across all ScareVerseLab cell types and frontend modules.

## Purpose

Provides a single source of truth for reusable frontend composables, backend
Python utilities, API configuration, and type definitions so that individual
cell implementations remain thin and consistent.

## Content Index

### Files
| File | Description |
|------|-------------|
| `__init__.py` | Python package marker |
| `config_manager.py` | Centralised configuration loader for Python workers |
| `jwt_utils.py` | JWT encode/decode helpers shared by backend services |
| `secret_client.py` | Client for retrieving secrets from the platform secret store |

### Subdirectories
| Directory | Description |
|-----------|-------------|
| `components/` | Shared Vue components (viewers and generic UI elements) |
| `composables/` | Vue composables — `useActionRegistry`, `useBaseCellFeatures`, `useCellFactory`, `useCellI18n`, and many more |
| `config/` | Frontend configuration modules (`apiConfig.js`, `chatLimits.js`, `endpoints.js`) |
| `crypto/` | TOTP/crypto validation utilities |
| `i18n/` | Internationalisation resources shared across cells |
| `services/` | Shared frontend service modules |
| `stores/` | Shared Pinia stores |
| `styles/` | Shared CSS/SCSS design tokens and global styles |
| `tests/` | Unit tests for shared utilities |
| `types/` | Shared TypeScript type definitions |
| `utils/` | Miscellaneous helper functions |

## Related Documentation

- [Artifacts Root](../README.md) — canonical, runtime, dev, and src artifacts
- [Canonical Workers](../canonical/workers/) — workers that import shared Python utilities
- [Shared Crypto](./crypto/) — TOTP validator utilities
