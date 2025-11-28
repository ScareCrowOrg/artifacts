# Tipos de Célula - NotebookItemType Canônicos

## 📋 Visão Geral

**Tipos de Célula** são blueprints canônicos implementados como **NotebookItemType** que definem a estrutura, comportamento e workflows de células instanciadas. A nova arquitetura usa tipo-driven behavior onde células herdam configurações de seus tipos.

### 🔄 Nova Arquitetura: NotebookItemType

Os tipos de célula agora são implementados como `NotebookItemType`, fornecendo:
- **default_refs**: Workflows, docs, scripts padrão (Dict[str, List[str]])
- **default_initial_data**: Dados iniciais padrão para novas instâncias
- **allow_instance_override_refs**: Política de override (bool)

> **📚 Documentação Completa**: [NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)

## ⚠️ Migração: TipoCelula → NotebookItemType

### Campos Legacy vs Novos

| Campo Legacy (TipoCelula) | Campo Novo (NotebookItemType) | Tipo | Observação |
|---------------------------|-------------------------------|------|------------|
| `name` | `name` | string | ✅ Mantido (mesmo nome) |
| `descricao` | `description` | string | 🔄 Renomeado |
| `docs_refs` | `default_refs["docs"]` | List[str] | 🔄 Agrupado em default_refs |
| `python_refs` | `default_refs["python"]` | List[str] | 🔄 Agrupado em default_refs |
| `javascript_refs` | `default_refs["javascript"]` | List[str] | 🔄 Agrupado em default_refs |
| `yaml_refs` | `default_refs["yaml"]` | List[str] | 🔄 Agrupado em default_refs |
| `views_components` | `default_refs["views_components"]` | List[str] | 🔄 Agrupado em default_refs |
| `workflows` | `default_refs["workflow_graph"]` | List[str] | 🔄 Agrupado em default_refs |
| `properties` | `default_initial_data` (schema) | Dict | 🔄 Reestruturado |
| *(não existia)* | `allow_instance_override_refs` | bool | 🆕 Novo |

> **📌 COMPATIBILIDADE**: Durante a migração, o backend suporta ambos os formatos. Tipos antigos (`TipoCelula`) são convertidos automaticamente para `NotebookItemType` via script de migração.

## 🎯 Propósito

NotebookItemType serve como **blueprint type-driven** para criar células runtime (Celula). Define:

-   **Metadados UI**: `name`, `description` para exibição na interface
-   **Referências Padrão (`default_refs`)**: Workflows, docs, scripts, componentes que células deste tipo usarão por padrão
    ```json
    {
      "workflow_graph": ["app.workflows.ingestion_graph"],
      "docs": ["docs/ingestion.md"],
      "python": ["scripts/process.py"],
      "views_components": ["CellView_Ingestion"]
    }
    ```
-   **Dados Iniciais Padrão (`default_initial_data`)**: Dados que novas instâncias receberão automaticamente
    ```json
    {
      "processing_mode": "batch",
      "chunk_size": 512
    }
    ```
-   **Política de Override (`allow_instance_override_refs`)**: Se células podem sobrescrever refs do tipo
    - `True`: Célula pode ter `refs` próprio que sobrescreve `default_refs`
    - `False`: Célula sempre usa `default_refs` do tipo, ignora `refs` da instância

## 📁 Estrutura

```
tipos_celula/
├── README.md                          # Este arquivo
├── SCHEMA.md                          # Schema detalhado
├── unclassified.json                  # Exemplo: Célula Não Classificada
├── file_editor.json                   # Exemplo: Editor de Arquivo
└── {uuid}.json                        # Outros arquivos de tipos
```

## 📊 Tipos Implementados (NotebookItemType)

Atualmente existem **7 tipos de célula** implementados como `NotebookItemType`:

1.  **Ingestion Cell** (`ingestion-cell-type`)
    *   Processa e ingere documentos no sistema
    *   default_refs: `{"workflow_graph": ["app.workflows.ingestion_graph"]}`
    *   allow_instance_override_refs: `True`

