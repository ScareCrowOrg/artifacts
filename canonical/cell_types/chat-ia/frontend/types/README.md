# Chat IA Cell – Type Definitions

## Purpose

TypeScript type definitions for the Chat IA Cell frontend.

## Content Index

| File | Description |
|------|-------------|
| [`chat.ts`](./chat.ts) | Core chat interfaces — `ChatMessage`, `ChatModel`, `ConversationHistory`, `Attachment`, `AgentTrace`, `ToolCall` |

## How to Use

```typescript
import type { ChatMessage, ChatModel } from './types/chat'

const message: ChatMessage = {
  content: 'Hello, AI!',
  role: 'user',
  timestamp: Date.now()
}
```

## Related

- [`../`](../) — Chat IA Cell frontend root
- [`../composables/useChatIA.ts`](../composables/useChatIA.ts) — Primary consumer of these types
