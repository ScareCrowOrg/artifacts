# AI Models Cell – Frontend

## Purpose

Vue 3 frontend implementation for the **AI Models Cell**, a BaseCell v1.0 admin cell that provides a permission-protected interface for managing AI model configurations across multiple providers (Ollama, Gemini, OpenAI).

Requires `ai-models:admin` permission for all operations.

## Content Index

### Files

| File | Description |
|------|-------------|
| [`AIModelsCell.ts`](./AIModelsCell.ts) | BaseCell implementation — defines cell actions (`get`, `update`, `test-connection`), validation, and health check |
| [`View.vue`](./View.vue) | Main cell Vue component — tabbed provider UI, loading/error states, form rendering |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`components/`](./components/) | Per-provider settings components (`GeminiSettings.vue`, `OllamaSettings.vue`, `OpenAISettings.vue`) |
| [`composables/`](./composables/) | `useAIModels.ts` — reactive composable for provider config management |
| [`stores/`](./stores/) | `aiModelsStore.ts` — Pinia store for AI model configuration state |
| [`tests/`](./tests/) | `AIModelsCell.test.ts` — unit tests for the cell implementation |

## How to Use

The cell is registered via the canonical cell loader. To use in a notebook:

```typescript
import { AIModelsCell } from '@/cell_types/ai-models-cell/frontend/AIModelsCell'

const cell = new AIModelsCell(cellUUID, notebook)
await cell.run({ action: 'get', provider: 'ollama' })
```

The `View.vue` component is rendered automatically by the cell framework when the cell is active in a notebook.

## Related

- [`../`](../) — AI Models Cell root (backend + frontend)
- [BaseCell Framework](../../../../cockpit-vue/src/types/BaseCell.ts) — Base class this cell extends
