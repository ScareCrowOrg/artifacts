# Artifacts Manager Cell

## Overview

The `artifacts-manager-cell` is a detail view cell that displays metadata about artifacts from the Artifact Runtime Map and provides management actions (Allowance) for cell-type artifacts.

## Purpose

When a user discovers a cell-type artifact in the `artifacts-explorer-cell` and clicks "Manage", this cell opens in the workspace grid showing:

- Artifact identity (name, icon, version)
- Artifact description
- Full metadata in formatted JSON
- **Allow** button to grant permission access to users

## Flow

```
artifacts-explorer-cell (modal)
  ↓ card → "Manage" button
  ↓ explorerStore.triggerManageArtifact(artifact)
  ↓
App.vue watcher
  ↓ closes explorer modal
  ↓ handleCellTypeSelected('artifacts-manager-cell', { artifactData })
  ↓
artifacts-manager-cell (grid)
  ↓ displays metadata
  ↓ "Allow" → UserSelectionCell → POST /api/local/allowance
```

## Integration Points

- **Explorer Store**: Uses `explorerStore.manageArtifactTarget` to receive artifact data from `artifacts-explorer-cell`
- **App.vue**: Watcher handles `manageArtifactTarget` and creates the cell via `handleCellTypeSelected()`
- **Allowance API**: `POST /api/local/allowance` — existing backend endpoint
- **UserSelectionCell**: Ephemeral overlay for user selection during allowance

## BaseCell Contract

| Method | Description |
|--------|-------------|
| `execute()` | Returns artifact metadata from initial_data |
| `describe()` | CellMetadata with id, name, version, inputs, outputs, tags |
| `validate()` | Validates artifact_id is present |
| `show()` | Returns componentPath for frontend/View.vue |
| `allowArtifact()` | Opens UserSelectionCell, POSTs /api/local/allowance |

## i18n Keys

All text is translated via `$t('artifactsManager.xxx')`. Supported locales:
- `en.json` — English
- `pt-BR.json` — Brazilian Portuguese

## Technical Notes

- **Buffer Local Pattern**: View.vue follows REACTIVITY_ISOLATION.md — props are hydrated into local refs on mount
- **No new backend endpoints**: Reuses existing `POST /api/local/allowance`
- **Store-based communication**: Same pattern as `selectedArtifact` in explorer store
- **TypeScript**: All code is TypeScript (RULESET.md §4.5)
