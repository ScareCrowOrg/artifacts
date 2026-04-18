# Calculator Cell – Frontend

## Purpose

Vue 3 frontend for the **Calculator Cell** — a pure-JavaScript proof-of-concept (PoC) BaseCell demonstrating the BaseCell interface with headless execution. Performs basic math operations with no backend dependency.

This cell is used as a reference implementation for testing the BaseCell framework.

## Content Index

| File | Description |
|------|-------------|
| [`CalculatorCell.ts`](./CalculatorCell.ts) | BaseCell PoC implementation — supports `add`, `subtract`, `multiply`, `divide`, `power`, `modulo` operations; pure JS, no backend |
| [`View.vue`](./View.vue) | Calculator UI component — numeric input, operation selector, result display |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`tests/`](./tests/) | Unit tests for the calculator cell |

## How to Use

```typescript
import { CalculatorCell } from './CalculatorCell'

const cell = new CalculatorCell(cellUUID, notebook)
const result = await cell.run({ operation: 'add', a: 5, b: 3 })
// result.data.result === 8
```

## Related

- [`../`](../) — Calculator Cell root
- [BaseCell Framework](../../../../cockpit-vue/src/types/BaseCell.ts) — The framework this cell demonstrates
