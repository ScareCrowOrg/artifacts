# Chat IA Cell – Frontend Services

## Purpose

API service layer for the Chat IA Cell frontend. Handles all HTTP communication with the Backend.

## Content Index

| File | Description |
|------|-------------|
| [`aiChatService.ts`](./aiChatService.ts) | Chat API service — `sendMessage()` (streaming + non-streaming), `getModels()`, `cancelRequest()` via Backend chat endpoints |
| [`tracesService.ts`](./tracesService.ts) | Conversation trace API service — `getTrace()`, `listTraces()` for fetching agent execution traces |

## Related

- [`../composables/useChatIA.ts`](../composables/useChatIA.ts) — Primary consumer of these services
- [`../`](../) — Chat IA Cell frontend root
