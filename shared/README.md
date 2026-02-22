# Artifacts Shared Module

This directory contains shared utilities, stores, and composables used across all cells in the artifacts ecosystem.

## Purpose

The shared module provides:
- **Stores**: Shared Pinia stores for cross-cell communication
- **Composables**: Reusable Vue composables for common cell operations
- **Types**: Shared TypeScript interfaces and types
- **Utils**: Common utility functions

## Key Components

### Cell Instances Store

**Location**: `stores/cellInstancesStore.ts`

A neutral Pinia store that acts as a bridge between cockpit-vue (core UI) and cell-specific functionality. Enables cells to discover and communicate with other running cell instances.

**Key Features**:
- Register/unregister cell instances
- Query instances by ID or type
- No cell-specific logic in core UI
- Clean separation of concerns

**Usage**:
```typescript
import { useCellInstancesStore } from '@artifacts/shared/stores/cellInstancesStore'

const store = useCellInstancesStore()

// Register a cell (called by cockpit-vue)
store.registerInstance(cellId, cellType, instance, { title: 'My Cell' })

// Query for cells (called by other cells)
const chatCell = store.getFirstInstanceByType('chat-ia')
```

### Cell Instances Composable

**Location**: `composables/useCellInstances.ts`

Helper composable for easy cell discovery and communication.

**Usage**:
```typescript
import { useCellInstances } from '@artifacts/shared/composables/useCellInstances'

const { getChatInstance, sendToChat, hasChatCell } = useCellInstances()

// Check if chat is available
if (hasChatCell()) {
  // Send content to chat
  sendToChat('fragment.md', fragmentContent, 'text')
}

// Or get instance directly
const chatCell = getChatInstance()
if (chatCell?.instance) {
  chatCell.instance.addAttachment(...)
}
```

## Architecture

### Before (Tightly Coupled)
```
cockpit-vue (CORE)
  ↓ (hardcoded imports)
  → DefaultCellView.vue
    → useChatStore (from @/stores/chat.ts)
      → ChatIA-specific logic
```

**Problems**:
- Core UI knows about specific cell types
- Cannot remove cell-specific stores without breaking core
- Not scalable for new cell types

### After (Decoupled via Bridge)
```
artifacts/shared/stores/cellInstancesStore.ts ← Neutral Bridge
    ↑                              ↑
    |                              |
cockpit-vue (registers)     artifacts/cells/ (queries)
  └─ DynamicWorkspace            └─ useCellInstances()
     └─ registerInstance()           └─ getChatInstance()
                                        └─ sendToChat()
```

**Benefits**:
- Core UI is cell-agnostic
- Cells can communicate without coupling
- Easy to add new cell types
- Clean separation of concerns

## Directory Structure

```
artifacts/shared/
├── README.md                        # This file
├── stores/
│   └── cellInstancesStore.ts       # Cell registry store
├── composables/
│   └── useCellInstances.ts         # Cell discovery helpers
├── types/                           # (future) Shared TypeScript types
└── utils/                           # (future) Common utilities
```

## Guidelines

### For Core UI Developers (cockpit-vue)

1. **Register cells**: Call `registerInstance()` after cell creation
2. **Unregister cells**: Call `unregisterInstance()` when cells are removed
3. **No cell-specific logic**: Keep core UI cell-agnostic

### For Cell Developers (artifacts/)

1. **Use the composable**: Import `useCellInstances` for easy access
2. **Check availability**: Always check if target cell exists before calling methods
3. **Handle gracefully**: Don't assume other cells are present
4. **Document interactions**: If your cell depends on others, document it

## Examples

### Example 1: Sending Fragment to Chat

```typescript
import { useCellInstances } from '@artifacts/shared/composables/useCellInstances'

function sendFragmentToChat(fragment: Fragment) {
  const { sendToChat, hasChatCell } = useCellInstances()
  
  if (!hasChatCell()) {
    console.warn('Chat cell not available')
    return false
  }
  
  return sendToChat(
    `fragment-${fragment.id}.md`,
    fragment.content,
    'text'
  )
}
```

### Example 2: Discovering All Cells

```typescript
import { useCellInstances } from '@artifacts/shared/composables/useCellInstances'

function listActiveCells() {
  const { getAllCells } = useCellInstances()
  
  const cells = getAllCells()
  console.log(`Active cells (${cells.length}):`)
  
  cells.forEach(cell => {
    console.log(`- ${cell.title} (${cell.cellType})`)
  })
}
```

### Example 3: Advanced - Direct Store Access

```typescript
import { useCellInstancesStore } from '@artifacts/shared/stores/cellInstancesStore'

const store = useCellInstancesStore()

// Get all file-editor cells
const fileEditors = store.getInstancesByType('file-editor')

// Check if specific cell exists
if (store.hasInstance('my-cell-id')) {
  const cell = store.getInstance('my-cell-id')
  // Use cell instance
}
```

## Related Documentation

- [RULESET.md](/docs/official/RULESET.md) - Project rules and conventions
- [ADDING_NEW_CELL_TYPE.md](/docs/official/ADDING_NEW_CELL_TYPE.md) - Cell development guide
- [Phase 7B Issue](/docs/issues/) - Original implementation issue

## Status

- ✅ **Cell Instances Store**: Implemented
- ✅ **Cell Instances Composable**: Implemented
- 🚧 **Integration**: In progress
- ⏳ **Testing**: Pending
- ⏳ **Documentation**: Ongoing
