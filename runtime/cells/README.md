---
processed: true
processed_date: 2025-12-09
themes:
  - architecture
  - artifacts
  - backend
  - data-models
modules:
  - backend
  - architecture
code_verified: true
dead_docs_found: false
---
# Células Runtime - NotebookItem Instanciados

## 📋 Visão Geral

**Células Runtime** são instâncias de **NotebookItem** criadas a partir de **NotebookItemType** (tipos canônicos). Cada célula pertence a um usuário específico (assignee) e pode fazer parte de um livro. As células herdam configurações e workflows de seus tipos, mas podem sobrescrevê-los quando permitido.

### 🔄 Nova Arquitetura: NotebookItem/NotebookItemType

O sistema foi refatorado para usar uma arquitetura tipo-driven baseada em:
- **NotebookItem**: Classe base para células (Celula) e livros (Livro)
- **NotebookItemType**: Blueprint que define comportamento, workflows e dados padrão
- **PipelineItem**: Contexto de execução que referencia NotebookItem via `notebook_item_id`

> **📚 Documentação Completa**: [docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)

> **🆕 Evolução para Sandbox Cells**: Este documento descreve a implementação atual. Para o sistema estendido com runtime dinâmico, controle de lifecycle e metadados avançados, consulte:
> - [Análise de Gaps: Células Sandbox](../../../docs/project/SANDBOX_CELLS_GAP_ANALYSIS.md)
> - [Plano de Implementação](../../../docs/project/SANDBOX_CELLS_IMPLEMENTATION_PLAN.md)

## 🎯 Propósito

Células runtime são unidades atômicas de trabalho no ScareVerse. Criadas quando:
- Usuário expressa uma intenção via chat IA
- Usuário solicita criar célula via API
- Sistema decompõe tarefa complexa em células

### Relacionamento NotebookItemType

Cada célula (`Celula`) herda de `NotebookItem` e referencia um `NotebookItemType` via:
- **Campo Novo**: `notebook_item_type_id` (campo primário)
- **Campo Legacy**: `tipoCelulaId` (mantido para compatibilidade, sincronizado automaticamente)

O `NotebookItemType` define:
- **default_refs**: Workflows, docs, scripts padrão
- **default_initial_data**: Dados iniciais padrão
- **allow_instance_override_refs**: Se a instância pode sobrescrever refs

## 🗄️ Armazenamento

**Diretório Base**: `Artefatos/runtime/celulas`  
**Mecanismo**: **JSONDatabase** (cada célula é um arquivo JSON separado)  
**Isolamento**: Por `assignee_id` (usuário)

## ⚠️ Campos Legacy vs Novos

### Mapeamento de Compatibilidade Retroativa

| Campo Legacy | Campo Novo | Status | Observação |
|--------------|------------|--------|------------|
| `tipoCelulaId` | `notebook_item_type_id` | ✅ Sincronizado | Ambos funcionam, `notebook_item_type_id` tem prioridade |
| `responsavelId` | `assignee_id` | ✅ Sincronizado | Property `responsavelId` mapeia para `assignee_id` |
| `fragmentos` | `fragments` | ✅ Sincronizado | Property `fragmentos` mapeia para `fragments` |
| `dataCriacao` | `created_at` | ✅ Sincronizado | Property `dataCriacao` mapeia para `created_at` |
| `dataAtualizacao` | `updated_at` | ✅ Sincronizado | Property `dataAtualizacao` mapeia para `updated_at` |
| `data` | `initial_data` | ✅ Sincronizado | Property `data` mapeia para `initial_data` |
| *(não existia)* | `refs` | 🆕 Novo | Override de refs por instância (Dict[str, List[str]]) |

> **📌 IMPORTANTE**: Todos os campos legacy continuam funcionando! O backend sincroniza automaticamente através de validators e properties. APIs antigas não quebram.

## 📝 Schema

Ver [SCHEMA.md](./SCHEMA.md) para documentação completa.

### Estrutura Básica (Nova Arquitetura)

