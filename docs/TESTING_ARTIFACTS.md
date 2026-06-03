# Testing Artifacts Independently of Cockpit-Vue

> **Data:** 2026-06-02
> **Context:** PR #2983 — 3D Mesh Cell Save/Load Fix
> **Origem:** [Resolution Report](../../docs/RESOLUTION_REPORT.md) — relatório completo do problema e solução.
> **Problema Resolvido:** Testes de cell types não podiam importar `BaseCell` real porque os aliases `@/types`, `@/utils` só existiam no `vitest.config.js` do cockpit-vue.

---

## Sumário

- [Contexto](#contexto)
- [Arquitetura da Solução](#arquitetura-da-solução)
- [Configuração: `artifacts/vitest.config.js`](#configuração-artifactsvitestconfigjs)
- [Stubs para Resolução de Módulos](#stubs-para-resolução-de-módulos)
- [Pattern de Mock em Testes](#pattern-de-mock-em-testes)
- [Guia: Adaptar Testes Legados (`describe.skip`)](#guia-adaptar-testes-legados-describeskip)
- [Template para Novos Testes](#template-para-novos-testes)
- [Mapeamento de Células com Testes Pendentes](#mapeamento-de-células-com-testes-pendentes)
- [Lições Aprendidas](#lições-aprendidas)
- [Arquivos Gerados](#arquivos-gerados)

---

## Contexto

### O Problema Original

Todo teste de cell type no repositório seguia o mesmo padrão **quebrado**:

```typescript
// artifacts/canonical/cell_types/*/frontend/tests/*Cell.test.ts
// import { XxxCell } from '../XxxCell' // ← comentado: "Module has unresolvable BaseCell dependency"

// Stub for non-existent module
class XxxCell {
  async execute(input) { return { status: 'ok', output: {} } }
  validate(input) { return [] }
  // ...
}

describe.skip('XxxCell', () => { /* ... */ })
```

**Sintomas:**
- Testes nunca executam (`describe.skip`)
- Stub retorna sempre valores fixos (`validate()` retorna `[]` sempre)
- Cobertura real: **zero**
- Dead code: 13 arquivos de teste, todos pulados

### Root Cause

O `MeshPrototypingCell.ts` (e toda cell type que estende `BaseCell`) importa:

```typescript
import { BaseCell, createHealthyResult } from '@/types/BaseCell'
import apiService from '@/services/apiService.js'
import { ENDPOINTS } from '@/config/endpoints.js'
import { createLogger } from '@/utils/logger'
```

As cells usam o alias `@/types` e `@/utils`, que **só existiam** no `vitest.config.js` do cockpit-vue:

```javascript
// cockpit-vue/vitest.config.js
resolve: {
  alias: {
    '@/types': path.resolve(__dirname, '../artifacts/shared/types'),
    '@/utils': path.resolve(__dirname, '../artifacts/shared/utils'),
    // ...
  }
}
```

**Problema duplo:**
1. Rodar vitest de fora do cockpit-vue → aliases `@/types` e `@/utils` não resolvem → import quebra
2. Rodar vitest de dentro do cockpit-vue → glob patterns com `path.resolve(__dirname, '..')` produzem backslashes no Windows → fast-glob não encontra os arquivos de teste

---

## Arquitetura da Solução

A solução cria um **ponto de entrada de testes autossuficiente** dentro de `artifacts/`, eliminando a dependência do cockpit-vue para rodar testes de cell types.

```
artifacts/
├── vitest.config.js          ← NOVO: config autossuficiente
├── tests/
│   └── stubs/
│       ├── apiService.js     ← NOVO: stub para resolução de specifier
│       └── endpoints.js      ← NOVO: stub para resolução de specifier
└── canonical/cell_types/
    └── 3d-mesh-prototyping-cell/
        └── frontend/
            └── tests/
                ├── MeshPrototypingCell.spec.ts  ← NOVO: teste real (49 testes)
                └── MeshPrototypingCell.test.ts  ← legado (describe.skip, mantido)
```

### Fluxo de Resolução

```
Test file → vi.mock('@/services/apiService.js') → registra mock
         → import { MeshPrototypingCell } from '../MeshPrototypingCell'
           → MeshPrototypingCell.ts → import BaseCell from '@/types/BaseCell'
             → vitest resolve alias: '@/types' → 'artifacts/shared/types/BaseCell.ts'
           → MeshPrototypingCell.ts → import apiService from '@/services/apiService.js'
             → vitest resolve alias: '@/services/apiService.js' → 'artifacts/tests/stubs/apiService.js'
             → vitest checka: tem mock registrado? SIM → retorna factory da mock
```

---

## Configuração: `artifacts/vitest.config.js`

Criado em `artifacts/vitest.config.js` (sem dependência de cockpit-vue):

```javascript
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    include: [
      './canonical/cell_types/**/tests/**/*.spec.ts',
      './canonical/cell_types/**/tests/**/*.test.ts',
    ],
  },
  resolve: {
    alias: {
      '@/types': path.resolve(__dirname, 'shared/types'),
      '@/utils': path.resolve(__dirname, 'shared/utils'),
      '@/services/apiService.js': path.resolve(__dirname, 'tests/stubs/apiService.js'),
      '@/config/endpoints.js': path.resolve(__dirname, 'tests/stubs/endpoints.js'),
    },
  },
})
```

### Decisões Arquiteturais

| Alias | Resolve para | Motivo |
|-------|-------------|--------|
| `@/types` | `artifacts/shared/types` | BaseCell.ts, interfaces — vivem em artifacts |
| `@/utils` | `artifacts/shared/utils` | logger.js, cellTypeLoaderUtil.ts — vivem em artifacts |
| `@/services/apiService.js` | stub em `tests/stubs/` | Real fica no cockpit-vue, mas é mocked via `vi.mock()` |
| `@/config/endpoints.js` | stub em `tests/stubs/` | Real fica no cockpit-vue, mas é mocked via `vi.mock()` |

### Uso

```bash
# Da raiz do repo:
npx vitest run --config artifacts/vitest.config.js

# Ou de dentro de artifacts/:
cd artifacts && npx vitest run
```

---

## Stubs para Resolução de Módulos

`vitest` precisa **resolver** o specifier da importação mesmo quando o módulo é mockado por `vi.mock()`. Sem os stubs, Vite lança `Failed to resolve import`.

```javascript
// artifacts/tests/stubs/apiService.js
export default {
  fetch: () => Promise.reject(new Error('Stub — must be mocked in test')),
}

// artifacts/tests/stubs/endpoints.js
export const ENDPOINTS = {}
```

### Por que stubs e não arquivos reais?

- `apiService.js` e `endpoints.js` são do cockpit-vue (fora do escopo de `artifacts/`)
- Em teste, são **sempre mockados** via `vi.mock()` com factory
- Stub existe apenas para **resolução do specifier** — o conteúdo nunca é executado

> ⚠️ **Importante:** Se a cell type que você está testando importar módulos além de `@/services/apiService.js` e `@/config/endpoints.js`, será necessário adicionar stubs correspondentes no diretório `artifacts/tests/stubs/` e aliases no `artifacts/vitest.config.js`.

---

## Pattern de Mock em Testes

### Módulos que SEMPRE devem ser mockados

```typescript
// Module-level mocks (hoisted por vitest ANTES dos imports)
vi.mock('@/services/apiService.js', () => ({
  default: { fetch: vi.fn() }
}))

vi.mock('@/config/endpoints.js', () => ({
  ENDPOINTS: {
    executeEphemeralCell: 'http://localhost:5050/api/cells/execute-ephemeral',
    systemStatus: 'http://localhost:5050/api/status'
  }
}))

vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn()
  })
}))

// Real import (funciona porque os aliases do vitest.config.js resolvem)
import { MeshPrototypingCell } from '../MeshPrototypingCell'
```

### Regras

1. **Module-level**: Mocks DEVEM estar no nível do módulo (fora de `describe`/`it`), pois o vitest hoista `vi.mock()` para o topo do arquivo
2. **Factory**: A factory de mock deve retornar o objeto que substitui o módulo real
3. **`vi.fn()`**: Use `vi.fn()` para que cada teste possa fazer assertions no mock
4. **`beforeEach`**: Sempre chame `vi.clearAllMocks()` no `beforeEach` para evitar vazamento entre testes

---

## Guia: Adaptar Testes Legados (`describe.skip`)

### Checklist

- [ ] **Verificar** se `artifacts/vitest.config.js` já existe (reutilizar)
- [ ] **Adicionar stubs** se a cell importar módulos além de `@/services/apiService.js` e `@/config/endpoints.js`
- [ ] **Adicionar aliases** no `artifacts/vitest.config.js` se necessário
- [ ] **Renomear** arquivo de `.test.ts` com `describe.skip` para `.spec.ts`
- [ ] **Trocar stub class** por import real do cell type
- [ ] **Adicionar mocks** para `@/services/apiService.js`, `@/config/endpoints.js`, `@/utils/logger`
- [ ] **Rodar** `npx vitest run --config artifacts/vitest.config.js`
- [ ] **Validar cobertura** — conferir se branches não cobertas são aceitáveis

---

## Template para Novos Testes

```typescript
/**
 * @file XxxCell.spec.ts
 * @description Unit tests for XxxCell
 */

import { describe, it, expect, beforeAll, beforeEach, vi } from 'vitest'

// ── Module-level mocks ──────────────────────────────────────────────────────
vi.mock('@/services/apiService.js', () => ({
  default: { fetch: vi.fn() }
}))
vi.mock('@/config/endpoints.js', () => ({
  ENDPOINTS: { /* ... */ }
}))
vi.mock('@/utils/logger', () => ({
  createLogger: () => ({
    debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn()
  })
}))

// ── Real imports ────────────────────────────────────────────────────────────
import { XxxCell } from '../XxxCell'

// ── Suite ───────────────────────────────────────────────────────────────────
describe('XxxCell', () => {
  let cell: XxxCell

  beforeAll(() => { cell = new XxxCell() })
  beforeEach(() => { vi.clearAllMocks() })

  describe('validate()', () => { /* ... */ })
  describe('describe()', () => { /* ... */ })
  describe('execute()', () => { /* ... */ })
  describe('health_check()', () => { /* ... */ })
  describe('getState() / setState()', () => { /* ... */ })
})
```

---

## Mapeamento de Testes em artifacts/

### ✅ Testes que JÁ RODAM COM IMPORT REAL

| Cell Type | Arquivo | Tests | Coverage |
|-----------|---------|:-----:|:--------:|
| `3d-mesh-prototyping-cell` | `MeshPrototypingCell.spec.ts` | 49 | 100% stmts ✅ |
| `calculator-cell` | `CalculatorCell.spec.ts` | 29 | 93.67% stmts ✅ |
| `content-selection-cell` | `ContentSelectionCell.spec.ts` | — | — |
| `content-upload-cell` | `ContentUploadCell.spec.ts` | — | — |
| `inbox-cell` | `InboxCell.spec.ts` | — | — |
| `messages-cell` | `MessagesCell.spec.ts` | — | — |
| `planet-chat-cell` | `PlanetChatCell.spec.ts` | — | — |
| `requests-cell` | `RequestsCell.spec.ts` | — | — |
| `wikipedia-search-cell` | `WikipediaSearchCell.test.ts` | — | — |
| `artifacts-explorer-cell` | `View.spec.ts` | — | — |
| `xterm-terminal-cell` | `resolveWsUrl.spec.ts` | — | — |

### ⏸️ Testes que RODAM MAS USAM STUB (não importam cell real)

| Cell Type | Arquivo | Observação |
|-----------|---------|------------|
| `user-selection-cell` | `UserSelectionCell.test.ts` | Stub inline + mocks, sem `describe.skip` |
| `manual-capture-cell` | `ManualCaptureCell.test.ts` | Stub inline, sem `describe.skip` |
| `artifacts-explorer-cell` | `ArtifactsExplorerCell.test.ts` | Stub inline + mocks, sem `describe.skip` |

### 🔴 Alvos para Remediar (com `describe.skip`)

#### Já remediado

| Cell Type | Arquivo | Status |
|-----------|---------|--------|
| `calculator-cell` | `CalculatorCell.test.ts` → `CalculatorCell.spec.ts` | ✅ **REMEDIADO** — 29 testes, 93.67% stmts |

#### Próximos — Fácil (frontend-only)

| Cell Type | Arquivo(s) | Prioridade |
|-----------|------------|:----------:|
| `calculator-cell` | `CalculatorCell.test.ts` (legado) | ✅ resolvido |
| `fragment-editor-cell` | `FragmentEditorCell.test.ts` | ⭐ 1 |
| `log-toggle-cell` | `View.spec.ts` | ⭐ 2 |
| `settings-manager` | `View.spec.ts` | ⭐ 3 |

#### Médio (full-stack, cell class)

| Cell Type | Arquivo(s) | Prioridade |
|-----------|------------|:----------:|
| `ai-models-cell` | `AIModelsCell.test.ts` | ⭐ 4 |
| `content-explorer-cell` | `ContentExplorerCell.test.ts`, `composables.test.ts` | ⭐ 5 |
| `content-manager-cell` | `ContentManagerCell.test.ts` | ⭐ 6 |
| `content-type-manager-cell` | `ContentTypeManagerCell.test.ts` | ⭐ 7 |
| `prompt-enhancer-cell` | `PromptEnhancerCell.test.ts` | ⭐ 8 |
| `roles-management-cell` | `RolesManagementCell.test.ts` | ⭐ 9 |

#### Complexo (View.vue + cell class + múltiplos componentes)

| Cell Type | Arquivo(s) | Prioridade |
|-----------|------------|:----------:|
| `chat-ia` | `View.spec.ts` | ⭐ 10 |
| `file-editor-v2` | `View.spec.ts` | ⭐ 11 |
| `notebook-cells-admin-cell` | `NotebookCellsAdminCell.spec.ts` | ⭐ 12 |
| `unclassified-cell` | `View.spec.ts` | ⭐ 13 |
| `xterm-terminal-cell` | `View.spec.ts` | ⭐ 14 |
| `issues-dashboard-cell` | 3 specs | ⭐ 15 |
| `settings-panel-cell` | 4 specs | ⭐ 16 |
| `pipeline-monitoring-cell` | 4 specs | ⭐ 17 |
| `png-generator-cell` | 2 (cell + View) | ⭐ 18 |
| `svg-generator-cell` | 2 (cell + View) | ⭐ 19 |
| `asset-prototyping-cell` | `AssetPrototypingCell.test.ts` | ⭐ 20 |
| `3d-mesh-prototyping-cell` | `MeshPrototypingCell.test.ts` (legado) | ⭐ 21 |

#### Viewers

| Viewer | Arquivo(s) | Prioridade |
|--------|------------|:----------:|
| `dynamic-workspace` | 4 test files | ⭐ 22 |

---

## Lições Aprendidas

### 1. `vi.mock()` Precisa de Resolução, Não de Conteúdo

O maior obstáculo técnico: `vi.mock('@/services/apiService.js', factory)` gera um `await import('@/services/apiService.js')` no código transformado. Mesmo que o módulo seja substituído pela factory, o **specifier precisa ser resolvível** pelo Vite. Sem alias ou stub, a importação falha antes do mock ser aplicado.

### 2. Windows + `path.resolve()` + Backslashes = Glob Quebrado

No `cockpit-vue/vitest.config.js`:
```javascript
path.resolve(__dirname, '../artifacts/canonical/cell_types/**/tests/**/*.spec.ts')
// Produz: D:\projetos\...\cell_types\**\tests\**\*.spec.ts ← BACKSLASHES
// fast-glob no Windows não interpreta backslashes corretamente com **/
```

No `artifacts/vitest.config.js` (solução):
```javascript
'./canonical/cell_types/**/tests/**/*.spec.ts'
// forward slashes — funciona em qualquer SO
```

### 3. Arquivos `.spec.ts` vs `.test.ts`

Vitest descobre ambos os padrões. Arquivos legados com `describe.skip` continuam sendo encontrados mas não executam. **Decisão:** não remover arquivos legados para manter compatibilidade. Arquivos novos devem usar `.spec.ts` para clara distinção entre "teste real" e "teste legado".

### 4. Cobertura no `artifacts/vitest.config.js`

O coverage configurado no cockpit-vue tem thresholds (90% linhas, 80% branches) que **NÃO** se aplicam ao `artifacts/vitest.config.js`. Se quiser enforced thresholds para cell types, adicione:

```javascript
coverage: {
  provider: 'v8',
  thresholds: {
    lines: 90,
    functions: 90,
    branches: 80,
    statements: 90,
  },
}
```

### 5. Stubs São Específicos por Cell Type

Se uma cell type importa módulos customizados (ex: `@/services/someService.js`), é necessário:
1. Criar stub em `artifacts/tests/stubs/`
2. Adicionar alias correspondente em `artifacts/vitest.config.js`
3. Mockar via `vi.mock()` no arquivo de teste

---

## Arquivos Gerados

| Arquivo | Descrição |
|---------|-----------|
| `artifacts/vitest.config.js` | Config autossuficiente para testar cell types |
| `artifacts/tests/stubs/apiService.js` | Stub para `@/services/apiService.js` |
| `artifacts/tests/stubs/endpoints.js` | Stub para `@/config/endpoints.js` |
| `artifacts/.../MeshPrototypingCell.spec.ts` | Teste real com 49 testes (célula de referência) |

---

> 📎 **Documento original:** [docs/RESOLUTION_REPORT.md](../../docs/RESOLUTION_REPORT.md) — contém o relatório completo de diagnóstico e resolução do problema.
