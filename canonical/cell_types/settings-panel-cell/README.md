---
processed: true
processed_date: 2026-02-23
themes:
  - cell-types
  - settings
  - rbac
  - configuration
modules:
  - settings-panel-cell
code_verified: false
---

# ⚙️ Settings Panel Cell

## Overview

The **SettingsPanelCell** is a RBAC-aware cell for managing user and global application settings. It provides a tabbed interface for personal preferences (accessible to all users) and global/admin settings (protected by `settings:admin` permission).

## Purpose

Provide a unified, secure, and modular interface for managing application settings with conditional RBAC protection.

## Key Features

- **Conditional RBAC**: User settings accessible to all; global settings require `settings:admin`
- **Theme Management**: Light, dark, and auto themes with system preference detection
- **OAuth Configuration**: Google OAuth client ID and secret management (admin only)
- **Tab-Based UI**: Clean separation between user and admin settings
- **LocalStorage Persistence**: Settings persisted locally with optional backend sync
- **BaseCell Compliance**: Fully implements BaseCell interface

## Directory Structure

```
settings-panel-cell/
├── README.md                           # This file
├── type.json                           # Cell metadata and configuration
├── frontend/                           # Frontend implementation
│   ├── SettingsPanelCell.ts            # BaseCell implementation
│   ├── View.vue                        # Main Vue component (tab navigation)
│   ├── components/                     # UI components
│   │   ├── UserSettings.vue            # Personal preferences (no RBAC)
│   │   ├── AdminSettings.vue           # Global settings (RBAC protected)
│   │   ├── ThemeSettings.vue           # Theme configuration
│   │   └── LayoutSettings.vue          # Layout preferences
│   ├── composables/                    # Vue composables
│   │   └── useSettings.ts              # Settings management logic
│   ├── stores/                         # State management
│   │   └── settingsStore.ts            # Settings state (migrated from cockpit-vue)
│   └── tests/                          # Test files
│       ├── SettingsPanelCell.spec.ts   # Cell logic tests
│       ├── View.spec.ts                # View component tests
│       └── components/                 # Component tests
│           ├── UserSettings.spec.ts
│           └── AdminSettings.spec.ts
```

## Technical Details

- **TypeScript**: All frontend code uses TypeScript (RULESET.md Rule 4.5)
- **File Size**: All files under 500 lines (RULESET.md Rule 1.1)
- **Canonical Cell**: Follows BaseCell v1.0 structure
- **RBAC Integration**: Uses permissions store for access control
- **Test Coverage**: 90%+ coverage target (RULESET.md Rule 3.1)

## Usage

### User Settings (No Permission Required)

```typescript
const cell = new SettingsPanelCell()

// Get user settings
const result = await cell.execute({
  action: 'get',
  scope: 'user'
})

// Update user theme
await cell.execute({
  action: 'update',
  scope: 'user',
  settings: {
    theme: 'dark'
  }
})
```

### Global Settings (Requires `settings:admin`)

```typescript
// Get global settings
const result = await cell.execute({
  action: 'get',
  scope: 'global'
})

// Update global settings (requires permission)
await cell.execute({
  action: 'update',
  scope: 'global',
  settings: {
    defaultTheme: 'light',
    oauthEnabled: true
  }
})
```

## RBAC Behavior

- **User Settings**: Always accessible, no permission check
- **Global Settings**: Requires `settings:admin` permission
- **Admin Tab**: Hidden in UI if user lacks permission
- **Graceful Degradation**: Users without admin rights see only user settings tab

## Settings Persistence

- **User Settings**: `localStorage.getItem('scareverse_user_settings')`
- **Global Settings**: `localStorage.getItem('scareverse_global_settings')` + optional backend sync
- **Theme**: Applied to `document.documentElement.setAttribute('data-theme', theme)`

## Testing Strategy

- **Unit Tests**: Cell methods (`execute`, `validate`, `describe`)
- **RBAC Tests**: Permission checks for global settings
- **Component Tests**: UI rendering and user interactions
- **Integration Tests**: Settings persistence and theme application
- **Coverage Target**: 90%+ (RULESET.md Rule 3.1)

## Replaces

This cell replaces the following hardcoded components in cockpit-vue:
- `cockpit-vue/src/components/UnifiedSettingsPanelRefactored.vue` (removed)
- Hardcoded panel in `App.vue` (removed)

## Related Components

- **AuthStore**: For permission checking (`hasPermission`)
- **UIStore**: For panel visibility state (if needed)
- **Theme System**: CSS variables and data-theme attribute

---

**Version**: 1.0.0  
**Category**: system  
**Status**: Active
