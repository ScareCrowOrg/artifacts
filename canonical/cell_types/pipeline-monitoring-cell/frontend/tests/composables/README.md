# Pipeline Monitoring Cell — Composable Tests

Unit tests for the `useMonitoring` composable used by the Pipeline Monitoring cell.

## Purpose

This directory contains Vitest tests for the `useMonitoring` composable:
- Validates the composable's setup, execute, save, and health check lifecycle
- Uses stub implementations to work around unresolvable BaseCell dependencies in the test environment

## Directory Structure

```
composables/
└── useMonitoring.spec.ts   - Unit tests for the useMonitoring composable
```

## How to Use

```bash
# Run from the cockpit-vue root
cd cockpit-vue
npx vitest run

# Or run from the cell type frontend root
cd artifacts/canonical/cell_types/pipeline-monitoring-cell/frontend
npm test
```

## Content Index

| File | Description |
|---|---|
| `useMonitoring.spec.ts` | Unit tests for the useMonitoring composable (setup, execute, save, healthCheck) |