```json
{
  "id": "uuid-celula",
  "assignee_id": "uuid-usuario",
  "notebook_item_type_id": "uuid-tipo-canonico",
  "tipoCelulaId": "uuid-tipo-canonico",
  "origemLivroId": "uuid-livro-origem",
  "initial_data": {
    "title": "Título da Célula",
    "content": "Conteúdo da célula",
    "fileName": "nome_arquivo.md"
  },
  "refs": {
    "workflow_graph": ["app.workflows.custom_workflow"],
    "docs": ["path/to/custom_doc.md"]
  },
  "fragments": [
    {
      "tipo": "memoria",
      "conteudo": {
        "anotacao": "Anotações do usuário"
      },
      "timestamp": "2024-11-02T23:00:00.000000"
    },
    {
      "tipo": "execucao",
      "conteudo": {
        "resultado": "Resultado da execução"
      },
      "timestamp": "2024-11-02T23:00:00.000000"
    }
  ],
  "estado": "finalizado",
  "created_at": "2024-11-02T23:00:00Z",
  "updated_at": "2024-11-02T23:30:00Z"
}
```

> **⚠️ CAMPOS LEGACY**: Os campos `tipoCelulaId`, `responsavelId`, `data`, `fragmentos`, `dataCriacao`, `dataAtualizacao` ainda funcionam por compatibilidade retroativa, mas são automaticamente sincronizados com os campos novos.

## 🔄 Estados da Célula

Uma célula pode estar em um dos seguintes estados:

| Estado | Descrição | Transições Possíveis |
|--------|-----------|---------------------|
| `pendente` | Criada mas não executada | → `executando`, `erro` |
| `executando` | Em processo de execução | → `finalizado`, `erro` |
| `finalizado` | Execução completa | → `executando` (re-execução) |
| `erro` | Falha na execução | → `executando` (retry) |

### Diagrama de Estados

```
    [pendente]
        ↓
   [executando]
     ↙     ↘
[finalizado] [erro]
     ↓         ↓
     └─────────┘
          ↓
    [executando] (retry)
```

## 🔧 Fragmentos

Células contêm **fragmentos** que registram memória e resultados de execução.

### Estrutura do Fragmento

```json
{
  "tipo": "memoria",
  "conteudo": { /* Dicionário de dados específicos do fragmento */ },
  "timestamp": "2024-11-02T23:00:00.000000"
}
```

### Tipos de Fragmentos

#### 1. Memória
```json
{
  "tipo": "memoria",
  "conteudo": {
    "anotacoes": "Anotações, contexto, observações do usuário",
    "decisao": "Decisão tomada pela IA"
  },
  "timestamp": "2024-11-02T23:00:00.000000"
}
```

**Uso**: Armazenar contexto, anotações, decisões, etc.

#### 2. Execução
```json
{
  "tipo": "execucao",
  "conteudo": {
    "output": "Resultado da execução",
    "logs": ["log1", "log2"],
    "erro": null
  },
  "timestamp": "2024-11-02T23:00:00.000000"
}
```

**Uso**: Armazenar resultados de execuções, logs, erros.

## 🔄 Ciclo de Vida

### 1. Criação (Nova Arquitetura)

```http
POST /api/mvp/celulas/criar
Authorization: Bearer {token}

{
  "notebook_item_type_id": "45666a57-b1a2-486c-91ac-c8ea2ab5649b",
  "assignee_id": "uuid-usuario",
  "dadosIniciais": {
    "title": "Título da Célula",
    "content": "Conteúdo inicial da célula"
  },
  "refs": {
    "workflow_graph": ["app.workflows.custom_workflow"]
  }
}
```

> **⚠️ COMPATIBILIDADE**: O campo `tipoCelulaId` ainda funciona e é automaticamente sincronizado com `notebook_item_type_id`.

**Response**:
```json
{
  "id": "novo-uuid-celula",
  "assignee_id": "uuid-usuario",
  "notebook_item_type_id": "45666a57-b1a2-486c-91ac-c8ea2ab5649b",
  "tipoCelulaId": "45666a57-b1a2-486c-91ac-c8ea2ab5649b",
  "initial_data": {
    "title": "Título da Célula",
    "content": "Conteúdo inicial da célula"
  },
  "refs": {
    "workflow_graph": ["app.workflows.custom_workflow"]
  },
  "estado": "pendente",
  "fragments": [],
  "created_at": "2024-11-02T23:00:00Z",
  "updated_at": "2024-11-02T23:00:00Z"
}
```

