# Pipeline Monitoring Cell — Frontend

Vue 3 frontend for the Pipeline Monitoring Cell, providing real-time visualization of ScareVerse processing pipeline status.

## Purpose

This package contains the complete frontend implementation of the Pipeline Monitoring Cell: a monitoring cell that displays pipeline health, component status, metrics, alerts, and quick actions within the ScareVerse Cockpit.

## Index

### Files

| File | Description |
|------|-------------|
| `View.vue` | Root Vue component composing the monitoring dashboard |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `components/` | UI components for the monitoring dashboard |
| `composables/` | Vue composables for data fetching and real-time updates |
| `tests/` | Vitest unit, composable, and component tests |

## Components

| Component | Description |
|-----------|-------------|
| `AlertBanner.vue` | Displays active alerts and warning banners at the top of the dashboard |
| `ComponentHealthIndicator.vue` | Traffic-light health status for individual pipeline components (healthy/degraded/down) |
| `MetricsChart.vue` | Time-series chart for pipeline throughput, latency, and error rate metrics |
| `PrerequisiteCard.vue` | Status card for pipeline prerequisites (GPU availability, Redis connectivity, model files) |
| `QuickActions.vue` | Action buttons for common operations (restart pipeline, clear queue, trigger health check) |

## Composables

| Composable | Description |
|------------|-------------|
| `useAlerts.ts` | Fetches and manages active pipeline alerts; supports dismissal and severity filtering |
| `useClientSideValidation.ts` | Validates user inputs for quick action forms before submission |
| `useHealthChecks.ts` | Polls backend health check endpoints for all pipeline components |
| `useMonitoring.ts` | Aggregates metrics data from backend APIs and computes summary statistics |
| `useMonitoringWebSocket.ts` | WebSocket connection for real-time pipeline event streaming |

## Usage

The cell is rendered inside the cockpit-vue shell when activated. Real-time updates are delivered via `useMonitoringWebSocket.ts`.

## Related Documentation

- [Pipeline Monitoring Cell Root](../) - Full cell overview and `type.json` specification
- [Shared Composables](../../../../shared/composables/) - Platform-wide composables
- [Shared Services](../../../../shared/services/) - Shared HTTP service modules
