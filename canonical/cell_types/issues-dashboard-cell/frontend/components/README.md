# Issues Dashboard Cell – Frontend Components

## Purpose

Vue 3 components for the **Issues Dashboard Cell** frontend — GitHub issue management UI with filtering, listing, detail view, stats, and pipeline activity feed.

## Content Index

| File | Description |
|------|-------------|
| [`CreateCellForm.vue`](./CreateCellForm.vue) | Form to create a new notebook cell from an issue |
| [`IngestForm.vue`](./IngestForm.vue) | Form to ingest GitHub issues into the system |
| [`IssueCard.vue`](./IssueCard.vue) | Compact issue card for list/grid display — shows title, labels, status, assignee |
| [`IssueDetails.vue`](./IssueDetails.vue) | Full issue detail panel — body, comments, labels, linked PRs |
| [`IssueFilters.vue`](./IssueFilters.vue) | Filter controls — by label, assignee, milestone, status, date range |
| [`IssueList.vue`](./IssueList.vue) | Paginated issue list with sorting and batch actions |
| [`IssueStats.vue`](./IssueStats.vue) | Statistics panel — open/closed counts, velocity chart, label distribution |
| [`Pagination.vue`](./Pagination.vue) | Reusable pagination controls used by IssueList |
| [`PipelineActivityFeed.vue`](./PipelineActivityFeed.vue) | Real-time pipeline activity feed via SSE — shows CI/CD events linked to issues |

## Related

- [`../`](../) — Issues Dashboard Cell frontend root
- [`../stores/issuesStore.ts`](../stores/issuesStore.ts) — Pinia store consumed by these components