### 2. Leitura

```http
GET /api/mvp/celulas/{id}
Authorization: Bearer {token}
```

**Response**: Objeto Celula completo, incluindo `initial_data`, `refs` e `fragments` (campos legacy `data` e `fragmentos` também retornados por compatibilidade).

### 3. Execução (Nova Arquitetura com PipelineItem)

```http
POST /api/mvp/celulas/{id}/executar
Authorization: Bearer {token}

{
  "parametros": {
    "input": "dados de entrada para a execução"
  }
}
```

**Processo de Execução**:
1.  Frontend/Agente solicita execução da célula
2.  Backend carrega `Celula` (NotebookItem) e `NotebookItemType`
3.  Backend cria `PipelineItem`:
    ```python
    pipeline_item = PipelineItem(
        notebook_item_id=celula.id,
        assignee_id=celula.assignee_id,
        status="running"
    )
    ```
4.  Backend resolve workflow path com prioridade:
    - Se `NotebookItemType.allow_instance_override_refs == True`:
      - Usa `Celula.refs["workflow_graph"]` se presente
      - Senão, usa `NotebookItemType.default_refs["workflow_graph"]`
    - Se `allow_instance_override_refs == False`:
      - Sempre usa `NotebookItemType.default_refs["workflow_graph"]`
5.  Workflow é carregado dinamicamente:
    ```python
    workflow_module = importlib.import_module(workflow_path)
    result = workflow_module.execute_workflow(pipeline_item, celula)
    ```
6.  Estado atualizado: `pendente` → `executando` → `finalizado` ou `erro`
7.  Resultados salvos em `Celula.fragments`

