# Settings Panel Cell – Frontend

## Purpose

Vue 3 frontend for the **Settings Panel Cell** — an RBAC-aware settings management cell. User settings require no permissions; global/admin settings require `settings:admin`.

## Content Index

| File | Description |
|------|-------------|
| [`SettingsPanelCell.ts`](./SettingsPanelCell.ts) | BaseCell implementation — conditional RBAC, `user-settings` and `admin-settings` action groups |
| [`View.vue`](./View.vue) | Main component — tabbed settings panels (User, Theme, Layout, Admin) with permission gating |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`components/`](./components/) | `AdminSettings.vue`, `LayoutSettings.vue`, `ThemeSettings.vue`, `UserSettings.vue` |
| [`composables/`](./composables/) | `useSettings.ts` — settings load/save state management |
| [`stores/`](./stores/) | `settingsStore.ts` — Pinia store for settings state |
| [`tests/`](./tests/) | `SettingsPanelCell.spec.ts`, `View.spec.ts` — tests (README already present in tests/) |

## Related

- [`../`](../) — Settings Panel Cell root
