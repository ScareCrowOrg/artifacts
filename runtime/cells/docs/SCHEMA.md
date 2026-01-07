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
# Schema: Celula (Célula Runtime - NotebookItem)

## 📋 Visão Geral

Este documento define o schema completo para **Células Runtime** - instâncias concretas de `NotebookItem` baseadas em `NotebookItemType`. Reflete a nova arquitetura com:
- **Campos Novos**: `notebook_item_type_id`, `assignee_id`, `initial_data`, `refs`, `fragments`, `created_at`, `updated_at`
- **Campos Legacy**: `tipoCelulaId`, `responsavelId`, `data`, `fragmentos`, `dataCriacao`, `dataAtualizacao` (sincronizados automaticamente)
- **Persistência**: Via `JSONDatabase`
- **Execução**: Via `PipelineItem`

> **📚 Arquitetura Completa**: [NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)

## 🔧 Schema Pydantic (Nova Arquitetura)

```python
# backend/app/models/content.py
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from backend.app.core.models import NotebookItem
from backend.app.models.base import EstadoCelula

class Celula(NotebookItem):
    """
    Modelo de célula instanciada (herda de NotebookItem).
    
    Herda campos base do NotebookItem:
    - id: str (UUID único)
    - assignee_id: str (UUID do responsável/usuário)
    - fragments: List[Union[str, Dict[str, Any]]] (flexível: strings OU dicts estruturados)
    - refs: Dict[str, List[str]] (override de refs por instância, ex: {"workflow_graph": ["app.workflows.custom"]})
    - initial_data: Dict[str, Any] (dados específicos da instância, ex: {"title": "Célula X", "content": "..."})
    - created_at: datetime (timestamp UTC de criação)
    - updated_at: datetime (timestamp UTC de última atualização)
    
    Campos específicos de Celula:
    - notebook_item_type_id: str (ID do NotebookItemType - campo primário)
    - tipoCelulaId: Optional[str] (compatibilidade retroativa, sincronizado com notebook_item_type_id)
    - origemLivroId: Optional[str] (ID do livro origem, se aplicável)
    - estado: EstadoCelula (enum: PENDENTE, EXECUTANDO, FINALIZADO, ERRO)
    - versao: str (versão semântica, ex: "1.0.0")
    
    Compatibilidade Retroativa (Properties Read-Only):
    - tipoCelulaId ↔ notebook_item_type_id (sincronizados bidirecionalmente)
    - responsavelId → assignee_id (property)
    - data → initial_data (property)
    - fragmentos → fragments (property)
    - dataCriacao → created_at (property)
    - dataAtualizacao → updated_at (property)
    """
    # Campos específicos de Celula
    notebook_item_type_id: str = Field(..., description="ID do NotebookItemType (campo primário)")
    tipoCelulaId: Optional[str] = Field(None, description="UUID do tipo (legacy, sincronizado com notebook_item_type_id)")
    origemLivroId: Optional[str] = Field(None, description="UUID do livro de origem")
    estado: EstadoCelula = Field(default=EstadoCelula.PENDENTE, description="Estado da célula")
    versao: str = Field(default="1.0.0", description="Versão da célula")
    
    # Properties para compatibilidade retroativa (read-only)
    @property
    def responsavelId(self) -> str:
        """Legacy field mapping to assignee_id."""
        return self.assignee_id
    
    @property
    def fragmentos(self) -> List[Union[str, Dict[str, Any]]]:
        """Legacy field mapping to fragments."""
        return self.fragments
    
    @property
    def dataCriacao(self) -> datetime:
        """Legacy field mapping to created_at."""
        return self.created_at
    
    @property
    def dataAtualizacao(self) -> datetime:
        """Legacy field mapping to updated_at."""
        return self.updated_at
    
    @property
    def data(self) -> Dict[str, Any]:
        """Legacy field mapping to initial_data."""
        return self.initial_data
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        populate_by_name = True
```

## ⚠️ Tabela de Mapeamento: Legacy → Novo

| Campo Legacy | Campo Novo | Tipo | Sincronização | Observação |
|--------------|------------|------|---------------|------------|
| `tipoCelulaId` | `notebook_item_type_id` | string (UUID) | ✅ Bidirecional | Ambos funcionam, `notebook_item_type_id` tem prioridade. Sincronizado via `@model_validator` |
| `responsavelId` | `assignee_id` | string (UUID) | ✅ Property | Acesso via `@property`, armazenado em `assignee_id` |
| `data` | `initial_data` | Dict[str, Any] | ✅ Property | Acesso via `@property`, armazenado em `initial_data` |
| `fragmentos` | `fragments` | List[Union[str, Dict]] | ✅ Property | Acesso via `@property`, armazenado em `fragments`. Suporta strings simples OU dicts estruturados |
| `dataCriacao` | `created_at` | datetime | ✅ Property | Acesso via `@property`, armazenado em `created_at` |
| `dataAtualizacao` | `updated_at` | datetime | ✅ Property | Acesso via `@property`, armazenado em `updated_at` |
| *(não existia)* | `refs` | Dict[str, List[str]] | 🆕 Novo | Override de refs por instância. Permite sobrescrever workflows, docs, scripts definidos no tipo |

