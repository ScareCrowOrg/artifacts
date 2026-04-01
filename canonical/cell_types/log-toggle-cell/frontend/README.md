# Log Toggle Cell — Frontend

Vue 3 frontend for the Log Toggle Cell, providing a UI for enabling and disabling log namespaces at runtime.

## Purpose

This package contains the frontend implementation of the Log Toggle Cell: a utility cell that lets developers toggle logging namespaces on/off without restarting services, directly from the ScareVerse Cockpit workspace.

## Index

### Files

| File | Description |
|------|-------------|
| `View.vue` | Root Vue component — renders the namespace toggle list and execute button |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| `tests/` | `View.spec.ts` — component tests for the toggle UI |

## Overview

The `View.vue` component presents:

- A list of known log namespaces (e.g., `cockpit.auth`, `cockpit.cells`, `cockpit.render`)
- Toggle switches for each namespace (enable/disable)
- An **Apply** button that triggers cell execution with the current toggle state
- A result summary showing which namespaces were successfully enabled/disabled

The cell communicates with the backend via the standard `execute-ephemeral` endpoint, passing the current toggle selections as `cell_data`.

## Usage

The cell is available in the workspace as a **Utility** cell. Add it to a notebook, configure the desired namespace toggles, and click **Apply** to update the runtime logging configuration.

## Related Documentation

- [Log Toggle Cell Root](../) - Full cell overview and `type.json` specification
- [Log Toggle Backend](../backend/) - Python execution backend
- [Shared Utils / Logger](../../../../shared/utils/) - The logging system this cell controls
