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
# Artefatos Runtime - NotebookItem Instances

## 📋 Visão Geral

Artefatos **runtime** são instâncias de **NotebookItem** criadas durante a execução do sistema, isoladas por usuário (assignee). Armazenados em **MongoDB** e/ou **storage externo** (não versionados em Git).

### 🔄 Nova Arquitetura: NotebookItem/PipelineItem

O sistema runtime agora é baseado em:
- **NotebookItem**: Classe base para células (Celula) e livros (Livro)
- **NotebookItemType**: Tipos canônicos que definem comportamento
- **PipelineItem**: Contexto de execução que referencia NotebookItem

> **📚 Documentação Completa**: [NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)

## 🎯 Características

- **Mutáveis**: Podem ser modificados durante execução
- **Isolados**: Por usuário (`assignee_id`) e contexto de execução
- **Persistentes**: MongoDB para dados estruturados, storage para arquivos
- **Type-Driven**: Herdam comportamento de NotebookItemType canônico
- **Execution Context**: PipelineItem mantém contexto separado dos dados
- **Não Versionados**: Não entram no controle de versão Git

## 📁 Estrutura

```
runtime/
├── README.md              # Este arquivo
├── celulas/               # Células instanciadas
│   ├── README.md
│   └── SCHEMA.md
├── livros/                # Livros (voláteis ou mestres)
│   ├── README.md
│   └── SCHEMA.md
├── sessoes/               # Sessões de trabalho
│   ├── README.md
│   └── SCHEMA.md
└── usuarios/              # Usuários do sistema
    ├── README.md
    └── SCHEMA.md
```

> **Nota**: Esta pasta contém apenas **documentação**. Os artefatos runtime reais estão armazenados em MongoDB, não em arquivos Git.

## 🗄️ Armazenamento

### MongoDB Collections

```
scareversedb/
├── usuarios                # Usuários
├── sessoes                 # Sessões
├── celulas                 # Células (NotebookItem instances)
├── livros                  # Livros (NotebookItem instances)
├── notebook_item_types     # Tipos canônicos (NotebookItemType)
├── pipeline_items          # Contextos de execução (PipelineItem)
└── artefatos_instantiados  # Artefatos genéricos
```

### Estrutura de Isolamento (Nova Arquitetura)

```
MongoDB Document (NotebookItem):
{
  "id": "uuid-artefato",
  "assignee_id": "uuid-usuario",              ← Isolamento por usuário/agente
  "notebook_item_type_id": "uuid-tipo",       ← Referência ao tipo canônico
  "initial_data": {...},                      ← Dados específicos da instância
  "refs": {"workflow_graph": [...]},          ← Override de refs (opcional)
  "fragments": [...],                         ← Memória e resultados
  "created_at": "2024-11-17T...",
  "updated_at": "2024-11-17T..."
}

MongoDB Document (PipelineItem):
{
  "id": "uuid-pipeline",
  "notebook_item_id": "uuid-artefato",        ← Referência ao NotebookItem
  "assignee_id": "uuid-usuario",
  "status": "running",                        ← Estado de execução
  "agent_data": {...},                        ← Dados do agente/modelo
  "error": null,
  "created_at": "2024-11-17T...",
  "updated_at": "2024-11-17T..."
}
```

> **🔑 Separação de Responsabilidades**:
> - **NotebookItem**: Dados e configuração da instância
> - **PipelineItem**: Contexto e estado de execução

## 🔧 Tipos de Artefatos Runtime

### 1. Células (Celula - NotebookItem)
**Collection**: `celulas`  
**Schema**: [celulas/SCHEMA.md](./celulas/SCHEMA.md)  
**Documentação**: [celulas/README.md](./celulas/README.md)

Células são instâncias de NotebookItem criadas a partir de NotebookItemType. Cada célula:
- Herda de `NotebookItem` (classe base)
- Referencia um `NotebookItemType` via `notebook_item_type_id`
- Pertence a um usuário/agente específico (`assignee_id`)
- Pode fazer parte de um livro (`origemLivroId`)
- Contém `initial_data` (dados da instância) e `fragments` (memória/resultados)
- Pode sobrescrever refs do tipo via campo `refs` (se permitido)
- Tem estado (`EstadoCelula`: PENDENTE, EXECUTANDO, FINALIZADO, ERRO)

**Exemplo MongoDB**:
```json
{
  "_id": ObjectId("..."),
  "id": "uuid-celula",
  "assignee_id": "user-123",
  "notebook_item_type_id": "ingestion-type-uuid",
  "tipoCelulaId": "ingestion-type-uuid",
  "initial_data": {
    "processing_mode": "batch",
    "chunk_size": 512
  },
  "refs": {
    "workflow_graph": ["app.workflows.custom"]
  },
  "fragments": [
    {"tipo": "memoria", "conteudo": {...}},
    {"tipo": "execucao", "conteudo": {...}}
  ],
  "estado": "FINALIZADO",
  "created_at": ISODate("2024-11-17T10:00:00Z"),
  "updated_at": ISODate("2024-11-17T10:30:00Z")
}
```