> **🔁 SINCRONIZAÇÃO AUTOMÁTICA**: O backend usa `@model_validator(mode='before')` para sincronizar campos legacy com novos durante desserialização. Código antigo continua funcionando sem alterações!

## 📝 Campos Detalhados

### 🆕 Campos Novos (Arquitetura NotebookItem)

#### `id` (string, obrigatório)
- **Tipo**: String UUID v4 lowercase
- **Obrigatório**: Sim
- **Único**: Sim
- **Geração**: Backend (`uuid.uuid4()` via `generate_uuid()`)
- **Exemplo**: `"a1b2c3d4-e5f6-7890-1234-567890abcdef"`
- **Descrição**: Identificador único da instância da célula. Usado para referência em `PipelineItem.notebook_item_id`.

#### `assignee_id` (string, obrigatório)
- **Tipo**: String UUID
- **Obrigatório**: Sim
- **Exemplo**: `"user-123"` ou `"agent-456"`
- **Descrição**: ID do responsável (usuário ou agente) pela criação/edição da célula. Usado para isolamento de dados.
- **Legacy Property**: `responsavelId` (read-only)

#### `notebook_item_type_id` (string, obrigatório)
- **Tipo**: String UUID
- **Obrigatório**: Sim
- **Exemplo**: `"45666a57-b1a2-486c-91ac-c8ea2ab5649b"`
- **Descrição**: ID do `NotebookItemType` canônico ao qual esta instância pertence. Define comportamento, workflows e dados padrão.
- **Legacy Sync**: Sincronizado bidirecionalmente com `tipoCelulaId`

#### `initial_data` (dicionário, obrigatório)
- **Tipo**: `Dict[str, Any]`
- **Obrigatório**: Sim (default: `{}`)
- **Exemplo**: `{"title": "Minha Célula", "content": "Conteúdo", "fileName": "arquivo.md"}`
- **Descrição**: Dados específicos da instância da célula. O schema de propriedades é definido por `NotebookItemType.properties`.
- **Legacy Property**: `data` (read-only)

#### `refs` (dicionário, opcional)
- **Tipo**: `Dict[str, List[str]]`
- **Obrigatório**: Não (default: `None`)
- **Exemplo**: `{"workflow_graph": ["app.workflows.custom"], "docs": ["path/to/doc.md"]}`
- **Descrição**: Override de referências por instância. Permite sobrescrever workflows, docs, scripts definidos em `NotebookItemType.default_refs`.
- **Comportamento**: 
  - Se `NotebookItemType.allow_instance_override_refs == True`: `refs` da instância sobrescreve `default_refs` do tipo
  - Se `False`: `refs` da instância é ignorado, sempre usa `default_refs`

#### `fragments` (array, obrigatório)
- **Tipo**: `List[Union[str, Dict[str, Any]]]`
- **Obrigatório**: Sim (default: `[]`)
- **Exemplo**: 
  ```json
  [
    "Anotação simples de memória",
    {
      "tipo": "execucao",
      "conteudo": {"output": "Resultado X"},
      "timestamp": "2024-11-17T10:00:00Z"
    }
  ]
  ```
- **Descrição**: Lista de fragmentos de memória, resultados de execução ou outras subdivisões. **Flexível**: aceita strings simples OU dicionários estruturados.
- **Legacy Property**: `fragmentos` (read-only)

#### `created_at` (datetime, obrigatório)
- **Tipo**: datetime (ISO 8601 UTC)
- **Obrigatório**: Sim
- **Geração**: Backend (`datetime.utcnow()`)
- **Exemplo**: `"2024-11-17T10:00:00.000000Z"`
- **Descrição**: Timestamp UTC da criação da célula.
- **Legacy Property**: `dataCriacao` (read-only)

#### `updated_at` (datetime, obrigatório)
- **Tipo**: datetime (ISO 8601 UTC)
- **Obrigatório**: Sim
- **Geração**: Backend (`datetime.utcnow()`)
- **Exemplo**: `"2024-11-17T10:30:00.000000Z"`
- **Descrição**: Timestamp UTC da última atualização da célula.
- **Legacy Property**: `dataAtualizacao` (read-only)

### 📦 Campos Específicos de Celula

#### `tipoCelulaId` (string, opcional - legacy)
- **Tipo**: String UUID
- **Obrigatório**: Não (sincronizado automaticamente)
- **Exemplo**: `"45666a57-b1a2-486c-91ac-c8ea2ab5649b"`
- **Descrição**: Campo legacy para compatibilidade retroativa. Sincronizado bidirecionalmente com `notebook_item_type_id`. Código antigo usando `tipoCelulaId` continua funcionando.
- **Sincronização**: Via `@model_validator` no backend

#### `origemLivroId` (string, opcional)
- **Tipo**: String UUID
- **Obrigatório**: Não
- **Exemplo**: `"book-789"`
- **Descrição**: ID do Livro (se aplicável) que originou ou contém esta célula. Permite organizar células em livros (notebooks).