> **📚 Documentação Completa**: Ver [NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md#workflow-resolution-logic) para detalhes de resolução de workflows e execução dinâmica.

### 4. Atualização

```http
PUT /api/mvp/celulas/{id}/atualizar
Authorization: Bearer {token}

{
  "estado": "finalizado",
  "initial_data": {
    "title": "Título Atualizado",
    "content": "Conteúdo da célula após edição"
  },
  "fragments": [
    {
      "tipo": "memoria",
      "conteudo": {
        "anotacao": "Nova anotação ou atualização de contexto"
      },
      "timestamp": "2024-11-02T23:45:00.000000"
    }
  ]
}
```

> **⚠️ COMPATIBILIDADE**: Os campos `data` e `fragmentos` continuam funcionando e são sincronizados automaticamente.

**Response**: Objeto Celula atualizado.

### 5. Exclusão

```http
DELETE /api/mvp/celulas/{id}/deletar
Authorization: Bearer {token}
```

**Response**: Mensagem de sucesso ou erro.

## 🔗 Relacionamentos (Nova Arquitetura)

-   **`Celula` (NotebookItem) ↔ `NotebookItemType`**: Uma instância de `Celula` é sempre baseada em um `NotebookItemType` via `notebook_item_type_id`. O tipo define `default_refs`, `default_initial_data` e políticas de override. O campo legacy `tipoCelulaId` é mantido sincronizado automaticamente.

-   **`PipelineItem` ↔ `Celula` (NotebookItem)**: Durante execução, um `PipelineItem` é criado referenciando a `Celula` via `notebook_item_id`. O `PipelineItem` mantém o contexto de execução (status, erro, agent_data) separado dos dados da célula.

-   **`Celula` ↔ `Livro`**: Uma `Celula` pode ter um `origemLivroId` referenciando o livro ao qual pertence. Livros também são `NotebookItem` e podem ter `NotebookItemType`.

-   **`Celula` ↔ `Usuário/Agente`**: `assignee_id` vincula a célula ao seu criador/proprietário (property legacy `responsavelId` também funciona).

-   **`Celula` ↔ Workflows**: Workflows são referenciados via `refs["workflow_graph"]` (instância) ou `NotebookItemType.default_refs["workflow_graph"]` (tipo), carregados dinamicamente em runtime.

## 🎮 Uso no Jogo

### Criação via Intenção da IA (Nova Arquitetura)

Quando a IA gera uma célula com base em uma intenção do usuário:

```json
{
  "resposta": "Criei uma célula de geração de código para você. Por favor, especifique os requisitos.",
  "celula": {
    "id": "uuid-nova-celula-gerada-ia",
    "assignee_id": "uuid-usuario-solicitante",
    "notebook_item_type_id": "1cbb5e6f-1570-4462-99c6-287c37b201b6",
    "tipoCelulaId": "1cbb5e6f-1570-4462-99c6-287c37b201b6",
    "initial_data": {
      "specification": "Listar todos os arquivos .md no diretório 'docs'",
      "generatedCode": ""
    },
    "refs": {
      "workflow_graph": ["app.workflows.code_generation"]
    },
    "estado": "pendente",
    "created_at": "2024-11-02T23:50:00Z",
    "updated_at": "2024-11-02T23:50:00Z"
  }
}
```

> **📌 NOTA**: A IA pode criar células especificando `notebook_item_type_id` (novo) ou `tipoCelulaId` (legacy). O backend sincroniza automaticamente.

### Orquestração de Gameplay

Células podem ser encadeadas em workflows definidos em `NotebookItemType.default_refs["workflow_graph"]` ou orquestradas por agentes. Durante execução, `PipelineItem` mantém o contexto separado da célula.

### Exemplo de Migração de Código Legacy para Nova Arquitetura

**Antes (Legacy)**:
```python
# Criar célula com tipoCelulaId
celula = Celula(
    tipoCelulaId="old-type-id",
    responsavelId="user-123",
    data={"title": "Minha Célula"}
)
```

**Depois (Nova Arquitetura)**:
```python
# Criar célula com NotebookItemType
celula = Celula(
    notebook_item_type_id="new-type-id",
    assignee_id="user-123",
    initial_data={"title": "Minha Célula"},
    refs={
        "workflow_graph": ["app.workflows.custom"]
    }
)
```

**Compatibilidade Total** (Ambos funcionam):
```python
# Código legacy ainda funciona! Backend sincroniza automaticamente
celula = Celula(
    tipoCelulaId="type-id",  # Sincronizado com notebook_item_type_id
    responsavelId="user-123",  # Sincronizado com assignee_id
    data={"title": "Célula"}  # Sincronizado com initial_data
)
# Resultado: celula.notebook_item_type_id == "type-id"
# Resultado: celula.assignee_id == "user-123"
# Resultado: celula.initial_data == {"title": "Célula"}
```

---

## 📚 Documentação Relacionada

### Arquitetura
- **[NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)** - Arquitetura completa NotebookItem/NotebookItemType/PipelineItem
- **[SCHEMA.md](./SCHEMA.md)** - Schema detalhado de Celula com campos novos e legacy
- **[Tipos de Célula](../../canonicos/tipos_celula/README.md)** - Documentação de NotebookItemType canônicos

### Modelos e Implementação
- **[backend/app/models/content.py](../../../backend/app/models/content.py)** - Implementação Pydantic de Celula, NotebookItemType e Livro
- **[backend/app/core/models.py](../../../backend/app/core/models.py)** - Classes base NotebookItem e PipelineItem
- **[backend/app/models/adapters.py](../../../backend/app/models/adapters.py)** - Adapters para execução dinâmica de workflows

### Testes
- **[tests/unit/backend/test_notebook_item_type.py](../../../tests/unit/backend/test_notebook_item_type.py)** - Testes unitários da arquitetura
- **[tests/unit/backend/test_adapter_dynamic_loading.py](../../../tests/unit/backend/test_adapter_dynamic_loading.py)** - Testes de carregamento dinâmico de workflows

### Guias
- **[GAP_RESOLUTION_GUIDE.md](../../../docs/GAP_RESOLUTION_GUIDE.md)** - Guia de resolução de gaps de documentação
- **[ARQUITETURA_TESTES.md](../../../docs/ARQUITETURA_TESTES.md)** - Arquitetura e padrões de testes

**`Total de Células Runtime`**: (Pode ser atualizado dinamicamente pelo sistema, ex: `7` ou mais)

**`Storage`**: Disco (`JSONDatabase` em `Artefatos/runtime/celulas`)  
**`Last Update`**: 2024-11-17 (Atualizado para arquitetura NotebookItem/NotebookItemType/PipelineItem)
