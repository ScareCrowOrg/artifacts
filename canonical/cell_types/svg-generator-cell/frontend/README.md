# SVG Generator Cell – Frontend

## Purpose

Vue 3 frontend for the **SVG Generator Cell** — a BaseCell that generates SVG visualizations from text prompts using LLM services.

## Content Index

| File | Description |
|------|-------------|
| [`SvgGeneratorCell.ts`](./SvgGeneratorCell.ts) | BaseCell implementation — `generate` action; delegates to `/api/cells/execute-ephemeral`; category: `visualization` |
| [`View.vue`](./View.vue) | Main component — prompt input, SVG preview with zoom/pan, download button |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [`tests/`](./tests/) | Frontend unit and component tests |
| [`translations/`](./translations/) | `en.json`, `pt-BR.json` — i18n strings |

## Related

- [`../`](../) — SVG Generator Cell root
- [`../../asset-prototyping-cell/`](../../asset-prototyping-cell/) — Uses SVG Generator as Stage 2 (PNG → SVG vectorization)