#### `estado` (enum, obrigatório)
- **Tipo**: `EstadoCelula` (enum)
- **Obrigatório**: Sim (default: `PENDENTE`)
- **Valores**: `PENDENTE`, `EXECUTANDO`, `FINALIZADO`, `ERRO`
- **Exemplo**: `"FINALIZADO"`
- **Descrição**: Estado atual do ciclo de vida da célula. Atualizado durante execução via `PipelineItem`.

#### `versao` (string, obrigatório)
- **Tipo**: String (SemVer)
- **Obrigatório**: Sim (default: `"1.0.0"`)
- **Exemplo**: `"1.2.3"`
- **Descrição**: Versão semântica da célula. Útil para versionamento e controle de compatibilidade.

## 📊 Exemplo Completo: Celula JSON (Nova Arquitetura)

```json
{
  "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "assignee_id": "user-123",
  "notebook_item_type_id": "45666a57-b1a2-486c-91ac-c8ea2ab5649b",
  "tipoCelulaId": "45666a57-b1a2-486c-91ac-c8ea2ab5649b",
  "origemLivroId": "book-xyz",
  "initial_data": {
    "title": "Célula de Processamento de Dados",
    "content": "Processar documentos PDF",
    "fileName": "process_docs.py"
  },
  "refs": {
    "workflow_graph": ["app.workflows.custom_ingestion"],
    "docs": ["docs/ingestion_guide.md"]
  },
  "fragments": [
    "Criada para processamento batch",
    {
      "tipo": "memoria",
      "conteudo": {"contexto": "Início da sessão de processamento"},
      "timestamp": "2024-11-17T10:00:00.000000Z"
    },
    {
      "tipo": "execucao",
      "conteudo": {
        "output": "Processados 42 documentos com sucesso",
        "logs": ["INFO: Iniciando...", "INFO: Finalizado"]
      },
      "timestamp": "2024-11-17T10:05:30.000000Z"
    }
  ],
  "estado": "FINALIZADO",
  "versao": "1.0.0",
  "created_at": "2024-11-17T09:55:00.000000Z",
  "updated_at": "2024-11-17T10:06:00.000000Z"
}
```

## 🔄 Exemplo de Compatibilidade Retroativa

### Código Legacy (Ainda Funciona!)

```python
# Código antigo usando campos legacy
celula = Celula(
    tipoCelulaId="type-123",  # Legacy field
    responsavelId="user-456",  # Legacy field (via validator)
    data={"title": "Célula Legacy"},  # Legacy field (via validator)
    fragmentos=["nota 1", "nota 2"]  # Legacy field (via validator)
)

# Backend sincroniza automaticamente:
print(celula.notebook_item_type_id)  # "type-123"
print(celula.assignee_id)  # "user-456"
print(celula.initial_data)  # {"title": "Célula Legacy"}
print(celula.fragments)  # ["nota 1", "nota 2"]

# Properties também funcionam:
print(celula.responsavelId)  # "user-456" (property)
print(celula.data)  # {"title": "Célula Legacy"} (property)
```

### Código Novo (Recomendado)

```python
# Código novo usando campos da nova arquitetura
celula = Celula(
    notebook_item_type_id="type-123",
    assignee_id="user-456",
    initial_data={"title": "Célula Nova"},
    refs={"workflow_graph": ["app.workflows.custom"]},
    fragments=["nota 1", {"tipo": "memoria", "conteudo": {"x": 1}}]
)

# Campos legacy ainda acessíveis via properties:
print(celula.tipoCelulaId)  # "type-123" (sincronizado)
print(celula.responsavelId)  # "user-456" (property)
print(celula.data)  # {"title": "Célula Nova"} (property)
```

## 🚀 Integração com PipelineItem

Durante execução, a célula é encapsulada em um `PipelineItem`:

```python
from backend.app.core.models import PipelineItem

# Criar PipelineItem para execução
pipeline_item = PipelineItem(
    notebook_item_id=celula.id,  # Referência à Celula
    assignee_id=celula.assignee_id,
    status="running",
    agent_data={"model": "gpt-4", "temperature": 0.7}
)

# Workflow recebe ambos: PipelineItem e Celula
result = workflow_module.execute_workflow(pipeline_item, celula)

# PipelineItem mantém contexto de execução separado
# Celula mantém dados e estado da instância
```

## 📚 Documentação Relacionada

- **[NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)** - Arquitetura completa
- **[README.md](./README.md)** - Documentação de Células Runtime
- **[Tipos de Célula](../../canonicos/tipos_celula/SCHEMA.md)** - Schema de NotebookItemType
- **[backend/app/models/content.py](../../../backend/app/models/content.py)** - Implementação Pydantic
- **[backend/app/core/models.py](../../../backend/app/core/models.py)** - NotebookItem e PipelineItem

---

**Last Update**: 2024-11-17 (Atualizado para arquitetura NotebookItem/NotebookItemType/PipelineItem)
