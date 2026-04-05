---
processed: true
processed_date: 2025-12-26
themes:
  - frontend
  - actions
  - modularization
modules:
  - cockpit-vue
code_verified: true
dead_docs_found: false
---
# Action Registry Modules

This directory contains the modularized action handlers for the Action Registry system.

## Overview

The Action Registry has been modularized from a single large file (`useActionRegistry.js` - 2485 lines) into smaller, focused modules to comply with RULESET.md Rule 1.1 (500-line limit).

## Module Structure

### Core Action Modules

Each module exports a registration function that registers related actions:

#### 1. **githubActions.js** (332 lines)
- **Purpose**: GitHub PR operations
- **Export**: `registerGitHubActions(registerAction)`
- **Actions**:
  - `get_pr_report` - Get PR metadata and statistics
  - `get_pr_changes` - List changed files in PR
  - `get_pr_file_diff` - Get diff for specific file
  - `get_pr_new_file_content` - Get content of newly added files

#### 2. **cellActions.js** (449 lines)
- **Purpose**: Cell management operations
- **Export**: `registerCellActions(registerAction)`
- **Actions**:
  - `list_cells` - List cells with RBAC filtering
  - `get_cell` - Get detailed cell information
  - `execute_cell` - Execute cell using pipeline
  - `update_cell` - Update cell properties
  - `delete_cell` - Delete cell permanently
  - `list_notebook_item_types` - List available notebook types

#### 3. **issuesActions.js** (284 lines)
- **Purpose**: Issues management and monitoring
- **Export**: `registerIssuesActions(registerAction)`
- **Actions**:
  - `trigger_manual_ingest` - Trigger document ingestion
  - `trigger_manual_processing` - Process pending cells
  - `start_automatic_monitoring` - Start monitoring loop
  - `stop_automatic_monitoring` - Stop monitoring loop
  - `pause_queue_processing` - Pause cell processing
  - `resume_queue_processing` - Resume cell processing

#### 4. **runtimeActions.js** (452 lines)
- **Purpose**: Runtime file operations
- **Export**: `registerRuntimeActions(registerAction)`
- **Actions**:
  - `grep` - Search patterns in files (regex support)
  - `find` - Find files by name pattern
  - `read_file` - Read single or multiple files

#### 5. **proposalActions.js** (308 lines)
- **Purpose**: File modification proposals
- **Export**: `registerProposalActions(registerAction)`
- **Actions**:
  - `propose_file_update` - Propose file update with diff
  - `propose_file_creation` - Propose new file creation

#### 6. **utilityActions.js** (114 lines)
- **Purpose**: General utility actions
- **Export**: `registerUtilityActions(registerAction)`
- **Actions**:
  - `create_cell` - Create new cell
  - `open_docs` - Open documentation
  - `copy_to_clipboard` - Copy content to clipboard
  - `navigate` - Navigate to URL

#### 7. **discoveryActions.js** (241 lines)
- **Purpose**: Action discovery and introspection
- **Export**: `registerDiscoveryActions(registerAction)`
- **Actions**:
  - `discover_actions` - List all available actions with metadata

### Utility Module

#### **utils.js** (211 lines)
- **Purpose**: Shared utility functions
- **Exports**:
  - `shouldUseAttachment(content)` - Determine output strategy
  - `truncateIfNeeded(content, type)` - Intelligent content truncation
  - `formatGrepResults(data, pattern)` - Format grep output
  - `formatFindResults(data, pattern)` - Format find output
  - `formatFileSize(bytes)` - Human-readable file sizes
  - `safeDecodeURIComponent(value)` - Safe URI decoding
  - `generateAttachmentFilename(type, pattern)` - Generate attachment names
  - `OUTPUT_STRATEGY_LIMITS` - Configuration constants

## Usage

All modules follow the same pattern:

```javascript
import { registerXxxActions } from './actions/xxxActions'

// In useActionRegistry.js
registerRuntimeActions(registerAction)
registerProposalActions(registerAction)
registerUtilityActions(registerAction)
registerDiscoveryActions(registerAction)
registerGitHubActions(registerAction)
registerCellActions(registerAction)
registerIssuesActions(registerAction)
```

## Dependencies

All action modules depend on:
- `@/utils/logger` - Advanced logging system
- `@/services/apiService` - API communication
- `./utils` - Shared utility functions (as needed)

## Compliance

✅ **RULESET.md Rule 1.1**: All modules are under 500 lines
- Largest module: `cellActions.js` (449 lines) - ✅ Compliant
- Smallest module: `utilityActions.js` (114 lines) - ✅ Compliant
- Total: 2,391 lines across 8 files (average: 299 lines/file)

✅ **RULESET.md Rule 4.7**: All modules use Advanced Logging System
- All actions use `createLogger('action:xxx')` instead of `console.log`

✅ **RULESET.md Rule 4.3**: Technical naming in English
- All function names, variables, and exports in English

## File Size Summary

| File | Lines | Status | Purpose |
|------|-------|--------|---------|
| `cellActions.js` | 449 | ✅ | Cell management |
| `runtimeActions.js` | 452 | ✅ | File operations |
| `githubActions.js` | 332 | ✅ | GitHub PR actions |
| `proposalActions.js` | 308 | ✅ | File proposals |
| `issuesActions.js` | 284 | ✅ | Issues management |
| `discoveryActions.js` | 241 | ✅ | Action discovery |
| `utils.js` | 211 | ✅ | Utilities |
| `utilityActions.js` | 114 | ✅ | General utilities |
| **Total** | **2,391** | ✅ | All modules |

## Migration History

- **Original**: `useActionRegistry.js` (2,485 lines) - ❌ Non-compliant
- **Modularized**: 8 files (2,391 lines total, 299 avg) - ✅ Compliant
- **Reduction**: 94 lines (import consolidation, dead code removal)

## Next Steps

The main `useActionRegistry.js` file should now be updated to import and register all these modularized actions instead of defining them inline.

---

**Last Updated**: 2025-12-26  
**Compliance**: ✅ RULESET.md Rule 1.1, 4.3, 4.7  
**Maintained By**: Frontend Agent
