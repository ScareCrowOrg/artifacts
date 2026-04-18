# Chat IA Cell – Composables

## Purpose

Vue 3 composables for the Chat IA Cell frontend. Each composable is isolated per cell instance to support multiple concurrent chat cells in the same notebook.

## Content Index

| File | Description |
|------|-------------|
| [`useChatIA.ts`](./useChatIA.ts) | Primary composable — manages messages, user input, model selection, attachments, streaming, and API interactions; **per-cell isolated state** |
| [`useChatHistory.ts`](./useChatHistory.ts) | Conversation history persistence — load/save/delete chat sessions via Backend API |
| [`useActionDiscovery.ts`](./useActionDiscovery.ts) | Discovers available action links from the current notebook context for agent mode |
| [`useConversationTrace.ts`](./useConversationTrace.ts) | Manages conversation trace data — tool call timelines, agent reasoning steps |

## Architecture Note

Composables use **per-cell isolated instances** (not global singletons). Each cell instance passes its `cellUUID` to get an isolated state scope, preventing state leakage between multiple Chat IA cells in the same notebook.

## Related

- [`../components/`](../components/) — Vue components that consume these composables
- [`../stores/`](../stores/) — Pinia stores for shared state
- [`../`](../) — Chat IA Cell frontend root