2.  **Code Generator Cell** (`code-generator-type`)
    *   Gera código a partir de especificações
    *   default_refs: `{"workflow_graph": ["app.workflows.code_generation"]}`
    *   allow_instance_override_refs: `True`

3.  **Artifact Editor Cell** (`artifact-editor-type`)
    *   Edita artefatos existentes
    *   default_refs: `{"views_components": ["CellView_ArtifactEditor"]}`
    *   allow_instance_override_refs: `True`

4.  **Conversation Memory Cell** (`conversation-memory-type`)
    *   Armazena contexto de conversação
    *   default_refs: `{"docs": ["docs/conversation_memory.md"]}`
    *   allow_instance_override_refs: `False`

5.  **Test Executor Cell** (`test-executor-type`)
    *   Executa testes automatizados
    *   default_refs: `{"workflow_graph": ["app.workflows.test_execution"], "python": ["scripts/run_tests.py"]}`
    *   allow_instance_override_refs: `True`

6.  **Validator Cell** (`validator-cell-type`)
    *   Valida integridade de artefatos
    *   default_refs: `{"workflow_graph": ["app.workflows.validation"]}`
    *   allow_instance_override_refs: `False`

7.  **Unclassified Cell** (`unclassified-type`)
    *   Tipo genérico para células não classificadas
    *   default_refs: `{"views_components": ["CellView_Unclassified"]}`
    *   allow_instance_override_refs: `True`

> **📌 NOTA**: IDs acima são exemplos. IDs reais são UUIDs, exceto tipos especiais como "unclassified" que tem ID fixo.

## 📝 Exemplo de NotebookItemType

**Nome**: Ingestion Cell Type  
**Arquivo**: `ingestion-cell-type.json` (canônico, versionado em Git)

```json
{
  "id": "ingestion-cell-type-uuid",
  "name": "Ingestion Cell",
  "description": "Processa e ingere documentos no sistema, com chunking e embedding automático.",
  "default_refs": {
    "workflow_graph": ["app.workflows.ingestion_graph"],
    "docs": ["docs/ingestion.md", "docs/chunking_strategies.md"],
    "python": ["app/workflows/preprocess_and_chunk.py"],
    "views_components": ["CellView_IngestionInput", "CellView_IngestionProgress"]
  },
  "default_initial_data": {
    "processing_mode": "batch",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "embedding_model": "text-embedding-ada-002"
  },
  "allow_instance_override_refs": true,
  "created_at": "2024-11-17T10:00:00Z",
  "updated_at": "2024-11-17T10:00:00Z"
}
```

### Como Células Usam Este Tipo

```python
# Criar célula baseada neste tipo
celula = Celula(
    notebook_item_type_id="ingestion-cell-type-uuid",
    assignee_id="user-123",
    initial_data={
        # Herda default_initial_data do tipo, mas pode sobrescrever:
        "processing_mode": "streaming",  # Override
        "chunk_size": 1024,  # Override
        "file_path": "/docs/document.pdf"  # Adicional
    },
    refs={
        # Pode sobrescrever refs porque allow_instance_override_refs=True
        "workflow_graph": ["app.workflows.custom_ingestion"]
    }
)

# Durante execução:
# 1. Backend carrega NotebookItemType
# 2. Resolve workflow: usa celula.refs["workflow_graph"] (override permitido)
# 3. Carrega app.workflows.custom_ingestion dinamicamente
# 4. Executa passando PipelineItem e Celula
```

## 🔄 Fluxo de Uso (Nova Arquitetura)

```
1. Usuário solicita criar célula
        ↓
2. Frontend/Backend seleciona NotebookItemType apropriado
        ↓
3. NotebookItemType é carregado (JSON canônico) com default_refs e default_initial_data
        ↓
4. Nova Celula (NotebookItem) é instanciada:
   - initial_data = merge(tipo.default_initial_data, dados do usuário)
   - refs = dados do usuário (se allow_instance_override_refs=True)
        ↓
5. Celula salva em JSONDatabase
        ↓
6. Em execução:
   - PipelineItem criado referenciando Celula.id
   - Workflow resolvido (refs ou default_refs conforme política)
   - Workflow carregado dinamicamente via importlib
   - Workflow executa com PipelineItem e Celula
```

