# Issues Dashboard Cell — Frontend

Vue 3 frontend for the Issues Dashboard Cell, providing an admin interface for viewing and managing GitHub-linked project issues within the ScareVerse Cockpit.

## Purpose

This package contains the complete frontend implementation of the Issues Dashboard Cell: an admin cell that displays, filters, and provides actions on GitHub issues tracked by the ScareVerse project.

## Index

### Files

| File | Description |
|------|-------------|
| `IssuesDashboardCell.ts` | TypeScript class implementing `BaseCell` for this cell |
| `View.vue` | Root Vue component composing the issue list, filters, stats, and detail views |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `components/` | UI components (see below) |
| `stores/` | `issuesStore.ts` — Pinia store for issues state (list, filters, pagination, selected issue) |
| `tests/` | Vitest component and unit tests |
| `translations/` | i18n locale files: `en.json`, `pt-BR.json` |

## Components

| Component | Description |
|-----------|-------------|
| `CreateCellForm.vue` | Form for creating a new cell from an issue |
| `IssueCard.vue` | Compact issue summary card for the list view |
| `IssueDetails.vue` | Expanded issue detail view with labels, assignees, and body |
| `IssueFilters.vue` | Filter controls (state, labels, assignee, milestone) |
| `IssueList.vue` | Scrollable issue list rendering `IssueCard` components |
| `IssueStats.vue` | Aggregate statistics bar (open count, closed count, average age) |
| `IngestForm.vue` | Form for ingesting an issue as a new document into the platform |
| `Pagination.vue` | Page navigation component |
| `PipelineActivityFeed.vue` | Real-time feed of pipeline activity related to issues |

## Usage

The cell is an **admin cell** (category: `admin`) rendered inside the cockpit-vue shell. It communicates with `issuesService.js` and `issuesDashboardService.js` from `@artifacts/shared/services/`.

## Related Documentation

- [Issues Dashboard Cell Root](../) - Full cell overview and `type.json` specification
- [Shared Services](../../../../shared/services/) - `issuesService.js`, `issuesDashboardService.js`
- [Shared i18n Locales](../../../../shared/i18n/locales/) - Base translations extended here