> **⚠️ COMPATIBILIDADE**: Campos legacy (`tipoCelulaId`, `responsavelId`, `data`, `fragmentos`) sincronizados automaticamente.

### 2. Livros (Livro - NotebookItem)
**Collection**: `livros`  
**Schema**: [livros/SCHEMA.md](./livros/SCHEMA.md)  
**Documentação**: [livros/README.md](./livros/README.md)

Livros são instâncias de NotebookItem que agrupam células. Cada livro:
- Herda de `NotebookItem` (classe base)
- Pode referenciar um `NotebookItemType` opcional
- Organiza células via array `celulas` (UUIDs)
- Suporta hierarquia via `filhos` (livros filhos)
- Tipos: `VOLATIL` (temporário) ou `MESTRE` (template permanente)

**Exemplo MongoDB**:
```json
{
  "_id": ObjectId("..."),
  "id": "uuid-livro",
  "assignee_id": "user-123",
  "notebook_item_type_id": "issues-book-type-uuid",
  "name": "Livro de Issues",
  "description": "Gerenciamento de issues do projeto",
  "tipo": "MESTRE",
  "intencao": "Organizar e processar issues",
  "celulas": ["uuid-cel-1", "uuid-cel-2"],
  "filhos": [],
  "is_canonical_system_book": true,
  "created_at": ISODate("2024-11-17T10:00:00Z"),
  "updated_at": ISODate("2024-11-17T10:00:00Z")
}
```

### 3. Pipeline Items (PipelineItem)
**Collection**: `pipeline_items`  
**Schema**: Definido em `backend/app/core/models.py`

PipelineItem é o contexto de execução que referencia NotebookItem. Separação clara:
- **NotebookItem**: Dados, configuração, memória permanente
- **PipelineItem**: Estado de execução, contexto temporário

**Exemplo MongoDB**:
```json
{
  "_id": ObjectId("..."),
  "id": "uuid-pipeline",
  "notebook_item_id": "uuid-celula",
  "assignee_id": "user-123",
  "status": "completed",
  "agent_data": {
    "model": "gpt-4",
    "temperature": 0.7
  },
  "error": null,
  "created_at": ISODate("2024-11-17T10:00:00Z"),
  "updated_at": ISODate("2024-11-17T10:05:00Z")
}
```

> **📚 Detalhes**: Ver [NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md) para fluxo completo de execução.

### 4. Sessões
**Collection**: `sessoes`  
**Schema**: [sessoes/SCHEMA.md](./sessoes/SCHEMA.md)  
**Documentação**: [sessoes/README.md](./sessoes/README.md)

Contextos de trabalho isolados. Permite múltiplas linhas de trabalho simultâneas por usuário.

**Exemplo MongoDB**:
```json
{
  "_id": ObjectId("..."),
  "id": "uuid-sessao",
  "usuarioId": "uuid-usuario",
  "dataCriacao": ISODate("..."),
  "dataExpiracao": ISODate("..."),
  "ativa": true,
  "token": "jwt-token"
}
```

### 4. Usuários
**Collection**: `usuarios`  
**Schema**: [usuarios/SCHEMA.md](./usuarios/SCHEMA.md)  
**Documentação**: [usuarios/README.md](./usuarios/README.md)

Jogadores/usuários do sistema.

**Exemplo MongoDB**:
```json
{
  "_id": ObjectId("..."),
  "id": "uuid-usuario",
  "nome": "João Silva",
  "email": "joao@exemplo.com",
  "googleId": "google-oauth-id",
  "dataRegistro": ISODate("..."),
  "nivel": 5,
  "galaxia": "GalaxiaAlpha"
}
```

## 🔄 Fluxo de Criação

```
1. Usuário faz requisição (intenção ou API direta)
        ↓
2. Backend autentica usuário (OAuth2)
        ↓
3. Backend verifica/cria sessão
        ↓
4. Sistema carrega artefato canônico (Git)
        ↓
5. Nova instância runtime é criada
        ↓
6. Instância é populada com:
   - usuarioId (isolamento)
   - sessaoId (contexto)
   - Dados do canônico (template)
   - Dados específicos do request
        ↓
7. Instância runtime é salva em MongoDB
        ↓
8. ID é retornado ao cliente
```

## 🔐 Isolamento e Segurança

### Isolamento por Usuário
```python
# Backend sempre filtra por usuário autenticado
def get_celulas_usuario(usuario_id: str):
    return db.celulas.find({"assignee_id": usuario_id})

# Impossível acessar células de outro usuário
```

### Isolamento por Sessão
```python
# Filtro adicional por sessão quando necessário
def get_celulas_sessao(usuario_id: str, sessao_id: str):
    return db.celulas.find({
        "assignee_id": usuario_id,
        "sessaoId": sessao_id
    })
```

### Validação de Acesso
```python
# Toda operação valida propriedade
def atualizar_celula(celula_id: str, usuario_id: str, data):
    celula = db.celulas.find_one({"id": celula_id})
    if celula["assignee_id"] != usuario_id:
        raise PermissionError("Acesso negado")
    # ... atualizar
```

## 📊 Ciclo de Vida

