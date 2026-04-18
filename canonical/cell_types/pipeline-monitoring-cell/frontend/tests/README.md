# Pipeline Monitoring Cell – Frontend Tests

## Purpose

Tests for the Pipeline Monitoring Cell frontend — component tests, composable tests, and view tests.

## Content Index

| File | Description |
|------|-------------|
| [`View.spec.ts`](./View.spec.ts) | Component tests for `View.vue` — full dashboard rendering, alert display, real-time updates |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`components/`](./components/) | Component-level tests (`ComponentHealthIndicator.spec.ts`, `PrerequisiteCard.spec.ts`) |
| [`composables/`](./composables/) | Composable unit tests (if present) |

## How to Run

```bash
npm run test -- pipeline-monitoring
```

## Related

- [`../`](../) — Pipeline Monitoring Cell frontend root
