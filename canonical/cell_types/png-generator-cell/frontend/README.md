# PNG Generator Cell – Frontend

## Purpose

Vue 3 frontend for the **PNG Generator Cell** — a BaseCell that provides text-to-image generation and background removal via Stable Diffusion, with direct integration to the `execute-ephemeral` endpoint.

## Content Index

| File | Description |
|------|-------------|
| [`PngGeneratorCell.ts`](./PngGeneratorCell.ts) | BaseCell implementation — `generate` and `removeBackground` actions; delegates to `/api/cells/execute-ephemeral` |
| [`View.vue`](./View.vue) | Main component — prompt input, generation settings (model, steps, guidance), output image display, background removal toggle |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`tests/`](./tests/) | Frontend unit and component tests |
| [`translations/`](./translations/) | `en.json`, `pt-BR.json` — i18n strings |

## Related

- [`../`](../) — PNG Generator Cell root
- [`../../asset-prototyping-cell/`](../../asset-prototyping-cell/) — Uses PNG Generator as Stage 1
- [`../../content-manager-cell/frontend/components/PersistModal.vue`](../../content-manager-cell/frontend/components/PersistModal.vue) — Persist generated images
