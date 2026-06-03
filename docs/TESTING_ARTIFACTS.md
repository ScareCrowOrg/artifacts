# Testing Artifacts — Cell Types em artifacts/

> **Data:** 2026-06-03
> **Origem:** [Resolution Report](../../docs/RESOLUTION_REPORT.md)
> **Sessão de limpeza:** 37 describe.skip removidos, 6 import errors deletados, 2 suites fixadas (WikipediaSearch, ManualCapture)
> **Status atual:** ✅ 10 test files | 208 tests | 0 failures | 0 skipped

---

## Sumário

- [Contexto](#contexto)
- [Arquitetura da Solução](#arquitetura-da-solução)
- [Configuração: `artifacts/vitest.config.js`](#configuração-artifactsvitestconfigjs)
- [Stubs para Resolução de Módulos](#stubs-para-resolução-de-módulos)
- [Pattern de Mock em Testes](#pattern-de-mock-em-testes)
- [Mapeamento de Testes — Estado Atual](#mapeamento-de-testes--estado-atual)
- [Células sem Teste Nenhum (Alvos da Skill de Cobertura)](#células-sem-teste-nenhum-alvos-da-skill-de-cobertura)
- [Lições Aprendidas na Sessão de Limpeza (2026-06-02)](#lições-aprendidas-na-sessão-de-limpeza-2026-06-02)
- [Template para Novos Testes](#template-para-novos-testes)
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
- Dead code: 37 arquivos de teste com describe.skip, todos pulados

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
├── vitest.config.js          ← Config autossuficiente
├── tests/
│   └── stubs/
│       ├── apiService.js     ← Stub para resolução de specifier
│       └── endpoints.js      ← Stub para resolução de specifier
├── docs/
│   └── TESTING_ARTIFACTS.md  ← Este documento
└── canonical/cell_types/
    └── 3d-mesh-prototyping-cell/
        └── frontend/tests/
            └── MeshPrototypingCell.spec.ts  ← Teste real (49 testes)
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
cd artifacts && npx vitest run

# Com cobertura:
npx vitest run --coverage

# Filtrar por cell específica:
npx vitest run --coverage.include="**/calculator-cell/**"
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

## Mapeamento de Testes — Estado Atual

> Status pós-limpeza de 2026-06-02: 43 arquivos deletados (37 describe.skip + 6 import errors), 2 suites fixadas.

### ✅ Testes com Import Real (BaseCell Pattern)

Estes arquivos importam a cell type real e testam comportamento verdadeiro:

| Cell Type | Arquivo | Tests | Coverage | Observação |
|-----------|---------|:-----:|:--------:|------------|
| `3d-mesh-prototyping-cell` | `MeshPrototypingCell.spec.ts` | 49 | 100% stmts, 93% branch | ✅ Referência |
| `calculator-cell` | `CalculatorCell.spec.ts` | 29 | 93.67% stmts | ✅ Pure frontend (sem mocks) |
| `manual-capture-cell` | `ManualCaptureCell.spec.ts` | 21 | — | ✅ Pure frontend (sem mocks) |
| `planet-chat-cell` | `PlanetChatCell.spec.ts` | 19 | — | ✅ Mock apiService |
| `wikipedia-search-cell` | `WikipediaSearchCell.test.ts` | 12 | — | ✅ Mock global.fetch |

### ⏸️ Testes com Stub (Local Class)

Estes arquivos usam uma classe stub inline em vez de importar a cell real:

| Cell Type | Arquivo | Tests | Observação |
|-----------|---------|:-----:|------------|
| `inbox-cell` | `InboxCell.spec.ts` | 26 | Stub inline |
| `messages-cell` | `MessagesCell.spec.ts` | 13 | Stub inline |
| `requests-cell` | `RequestsCell.spec.ts` | 13 | Stub inline |
| `user-selection-cell` | `UserSelectionCell.test.ts` | 19 | Stub inline |

### 🔧 Utilitários

| Viewer/Util | Arquivo | Tests | Observação |
|-------------|---------|:-----:|------------|
| `xterm-terminal-cell` | `resolveWsUrl.spec.ts` | 7 | Testa função utilitária, não cell type |

---

## Células sem Teste Nenhum (Alvos da Skill de Cobertura)

Estas células **perderam o único teste** durante a limpeza (tinham `describe.skip` ou import errors) e agora estão **zero coverage**. São alvos da skill de remediação de cobertura.

### Fácil (frontend-only, sem backend — mais rápido)

| Cell Type | Por que é fácil |
|-----------|-----------------|
| `fragment-editor-cell` | Pure frontend (importa só BaseCell) |
| `log-toggle-cell` | Pure frontend (View.vue + composable) |
| `settings-manager` | Pure frontend (View.vue + composable) |
| `content-selection-cell` | Frontend com apiService |
| `content-upload-cell` | Frontend com apiService |

### Médio (full-stack, cell class)

| Cell Type | Observação |
|-----------|------------|
| `ai-models-cell` | Cell class + apiService |
| `content-explorer-cell` | Cell class + composables |
| `content-manager-cell` | Cell class + apiService |
| `content-type-manager-cell` | Cell class + apiService |
| `prompt-enhancer-cell` | Cell class + apiService |
| `roles-management-cell` | Cell class + apiService |
| `asset-prototyping-cell` | Cell class + apiService |
| `png-generator-cell` | Cell class + View.vue |
| `svg-generator-cell` | Cell class + View.vue |

### Complexo (View.vue + cell class + múltiplos componentes)

| Cell Type | Observação |
|-----------|------------|
| `chat-ia` | View.vue + cell class |
| `file-editor-v2` | View.vue + cell class |
| `notebook-cells-admin-cell` | Spec com múltiplos describes |
| `unclassified-cell` | View.vue + cell class |
| `issues-dashboard-cell` | 3 spec files (deletados) |
| `settings-panel-cell` | 4 spec files (deletados) |
| `pipeline-monitoring-cell` | 4 spec files (deletados) |
| `artifacts-explorer-cell` | Cell class + apiService |

### Viewers

| Viewer | Observação |
|--------|------------|
| `dynamic-workspace` | 4 composables, sem teste |

---

## Lições Aprendidas na Sessão de Limpeza (2026-06-02)

### 1. `describe.skip` Polui Relatórios de Cobertura

**Problema:** Arquivos com `describe.skip` são descobertos pelo vitest e aparecem em relatórios como "não testados", mascarando o progresso real.

**Solução:** Ao invés de remediar um por um, faça uma **limpeza geral primeiro**:
1. Delete todos os arquivos com `describe.skip` (ou remova o skip)
2. Delete arquivos com import errors irresolvíveis
3. Depois implemente testes novos do zero

**Resultado:** Relatórios de cobertura passam a refletir apenas código realmente testado.

### 2. Stub vs Real Import — Stub Mente

**Problema:** Stubs inline parecem convenientes mas **divergem silenciosamente** da implementação real:

| Diferença | Stub dizia | Real faz | Impacto |
|-----------|-----------|----------|---------|
| Mensagem de erro | `` `Unknown action: ${action}` `` | `` `Unknown action: ${action}. Supported actions: 'capture', 'wireframe'` `` | Teste passava com stub, falhava com real |
| Trim de conteúdo | Não trima | Trima | Teste asserta string com espaços, real retorna sem |
| `describe()` tags | `expect.arrayContaining(...)` | Array literal `['capture', 'utility', ...]` | Stub retornava objeto Proxy, não array |

**✅ Regra:** Sempre que possível, use **import real** com `vi.mock()` para dependências externas. Nunca confie em stub para validar comportamento.

### 3. Mock Case-Sensitive — O Erro `totalhits` vs `totalHits`

**Problema:** O mock da WikipediaSearchCell usava `totalhits` (minúsculo) mas a API real retorna `totalHits` (camelCase). JavaScript object keys são case-sensitive → `data?.query?.searchinfo?.totalHits` retornava `undefined` → `?? 0` → `totalResults = 0`.

**✅ Lição:** Ao mockar respostas de API, copie EXATAMENTE o formato que a API real retorna. Use `console.log` ou debbuger para ver o objeto real antes de criar o mock.

### 4. Ordem de Validação no `validate()` Pode Esconder Bugs

**Problema em ManualCaptureCell:**
```typescript
validate(input) {
  if (!input.content.trim()) { ... } // ← chamado PRIMEIRO
  if (typeof content !== 'string') { ... } // ← checagem de tipo DEPOIS
}
```

Se `input.content` for um número, `input.content.trim()` lança `TypeError` antes de chegar na validação de tipo.

**✅ Lição:** Teste `validate()` com tipos inesperados (number, null, object) — se der TypeError em vez de retornar array de erros, a cell tem bug de ordenação.

### 5. Vitest + Windows + Backslashes

**Problema:** `path.resolve(__dirname, '..')` produz backslashes (`D:\...\cell_types\**\tests\**\*.spec.ts`), e fast-glob no Windows não interpreta `**/` corretamente com backslashes.

**✅ Solução:** Use forward slashes relativos no `vitest.config.js`:
```javascript
// ✅ Funciona em Windows e Linux
include: ['./canonical/cell_types/**/tests/**/*.spec.ts']

// ❌ Quebra no Windows
include: [path.resolve(__dirname, './canonical/cell_types/**/tests/**/*.spec.ts')]
```

### 6. Cells Frontend-Only Não Precisam de Mock

Se a cell type só importa de `@/types/BaseCell` (sem apiService, sem endpoints), **não precisa de `vi.mock` nenhum**:

```typescript
// CalculatorCell.spec.ts — zero mocks
import { CalculatorCell } from '../CalculatorCell'
// ✅ Funciona perfeitamente
```

Isso vale para: `calculator-cell`, `manual-capture-cell`, `fragment-editor-cell` (verificar imports).

### 7. Estratégia de Nomenclatura

| Extensão | Uso |
|----------|-----|
| `.test.ts` | Legado — pode ser stub ou real, mantido para compatibilidade |
| `.spec.ts` | Novo padrão — sempre import real, sempre sem describe.skip |

**Decision:** Ao remediar uma célula, crie `.spec.ts` novo. Deixe o `.test.ts` legado — ele eventualmente será obsoleto quando ninguém mais referenciar.

### 8. `vi.fn()` vs MockResolvedValue

```typescript
// ✅ Correto para apiService.fetch
vi.mocked(apiService.fetch).mockResolvedValue(mockResponse as any)

// ✅ Correto para global.fetch  
(global.fetch as any).mockResolvedValueOnce({ ok: true, json: async () => data })
```

**Diferença:** `apiService.fetch` wrapper não precisa de `ok`/`json` — ele retorna o Response diretamente. Já `global.fetch` precisa de `Response`-like object.

---

## Template para Novos Testes

### Template para Cells com Backend (apiService)

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

// ── Real imports ────────────────────────────────────────────────────────────
import apiService from '@/services/apiService.js'
import { XxxCell } from '../XxxCell'
import type { XxxInput } from '../XxxCell'

// ── Suite ───────────────────────────────────────────────────────────────────
describe('XxxCell', () => {
  let cell: XxxCell

  beforeAll(() => { cell = new XxxCell() })
  beforeEach(() => { vi.clearAllMocks() })

  describe('validate()', () => {
    it('should return empty array for valid input', () => { /* ... */ })
    it('should return errors for invalid input', () => { /* ... */ })
    it('should handle edge case X', () => { /* ... */ })
  })

  describe('execute()', () => {
    it('should execute successfully with valid input', async () => { /* ... */ })
    it('should return validation error for invalid input', async () => { /* ... */ })
    it('should handle backend errors gracefully', async () => { /* ... */ })
    it('should handle network exceptions', async () => { /* ... */ })
  })

  describe('describe()', () => {
    it('should return metadata with id, name, version', async () => { /* ... */ })
    it('should define inputs and outputs', async () => { /* ... */ })
  })

  describe('health_check()', () => {
    it('should return healthy when backend reachable', async () => { /* ... */ })
    it('should return degraded on backend error', async () => { /* ... */ })
    it('should return unavailable on exception', async () => { /* ... */ })
  })

  describe('getState() / setState()', () => {
    it('should return defaults before any state set', () => { /* ... */ })
    it('should restore full state from persisted data', () => { /* ... */ })
    it('should handle partial state with defaults', () => { /* ... */ })
  })

  describe('setup() / teardown()', () => {
    it('setup should resolve without error', async () => { /* ... */ })
    it('teardown should resolve without error', async () => { /* ... */ })
  })
})
```

### Template para Cells Frontend-Only (sem mocks)

```typescript
/**
 * @file XxxCell.spec.ts
 * @description Unit tests for XxxCell — pure frontend (no backend)
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { XxxCell } from '../XxxCell'

describe('XxxCell', () => {
  let cell: XxxCell

  beforeAll(() => { cell = new XxxCell() })

  // Mesma estrutura, mas sem mocks e sem vi.clearAllMocks()
  describe('validate()', () => { /* ... */ })
  describe('execute()', () => { /* ... */ })
  describe('describe()', () => { /* ... */ })
  describe('health_check()', () => { /* ... */ })
  describe('setup() / teardown()', () => { /* ... */ })
})
```

---

## 📊 Progresso Geral

```
📈 COBERTURA DE TESTES EM artifacts/

Test files:  10 total
  └─ Real import:   5 (MeshPrototyping, Calculator, ManualCapture, PlanetChat, Wikipedia)
  └─ Stub:          4 (Inbox, Messages, Requests, UserSelection)
  └─ Utilitário:    1 (resolveWsUrl)

Total tests: 208 (0 failures, 0 skipped)

Células com cobertura real:   5 / ~30 cell types
Células com stub:              4 / ~30 cell types
Células sem teste nenhum:     ~21 / ~30 cell types
```

---

## Arquivos Gerados

| Arquivo | Descrição |
|---------|-----------|
| `artifacts/vitest.config.js` | Config autossuficiente para testar cell types |
| `artifacts/tests/stubs/apiService.js` | Stub para `@/services/apiService.js` |
| `artifacts/tests/stubs/endpoints.js` | Stub para `@/config/endpoints.js` |
| `artifacts/docs/TESTING_ARTIFACTS.md` | Este documento |
| `.../MeshPrototypingCell.spec.ts` | Teste real com 49 testes (célula de referência) |
| `.../CalculatorCell.spec.ts` | Teste real — 29 testes, 93.67% stmts |
| `.../ManualCaptureCell.spec.ts` | Teste real — 21 testes (reescrito de stub) |
| `.../WikipediaSearchCell.test.ts` | Teste real — 12 testes (fixado: totalhits→totalHits) |

---

> 📎 **Documento original:** [docs/RESOLUTION_REPORT.md](../../docs/RESOLUTION_REPORT.md) — contém o relatório completo de diagnóstico e resolução do problema.