> **📚 Detalhes**: Ver [NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md - Workflow Resolution Logic](../../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md#workflow-resolution-logic)

## 🔧 Campos do NotebookItemType Schema

Ver [SCHEMA.md](./SCHEMA.md) para documentação completa.

### Campos Principais

#### `id` (string, UUID)
Identificador único do tipo. Referenciado por `Celula.notebook_item_type_id`.

#### `name` (string)
Nome curto e legível para exibição na UI.

#### `description` (string)
Descrição detalhada do propósito e funcionalidade do tipo.

#### `default_refs` (Dict[str, List[str]])
Referências padrão que células deste tipo herdam:
- `workflow_graph`: Workflows de execução
- `docs`: Documentação
- `python`: Scripts Python
- `javascript`: Scripts JavaScript
- `yaml`: Configurações YAML
- `views_components`: Componentes Vue da UI

#### `default_initial_data` (Dict[str, Any])
Dados iniciais padrão que novas células recebem automaticamente.

#### `allow_instance_override_refs` (bool)
Define se células podem sobrescrever `default_refs` com seus próprios `refs`.

#### `created_at` / `updated_at` (datetime)
Timestamps de criação e atualização.

## 📚 Schema Completo

Ver [SCHEMA.md](./SCHEMA.md) para documentação detalhada com todos os campos, tipos, validações e exemplos completos do schema `NotebookItemType`.

## 🔄 Migração: TipoCelula → NotebookItemType

### Script de Migração

O sistema inclui um script de migração automática:

```bash
cd backend
python scripts/migrate_notebook_item_types.py
```

Este script:
- ✅ Converte tipos antigos (`TipoCelula`) para `NotebookItemType`
- ✅ Mapeia campos legacy para nova estrutura:
  - `docs_refs` → `default_refs["docs"]`
  - `python_refs` → `default_refs["python"]`
  - `workflows` → `default_refs["workflow_graph"]`
- ✅ Define `allow_instance_override_refs=True` por padrão
- ✅ Preserva IDs existentes (sem duplicatas)
- ✅ É **idempotente** (pode rodar múltiplas vezes sem problemas)

### Exemplo de Migração

**Antes (TipoCelula)**:
```json
{
  "id": "code-gen-uuid",
  "name": "Gerador de Código",
  "descricao": "Gera código",
  "category": "persistida",
  "docs_refs": ["docs/code_gen.md"],
  "python_refs": ["scripts/generate.py"],
  "workflows": "workflow YAML string",
  "versao": "1.0.0"
}
```

**Depois (NotebookItemType)**:
```json
{
  "id": "code-gen-uuid",
  "name": "Gerador de Código",
  "description": "Gera código",
  "default_refs": {
    "docs": ["docs/code_gen.md"],
    "python": ["scripts/generate.py"],
    "workflow_graph": ["app.workflows.code_generation"]
  },
  "default_initial_data": {},
  "allow_instance_override_refs": true,
  "created_at": "2024-11-17T10:00:00Z",
  "updated_at": "2024-11-17T10:00:00Z"
}
```

## 🆕 Criando Novo NotebookItemType

### 1. Definir Estrutura JSON

```json
{
  "id": "novo-tipo-uuid",
  "name": "Novo Tipo de Célula",
  "description": "Descrição detalhada do novo tipo e seu propósito.",
  "default_refs": {
    "workflow_graph": ["app.workflows.novo_tipo"],
    "docs": ["docs/novo_tipo_guia.md"],
    "python": ["scripts/novo_tipo_handler.py"],
    "views_components": ["CellView_NovoTipo"]
  },
  "default_initial_data": {
    "campo_padrao": "valor",
    "outra_config": 123
  },
  "allow_instance_override_refs": true,
  "created_at": "2024-11-17T10:00:00Z",
  "updated_at": "2024-11-17T10:00:00Z"
}
```

### 2. Registrar no Sistema

```python
# backend/app/seed_data.py ou similar
from backend.app.models.content import NotebookItemType

novo_tipo = NotebookItemType(
    id="novo-tipo-uuid",
    name="Novo Tipo de Célula",
    description="Descrição detalhada",
    default_refs={
        "workflow_graph": ["app.workflows.novo_tipo"],
        "docs": ["docs/novo_tipo_guia.md"]
    },
    default_initial_data={"campo_padrao": "valor"},
    allow_instance_override_refs=True
)

# Salvar em JSONDatabase ou collection apropriada
db.insert("notebook_item_types", novo_tipo, is_canonical=True)
```

## 🔍 Consultando NotebookItemType

### Via API
```http
# Listar todos os tipos (NotebookItemType)
GET /api/notebook-item-types

# Obter tipo específico
GET /api/notebook-item-types/{id}

# APIs legacy ainda funcionam:
GET /api/tipos-celula  # Retorna NotebookItemType
```

### Via Sistema de Arquivos
```bash
# Listar todos os tipos canônicos
ls -1 Artefatos/canonicos/tipos_celula/*.json

# Ver conteúdo de um tipo
cat Artefatos/canonicos/tipos_celula/{uuid}.json | jq

# Buscar tipos por nome/descrição
jq '.name, .description' Artefatos/canonicos/tipos_celula/*.json | grep -i "ingestion"
```

## 📊 Estatísticas

```bash
# Contar tipos
ls Artefatos/canonicos/tipos_celula/*.json | wc -l

# Verificar tipos com override habilitado
jq -r 'select(.allow_instance_override_refs == true) | .name' Artefatos/canonicos/tipos_celula/*.json

# Listar workflows disponíveis
jq -r '.default_refs.workflow_graph[]?' Artefatos/canonicos/tipos_celula/*.json | sort | uniq
```

## 🔗 Integração com Backend

### Model Pydantic (NotebookItemType)
```python
# backend/app/models/content.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class NotebookItemType(BaseModel):
    id: str = Field(..., description="UUID do notebook item type")
    name: str = Field(..., description="Nome do tipo")
    description: Optional[str] = Field(None, description="Descrição do tipo")
    default_refs: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Referências padrão (workflow_graph, docs, python, etc.)"
    )
    default_initial_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dados iniciais padrão para instâncias"
    )
    allow_instance_override_refs: bool = Field(
        True,
        description="Se instâncias podem sobrescrever default_refs"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Uso em Células Runtime
```python
# Ao criar célula com NotebookItemType
celula = Celula(
    notebook_item_type_id="ingestion-cell-type-uuid",
    assignee_id="user-123",
    initial_data={
        # Herda e pode sobrescrever default_initial_data do tipo
        "processing_mode": "streaming",
        "chunk_size": 1024
    },
    refs={
        # Override de workflow (se allow_instance_override_refs=True)
        "workflow_graph": ["app.workflows.custom_ingestion"]
    }
)

# Durante execução, backend:
# 1. Carrega NotebookItemType
# 2. Resolve workflow baseado em política de override
# 3. Executa com PipelineItem + Celula
```

## 📚 Documentação Relacionada

- **[SCHEMA.md](./SCHEMA.md)** - Schema detalhado de NotebookItemType
- **[NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)** - Arquitetura completa
- **[Células Runtime](../../runtime/celulas/README.md)** - Documentação de instâncias
- **[backend/app/models/content.py](../../../backend/app/models/content.py)** - Implementação Pydantic
- **[backend/scripts/migrate_notebook_item_types.py](../../../backend/scripts/migrate_notebook_item_types.py)** - Script de migração

---

**Última Atualização**: 2024-11-17 (Atualizado para arquitetura NotebookItemType)  
**Total de Tipos**: 7  
**Sistema**: NotebookItem/NotebookItemType/PipelineItem
