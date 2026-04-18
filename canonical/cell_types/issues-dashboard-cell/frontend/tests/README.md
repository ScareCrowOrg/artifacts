# Issues Dashboard Cell – Frontend Tests

## Purpose

Unit and component tests for the Issues Dashboard Cell frontend.

## Content Index

| File | Description |
|------|-------------|
| [`IssuesDashboardCell.spec.ts`](./IssuesDashboardCell.spec.ts) | Tests for the BaseCell implementation — action routing, data fetching, health check |
| [`View.spec.ts`](./View.spec.ts) | Component tests for `View.vue` — rendering, filter interaction, issue selection |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`components/`](./components/) | `IssueList.spec.ts` — component-level tests for `IssueList.vue` |

## How to Run

```bash
npm run test -- issues-dashboard
```

## Related

- [`../`](../) — Issues Dashboard Cell frontend root
