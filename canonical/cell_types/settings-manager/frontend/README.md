# Settings Manager Cell – Frontend

Vue 3 frontend component for the Settings Manager Cell. Provides the full administrative UI for listing, creating, updating, deleting settings, viewing modification history, rolling back values, and pushing to Redis L1.

## Purpose

`View.vue` is the main cell component rendered by the ScareVerse notebook runner. It communicates with the Python backend via the standard cell action protocol and presents a tabbed interface covering all settings management operations.

## Structure

```
frontend/
├── View.vue               # Main cell component (full CRUD + history + Redis push)
├── tests/
│   └── View.spec.ts       # Vitest/Vue Test Utils component tests
└── translations/
    └── en.json            # English i18n translation strings
```

## Key Features

- **Settings List**: Grouped by category, shows type and current value
- **Create Dialog**: New setting form with type selector (`string`, `number`, `boolean`, `json`)
- **Inline Edit**: Update existing setting values with type coercion validation
- **Delete**: Removes setting with confirmation
- **History Tab**: Full modification log with timestamps
- **Rollback**: Restore any setting to a previous value from history
- **Push to Redis**: One-click button to propagate all settings to Redis L1

## i18n

All user-facing strings are externalized to `translations/en.json` under the `settingsManager` namespace. The component uses `$t('settingsManager.*')` throughout.

## Running Tests

```bash
cd artifacts/canonical/cell_types/settings-manager
npx vitest run frontend/tests/View.spec.ts
```

## Theme Compliance

The component uses Tailwind CSS design tokens (e.g., `bg-surface`, `text-text-primary`, `border-border`) with full dark mode support via `dark:` variants.

## Related Documentation

- [Cell README](../README.md) — Cell overview and actions
- [Backend](../backend/) — Python backend implementation
- [Cell Docs](../docs/README.md) — Full API reference
