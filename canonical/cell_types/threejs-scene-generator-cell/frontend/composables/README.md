# Three.js Scene Generator Cell – Frontend Composables

## Purpose

Vue 3 composable for managing Three.js scene lifecycle in the frontend.

## Content Index

| File | Description |
|------|-------------|
| [`useThreeJSScene.ts`](./useThreeJSScene.ts) | `useThreeJSScene()` — scene loading from generated code, initialization, execution in canvas, cleanup on unmount |

## How to Use

```typescript
import { useThreeJSScene } from './composables/useThreeJSScene'

const { loadScene, executeScene, cleanup } = useThreeJSScene(canvasRef)
await loadScene(generatedJsCode)
```

## Related

- [`../`](../) — Three.js Scene Generator Cell frontend root
