# AI Models Cell – Composables

## Purpose

Vue 3 composable for the AI Models Cell providing reactive state management for AI provider configurations.

## Content Index

| File | Description |
|------|-------------|
| [`useAIModels.ts`](./useAIModels.ts) | Main composable — provider metadata, reactive config state, `loadConfig()`, `saveConfig()`, `testConnection()` methods |

## How to Use

```typescript
import { useAIModels } from './useAIModels'

const { providers, currentProvider, loadConfig, saveConfig } = useAIModels(cell)

await loadConfig('ollama')
await saveConfig('ollama', { host: 'http://localhost:11434' })
```

## Related

- [`../stores/aiModelsStore.ts`](../stores/aiModelsStore.ts) — Pinia store used internally by this composable
- [`../`](../) — AI Models Cell frontend root
