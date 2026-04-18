# Pipeline Monitoring Cell – Composables

## Purpose

Vue 3 composables for the **Pipeline Monitoring Cell** — provides reactive data streams for health checks, metrics, WebSocket connections, and alerts.

## Content Index

| File | Description |
|------|-------------|
| [`useAlerts.ts`](./useAlerts.ts) | Alert management — active alerts, dismiss, acknowledge, severity grouping |
| [`useClientSideValidation.ts`](./useClientSideValidation.ts) | Client-side validation for pipeline prerequisites (before server check) |
| [`useHealthChecks.ts`](./useHealthChecks.ts) | Polling health checks for all pipeline components — status aggregation, retry logic |
| [`useMonitoring.ts`](./useMonitoring.ts) | Main monitoring orchestrator — coordinates health checks, metrics, and alerts |
| [`useMonitoringWebSocket.ts`](./useMonitoringWebSocket.ts) | Real-time WebSocket connection for push-based pipeline events and status updates |

## Related

- [`../`](../) — Pipeline Monitoring Cell frontend root
- [`../components/`](../components/) — Components that consume these composables