### Criação
```http
POST /api/mvp/celulas/criar
{
  "tipoCelulaId": "uuid-tipo",
  "assignee_id": "uuid-usuario"
}

→ Célula criada em MongoDB
```

### Leitura
```http
GET /api/mvp/celulas/{id}

→ Retorna dados da MongoDB
```

### Atualização
```http
PUT /api/mvp/celulas/{id}/atualizar
{
  "estado": "finalizado",
  "fragmentos": [...]
}

→ Atualiza em MongoDB
```

### Execução
```http
POST /api/mvp/celulas/{id}/executar
{
  "parametros": {...}
}

→ Executa e atualiza estado
```

### Deleção
```python
# Soft delete (marcar como inativo)
db.celulas.update_one(
    {"id": celula_id},
    {"$set": {"ativo": False}}
)

# Ou hard delete após período
db.celulas.delete_one({"id": celula_id})
```

## 🔧 Configuração MongoDB

### Arquivo: `backend/app/database.py`

```python
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "scareversedb")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DATABASE_NAME]

# Collections
usuarios_collection = db.usuarios
sessoes_collection = db.sessoes
celulas_collection = db.celulas
livros_collection = db.livros
```

### Indexes

```javascript
// MongoDB shell
use scareversedb

// Index por usuário (comum)
db.celulas.createIndex({"assignee_id": 1})
db.livros.createIndex({"assignee_id": 1})
db.sessoes.createIndex({"usuarioId": 1})

// Index por sessão
db.celulas.createIndex({"sessaoId": 1})

// Index composto (usuário + sessão)
db.celulas.createIndex({"assignee_id": 1, "sessaoId": 1})

// Index por email (usuários)
db.usuarios.createIndex({"email": 1}, {unique: true})
db.usuarios.createIndex({"googleId": 1}, {unique: true})
```

## 📚 APIs REST (Nova Arquitetura)

### Células (NotebookItem)
```http
POST   /api/mvp/celulas/criar           # Aceita notebook_item_type_id ou tipoCelulaId
GET    /api/mvp/celulas/{id}            # Retorna com campos novos e legacy
POST   /api/mvp/celulas/{id}/executar   # Cria PipelineItem, executa workflow
PUT    /api/mvp/celulas/{id}/atualizar  # Atualiza initial_data, refs, fragments
GET    /api/mvp/usuarios/{id}/celulas   # Lista células do usuário
```

### Livros (NotebookItem)
```http
POST   /api/mvp/livros/criar                      # Cria Livro (NotebookItem)
GET    /api/mvp/livros/{id}                       # Obtém Livro completo
POST   /api/mvp/livros/{id}/adicionar_celula     # Adiciona célula ao livro
```

### NotebookItemType (Canonical Types)
```http
GET    /api/notebook-item-types              # Lista tipos disponíveis
GET    /api/notebook-item-types/{id}         # Obtém tipo específico
GET    /api/tipos-celula                     # API legacy (mesmo resultado)
```

### Sessões
```http
POST   /api/mvp/sessoes/criar
GET    /api/mvp/sessoes/usuario/{id}
POST   /api/mvp/sessoes/{id}/fechar
```

### Usuários
```http
POST   /api/mvp/usuarios/registrar
GET    /api/mvp/usuarios/{id}
```

Documentação completa: [backend/docs/](../../backend/docs/)

## 🔗 Referências e Documentação Relacionada

### Arquitetura
- **[NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)** - Arquitetura completa NotebookItem/NotebookItemType/PipelineItem
- **[Células Runtime](./celulas/README.md)** - Documentação detalhada de células
- **[Livros Runtime](./livros/README.md)** - Documentação detalhada de livros
- **[Sessões](./sessoes/README.md)** - Gerenciamento de sessões
- **[Usuários](./usuarios/README.md)** - Gestão de usuários

### Tipos Canônicos
- **[Artefatos Canônicos](../canonicos/README.md)** - Visão geral de artefatos canônicos
- **[NotebookItemType](../canonicos/tipos_celula/README.md)** - Tipos de células canônicos

### Backend
- **[backend/app/models/content.py](../../backend/app/models/content.py)** - Implementação Pydantic (Celula, Livro, NotebookItemType)
- **[backend/app/core/models.py](../../backend/app/core/models.py)** - Classes base (NotebookItem, PipelineItem)
- **[backend/app/models/adapters.py](../../backend/app/models/adapters.py)** - Adapters para execução dinâmica
- **[backend/app/database.py](../../backend/app/database.py)** - Gerenciamento MongoDB

### Testes
- **[tests/unit/backend/test_notebook_item_type.py](../../tests/unit/backend/test_notebook_item_type.py)** - Testes unitários
- **[tests/unit/backend/test_adapter_dynamic_loading.py](../../tests/unit/backend/test_adapter_dynamic_loading.py)** - Testes de workflows dinâmicos

---

**Última Atualização**: 2024-11-17 (Atualizado para arquitetura NotebookItem/NotebookItemType/PipelineItem)  
**Storage**: MongoDB + Storage Externo  
**Arquitetura**: Type-Driven com separação NotebookItem/PipelineItem
