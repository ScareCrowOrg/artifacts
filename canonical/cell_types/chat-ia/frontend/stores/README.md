# Chat IA Cell – Pinia Stores

## Purpose

Pinia stores for Chat IA Cell state management.

## Content Index

| File | Description |
|------|-------------|
| [`chat.ts`](./chat.ts) | Chat state store — messages, active model, conversation history reference, streaming state |
| [`ui.ts`](./ui.ts) | UI state store — sidebar visibility, active panel, settings modal open state, loading flags |

## Related

- [`../composables/useChatIA.ts`](../composables/useChatIA.ts) — Primary consumer of these stores
- [`../`](../) — Chat IA Cell frontend root
