# Prompt Enhancer Cell – Frontend

## Purpose

Frontend for the **Prompt Enhancer Cell** — a headless utility BaseCell (no `View.vue`) that enhances prompts with context and best practices. Used as a composable building block by other cells (e.g., PNG Generator).

Part of **BaseCell v1.0 Framework - Phase 3: Utilities**.

## Content Index

| File | Description |
|------|-------------|
| [`PromptEnhancerCell.ts`](./PromptEnhancerCell.ts) | Headless BaseCell — `enhance` action; takes raw prompt and returns enriched version with context injection, style guidance, and quality modifiers |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`tests/`](./tests/) | `PromptEnhancerCell.test.ts` — unit tests (README already present) |

## How to Use

```typescript
import { PromptEnhancerCell } from './PromptEnhancerCell'

const cell = new PromptEnhancerCell(cellUUID, notebook)
const result = await cell.run({ action: 'enhance', prompt: 'a cat', style: 'photorealistic' })
// result.data.enhancedPrompt = 'a photorealistic cat, studio lighting, 8k...'
```

## Related

- [`../`](../) — Prompt Enhancer Cell root
- [`../../png-generator-cell/`](../../png-generator-cell/) — Primary consumer of enhanced prompts
