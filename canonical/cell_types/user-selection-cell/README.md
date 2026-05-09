# user-selection-cell

**Category**: `ephemeral`
**Version**: `1.0.0`
**Icon**: 👤

## Purpose

`user-selection-cell` is an **ephemeral utility cell** that encapsulates the user-selection flow for ScareVerse. It opens a modal overlay with the platform's user list and resolves a Promise with the selected `User` object (or `null` if cancelled).

This cell is **not instantiated directly by end-users** — it is invoked programmatically by other cells via its `show()` method. The primary consumer is `artifacts-explorer-cell` for the allowance flow.

## How to Invoke via `show()`

```typescript
import { UserSelectionCell } from '../user-selection-cell/frontend/UserSelectionCell'

const userCell = new UserSelectionCell()

// Opens overlay and awaits user interaction
const user = await userCell.show({}, {
  mode: 'pick-one',
  title: 'Select user for allowance'
})

if (user) {
  console.log(`Selected: ${user.name}`)
} else {
  // User cancelled
}
```

## Architecture

```
UserSelectionCell.show()
    │
    ├─► useUserSelectionStore.open(title, resolve)
    │       │
    │       └─► isOpen = true  →  View.vue renders overlay
    │
    └─► new Promise((resolve) => { ... })
            │
            ├─► User clicks a name → store.selectUser(user) → resolve(user)
            └─► User clicks Cancel → store.cancel()         → resolve(null)
```

The Pinia store (`store.ts`) is the communication channel between the cell class and the Vue component. No Vue reactivity crosses cell boundaries.

## Communication Pattern (Promise ↔ Store ↔ View)

| Step | Actor | Action |
|------|-------|--------|
| 1 | `UserSelectionCell.show()` | Creates `new Promise`, calls `store.open(title, resolve)` |
| 2 | `store.open()` | Sets `isOpen = true`, stores resolver, calls `loadUsers()` |
| 3 | `View.vue` | Renders modal, shows user list |
| 4a | User selects | `store.selectUser(user)` → resolver called → Promise resolves with `user` |
| 4b | User cancels | `store.cancel()` → resolver called → Promise resolves with `null` |

## Expected Behavior

- ✅ On selection: Promise resolves with `SelectableUser` object
- ✅ On cancel (button or backdrop click): Promise resolves with `null`
- ✅ Errors in `GET /api/users/` (including 403) shown in overlay, cancel available
- ✅ Dark mode supported (Tailwind `dark:` classes)

## Required Permissions

`GET /api/users/` requires the `admin` role. If the caller is not an admin, a 403 error message is displayed in the overlay and the user can only cancel.

## Files

| File | Purpose |
|------|---------|
| `UserSelectionCell.ts` | BaseCell implementation — `show()` override |
| `store.ts` | Pinia store — Promise ↔ View channel |
| `View.vue` | Modal overlay (mounted via `<Teleport to="body">`) |
| `type.json` | Symlink → `../../notebook_item_types/user-selection-cell.json` |
