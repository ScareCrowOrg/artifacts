# AI Models Cell – Pinia Store

## Purpose

Pinia store for managing AI model provider configuration state in the AI Models Cell frontend.

## Content Index

| File | Description |
|------|-------------|
| [`aiModelsStore.ts`](./aiModelsStore.ts) | Pinia store (`useAIModelsStore`) — state for all provider configs (Ollama, Gemini, OpenAI), loading flags, and error state |

## How to Use

```typescript
import { useAIModelsStore } from './aiModelsStore'

const store = useAIModelsStore()
store.setConfig('ollama', { host: 'http://localhost:11434' })
```

## Related

- [`../composables/useAIModels.ts`](../composables/useAIModels.ts) — Composable that consumes this store
- [`../`](../) — AI Models Cell frontend root
