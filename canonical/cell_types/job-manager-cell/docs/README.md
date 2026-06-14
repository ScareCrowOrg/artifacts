# JobManagerCell

Célula efêmera reutilizável para exibir status de jobs assíncronos.

## Modos de Operação

### Embedded (Embutido)
Polling de um job único. Exibe barra de progresso + status. Ideal para embutir dentro de outras células (ex: PNG Generator).

**Parâmetros:**
| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `embedded` | `boolean` | `false` | Ativa modo embutido |
| `job_id` | `string` | `null` | Job ID para monitorar |
| `poll_interval_ms` | `integer` | `2000` | Intervalo de polling em ms |

**Eventos:**
| Evento | Payload | Descrição |
|--------|---------|-----------|
| `complete` | `JobRecord` | Job completou com sucesso |
| `error` | `string` | Job falhou |

### Standalone (Listagem)
Tabela de jobs do usuário com filtros. Funciona como célula independente na Workspace.

**Parâmetros:**
| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `status` | `string` | — | Filtro: `queued`, `processing`, `success`, `failed` |
| `job_type` | `string` | — | Filtro por tipo de job |
| `max_items` | `integer` | `10` | Máximo de items (max 100) |

## Endpoints Consumidos

- `GET /api/cells/job-status/{job_id}` — Status de job individual
- `GET /api/cells/jobs` — Listagem de jobs do usuário

Nenhum endpoint novo é criado — a célula usa endpoints de sistema existentes.

## Exemplo de Uso

```typescript
// Embutir JobManagerCell para monitorar um job
await cellFactory.addChildCell('job-manager-cell', {
  job_id: 'uuid-do-job',
  embedded: true,
  poll_interval_ms: 2000,
})
```
