# Pipeline Monitoring Cell – Frontend Components

## Purpose

Vue 3 components for the **Pipeline Monitoring Cell** — displays real-time system health, metrics, alerts, and prerequisite status for the ScareVerse pipeline.

## Content Index

| File | Description |
|------|-------------|
| [`AlertBanner.vue`](./AlertBanner.vue) | Dismissible alert banner for critical/warning system alerts |
| [`ComponentHealthIndicator.vue`](./ComponentHealthIndicator.vue) | Health badge for a single pipeline component — green/yellow/red status with uptime |
| [`MetricsChart.vue`](./MetricsChart.vue) | Time-series chart for pipeline metrics (latency, throughput, error rate) |
| [`PrerequisiteCard.vue`](./PrerequisiteCard.vue) | Card showing prerequisite status for a pipeline step — met/unmet indicators |
| [`QuickActions.vue`](./QuickActions.vue) | Quick-action buttons — restart service, clear cache, trigger manual check |

## Related

- [`../`](../) — Pipeline Monitoring Cell frontend root
- [`../composables/`](../composables/) — Composables that feed data to these components
