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
# Artifacts - NotebookItem/NotebookItemType Architecture

## 📋 Visão Geral

**Artifacts** são a base fundamental do ScareVerse. Tudo no sistema é um artefato - código, texto, configurações, workflows. A nova arquitetura usa **type-driven behavior** baseado em NotebookItem e NotebookItemType.

### 📊 Estatísticas do Sistema (70+ Artefatos Definidos)

| Tipo | Quantidade | Descrição |
|------|-----------|-----------|
| **Notebook Item Types** | 25 | Células, livros e tipos de componentes |
| **AI Models** | 10 | Modelos Ollama, Gemini, OpenAI, Aider, Interpreter |
| **Permissions** | 22 | Permissões granulares do sistema |
| **Agent Types** | 2 | Tipos de agentes (LLM Processor, Orchestrator) |
| **Agents** | 4 | Instâncias de agentes (Phi, DeepSeek, Mistral, Orchestrator) |
| **Roles** | 4 | Funções de usuário (user, admin, viewer, guest) |
| **Books** | 2 | Livros canônicos do sistema |
| **Legacy Cell Types** | 17 | Tipos de célula em formato antigo (TipoCelula) |
| **Cells** | 1 | Célula canônica padrão |
| **Workflows** | 1 | Workflow de ingestão de issues |

## 🔄 Nova Arquitetura: NotebookItem/NotebookItemType/PipelineItem

O sistema foi refatorado para arquitetura tipo-driven:
- **NotebookItem**: Classe base para células (Celula) e livros (Livro)
- **NotebookItemType**: Blueprints canônicos que definem comportamento e workflows
- **PipelineItem**: Contexto de execução separado dos dados do NotebookItem

> **📚 Documentação Completa**: [NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)

## 🎯 Conceito Central

> **Tudo é um artefato. Artefatos complexos são compostos por artefatos menores.**

A decomposição iterativa permite criar módulos que, reagrupados, geram o produto final.

### Artefatos Canônicos (NotebookItemType)
Artefatos **base/templates** armazenados em **Git** (este repositório). São imutáveis e versionados, servindo como blueprints para instâncias. Implementados como `NotebookItemType`.

**Localização**: `artifacts/canonical/`  
**Armazenamento**: Sistema de arquivos (Git)  
**Uso**: NotebookItemType, modelos de IA, workflows, livros mestres

### Artefatos Instanciados (NotebookItem Runtime)
Artefatos **criados durante execução**, baseados em NotebookItemType. Isolados por usuário/agente (`assignee_id`). Armazenados em **MongoDB**.

**Localização**: MongoDB (collection por tipo)  
**Armazenamento**: MongoDB + Storage para arquivos grandes  
**Uso**: Células ativas (Celula), livros voláteis (Livro), PipelineItem para execução

## 📁 Estrutura do Módulo

```
artifacts/
├── README.md                          # Este arquivo
├── canonical/                         # Artefatos canônicos (Git)
│   ├── README.md                      # Doc de artefatos canônicos
│   ├── notebook_item_types/           # ✅ CURRENT: NotebookItemType (blueprints)
│   │   ├── README.md
│   │   └── *.json
│   ├── cell_types/                    # ⚠️ LEGACY: TipoCelula (deprecated format)
│   │   ├── README.md                  # Redirects to notebook_item_types/
│   │   ├── SCHEMA.md
│   │   └── *.json
│   ├── agent_types/                   # Tipos de agentes (AgentType)
│   │   ├── README.md
│   │   └── *.json
│   ├── agents/                        # Instâncias de agentes (Agent)
│   │   ├── README.md
│   │   └── *.json
│   ├── cells/                         # Células canônicas (templates)
│   │   ├── README.md
│   │   └── *.json
│   ├── books/                         # Livros canônicos (mestres)
│   │   ├── README.md
│   │   └── *.json
│   ├── ai_models/                     # Modelos de IA (AIModel)
│   │   ├── README.md
│   │   ├── SCHEMA.md
│   │   └── *.json
│   └── workflows/                     # Workflows canônicos
│       ├── README.md
│       └── *.json
│
└── runtime/                           # Docs de artefatos runtime
    ├── README.md                      # Doc de artefatos runtime (NotebookItem/PipelineItem)
    ├── cells/                         # Células instanciadas (Cell - NotebookItem)
    │   ├── README.md
    │   ├── SCHEMA.md
    │   ├── SANDBOX_CELL_QUICK_REF.md
    │   └── sandbox_guide/             # 🆕 Guia sandbox modularizado
    │       └── *.md
    ├── books/                         # Livros (Book - NotebookItem)
    │   ├── README.md
    │   └── SCHEMA.md
    ├── sessoes/                       # Sessões de usuário
    │   ├── README.md
    │   └── SCHEMA.md
    └── usuarios/                      # Usuários
        ├── README.md
        └── SCHEMA.md
```

> **📌 NOTA**: O diretório `runtime/` contém apenas **documentação**. Os artefatos runtime reais estão armazenados em MongoDB.

> **⚠️ LEGACY vs CURRENT**: 
> - `canonical/cell_types/` = LEGACY (TipoCelula format, deprecated)
> - `canonical/notebook_item_types/` = CURRENT (NotebookItemType format)
> - See [canonical/cell_types/README.md](./canonical/cell_types/README.md) for migration guide

> **🆕 Evolução para Células Sandbox**: O sistema de células está sendo expandido para suportar runtime dinâmico, metadados avançados e controle de lifecycle. Consulte:
> - [Análise de Gaps](../docs/project/SANDBOX_CELLS_GAP_ANALYSIS.md) - Identificação de 8 gaps críticos
> - [Plano de Implementação](../docs/project/SANDBOX_CELLS_IMPLEMENTATION_PLAN.md) - Roadmap de 8 fases
> - [Referência Rápida](./runtime/cells/SANDBOX_CELL_QUICK_REF.md) - Guia de uso dos novos recursos

## 🔄 Fluxo de Artefatos (Nova Arquitetura)

```
1. Usuário expressa intenção
        ↓
2. IA classifica intenção e seleciona NotebookItemType apropriado
        ↓
3. Sistema instancia NotebookItem (Celula/Livro) do tipo selecionado
   - Herda default_refs e default_initial_data do tipo
   - Pode sobrescrever refs se allow_instance_override_refs=True
        ↓
4. Artefato runtime (NotebookItem) salvo em MongoDB
        ↓
5. Em execução:
   - PipelineItem criado referenciando NotebookItem.id
   - Workflow resolvido baseado em política de override
   - Workflow carregado dinamicamente via importlib
   - Workflow executa com PipelineItem + NotebookItem
        ↓
6. Resultado persistido: 
   - NotebookItem.fragments atualizado com memória/resultados
   - PipelineItem.status atualizado (completed/failed)
```

> **📚 Detalhes**: Ver [NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md) para fluxo completo de execução e resolução de workflows.
5. Artefato runtime é executado/processado
        ↓
6. Resultado persistido em MongoDB/Storage
```

## 📚 Tipos de Artefatos Definidos

### 🔷 Notebook Item Types (25 tipos ativos)

**Tipos com nomes descritivos:**
- `3d-mesh-prototyping-cell` - Prototipagem 3D com meshes
- `asset-prototyping-cell` - Prototipagem de assets
- `book-type-generic-v1` - Tipo genérico de livro
- `chat-ia` - Interface de chat com IA
- `conversation-trace-item` - Rastreamento de conversas
- `file-editor-v2` - Editor de arquivos (TypeScript)
- `file-manager-cell` - Gerenciador de arquivos
- `file_editor` - Editor de arquivo (português)
- `ingestion-issue` - Processamento de issues
- `layout-book` - Livro de layouts
- `log-toggle-cell` - Toggle para visualização de logs
- `manual-capture-cell` - Captura manual de dados
- `pipeline-monitoring-cell` - Monitoramento de pipelines
- `png-generator-cell` - Gerador de PNG via Stable Diffusion
- `redis-explorer` - Explorador Redis
- `svg-generator-cell` - Gerador de SVG
- `threejs-scene-generator-cell` - Gerador de cenas Three.js
- `unclassified` / `unclassified-cell` - Célula não classificada
- `vault-token-manager` - Gerenciador de tokens Vault

**Tipos com IDs UUID (especializados):**
- `0cd532bb-f2b9-4951-8768-59644e40c7ab` - Executor de Testes (com workflow YAML)
- `1879e53a-09e0-4909-b958-35e247903298` - Memória de Conversação
- `1cbb5e6f-1570-4462-99c6-287c37b201b6` - Gerador de Código
- `2c2aa39f-fd86-4c28-bdf7-d407fba8cabe` - Editor de Artefatos
- `3a365e84-7431-4dbe-9c6c-17ab90b9d49a` - Validador de Artefatos

### 🤖 AI Models (10 modelos configurados)

**Modelos Ollama (Local):**
| Nome | ID | Modelo | Especialidade | Tamanho |
|------|----|----|---------------|---------|
| Mistral | `68221e1e-f9b1-4157-9b5b-2fdcdf81afc2` | mistral | Conversa geral | 7B |
| DeepSeek Coder | `26ccbd4d-6a26-4cc5-8a74-05694806bd5f` | deepseek-coder-6.7b | Código | 6.7B |
| Gemma | `4e8191e3-ab2e-468f-98e8-2a6891b45d08` | gemma:7b | Texto geral | 7B |
| Phi-3 | `ecb3788c-d1c3-4f19-a2ee-4a441d2b75cc` | phi | Raciocínio | 3.8B |
| Qwen2.5 Coder | `b5db5c64-815a-4a4f-b31c-79357a05e514` | qwen2.5-coder:14b | Código | 14B |

**Modelos Cloud:**
| Nome | ID | Provider | Tipo |
|------|----|----|------|
| Gemini 2.5 Flash | `425c6960-5e4f-4b2f-87a5-9d3b5542713f` | Gemini | Multimodal |
| Gemini 2.5 Flash Lite | `d7e8f9a0-1c2d-3e4f-5a6b-7c8d9e0f1a2b` | Gemini | Multimodal (lite) |
| GPT-4o Mini | `e866b850-0610-444d-b933-9f6bb7fb5e34` | OpenAI | Multimodal |
| Scare Aider | `aider-coder-model` | Aider | Mod. autônoma de código |
| Scare Interpreter | `963fd71c-91e0-4fb2-bedb-4dbde56cac06` | Interpreter | Interpretação e execução |

**Configuração Padrão:**
```json
{
  "temperature": 0.7,
  "max_tokens": 2048,
  "timeout": 30
}
```

### 🤝 Agents (4 instâncias ativas)

| ID | Nome | Agent Type | Modelo |
|----|------|-----------|--------|
| `agent-phi-task-executor-v1` | Phi Task Executor | LLM Processor | Phi |
| `agent-deepseek-code-analyzer-v1` | DeepSeek Code Analyzer | LLM Processor | DeepSeek Coder |
| `agent-mistral-general-ingestor-v1` | Mistral Document Ingestor | LLM Processor | Mistral |
| `main-workflow-orchestrator-v1` | Workflow Orchestrator | Orchestrator | Mistral |

### 📋 Agent Types (2 tipos)

1. **agent-type-ollama-llm-processor-v1** - Processamento genérico com Ollama
   - Especialidades: Text processing, code analysis, data extraction

2. **agent-type-workflow-orchestrator-v1** - Orquestração de workflows
   - Especialidades: Workflow management, agent coordination

### 👥 Roles (4 funções de sistema)

| ID | Nome | Permissões Principais |
|----|------|----|
| `2beefb1e-a2d1-4c47-bcb9-84c566a928c5` | user | cells.create, cells.read_own, books.create, ai_models.use |
| `aa73ebe0-4b74-480c-adb1-9b0b8842f392` | admin | Sistema completo (todas as permissões) |
| `944f834b-6e9e-4e57-b683-beaef6ec70a6` | guest | Leitura limitada |
| `e3ee8eda-9a89-4401-ae56-fa56161548c4` | viewer | Visualização apenas |

### 🔐 Permissions (22 permissões granulares)

**Recursos de Célula:**
- `cells.create` - Criar novas células
- `cells.read_own` - Ler próprias células
- `cells.read_any` - Ler qualquer célula
- `cells.update_own` - Atualizar próprias células
- `cells.update_any` - Atualizar qualquer célula
- `cells.delete_own` - Deletar próprias células
- `cells.delete_any` - Deletar qualquer célula

**Recursos de Livro:**
- `books.create` - Criar livros
- `books.read_own` - Ler próprios livros
- `books.read_any` - Ler qualquer livro
- `books.update_own` - Atualizar próprios livros
- `books.update_any` - Atualizar qualquer livro

**Recursos de Usuário:**
- `users.read_own` - Ler dados do próprio usuário
- `users.read_any` - Ler dados de qualquer usuário
- `users.update_own` - Atualizar dados do próprio usuário
- `users.update_any` - Atualizar dados de qualquer usuário

**Recursos Sistêmicos:**
- `system.configure` - Configurar sistema
- `ai_models.use` - Usar modelos de IA
- `ai_models.create` - Criar modelos de IA
- `ai_models.manage` - Gerenciar modelos de IA

### 📖 Books (2 livros canônicos do sistema)

| ID | Nome | Tipo | Propósito |
|----|------|------|----------|
| `book-conversation-traces-v1` | conversation-traces | VOLATILE | Armazenar traces de conversas para observabilidade |
| `book-issues-queue-v1` | issues-queue | VOLATILE | Gerenciar fila de issues de ingestão |

### 📚 Documentação por Tipo

- [canonical/README.md](./canonical/README.md) - Documentação completa
- [canonical/notebook_item_types/](./canonical/notebook_item_types/) - ✅ CURRENT: Tipos de células (NotebookItemType)
- [canonical/cell_types/](./canonical/cell_types/) - ⚠️ LEGACY: Tipos de células (TipoCelula, deprecated)
- [canonical/ai_models/](./canonical/ai_models/) - Modelos de IA (AIModel: Ollama, Gemini, OpenAI)
- [canonical/agent_types/](./canonical/agent_types/) - Tipos de agentes (AgentType)
- [canonical/agents/](./canonical/agents/) - Instâncias de agentes (Agent)
- [canonical/permissions/](./canonical/permissions/) - Definições de permissões
- [canonical/roles/](./canonical/roles/) - Funções do sistema
- [canonical/workflows/](./canonical/workflows/) - Workflows canônicos
- [canonical/books/](./canonical/books/) - Livros canônicos (Book)
- [canonical/cells/](./canonical/cells/) - Células canônicas (Cell)

### Artefatos Runtime
- [runtime/README.md](./runtime/README.md) - Documentação completa
- [runtime/cells/](./runtime/cells/) - Células instanciadas (Cell instances)
- [runtime/books/](./runtime/books/) - Livros voláteis (Book instances)
- [runtime/sessoes/](./runtime/sessoes/) - Sessões
- [runtime/usuarios/](./runtime/usuarios/) - Usuários

## 🔗 Integração com Backend

Os schemas de artefatos são implementados no backend:

**Arquivos Principais**:
- `backend/app/models/content.py` - Cell, Book, NotebookItemType
- `backend/app/models/ai_models.py` - AIModel
- `backend/app/models/agents.py` - Agent, AgentType
- `backend/app/models/security.py` - Role, Permission
- `backend/app/models/artifacts.py` - CanonicalArtifact, InstantiatedArtifact
- `backend/app/core/models.py` - NotebookItem, PipelineItem (classes base)

**Modelos Implementados (Core)**:
- `NotebookItemType` - Template de tipo de célula (canônico) - ✅ CURRENT
- `Cell` - Célula instanciada (runtime, extends NotebookItem)
- `Book` - Livro de células (runtime/canônico, extends NotebookItem)
- `AIModel` - Modelo de IA com 10 instâncias configuradas
- `Agent` - Agente instanciado (4 agentes ativos)
- `AgentType` - Tipo de agente (2 tipos disponíveis)
- `PipelineItem` - Contexto de execução temporário

**Modelos de Segurança**:
- `Role` - 4 funções (user, admin, viewer, guest)
- `Permission` - 22 permissões granulares
- Suporte a RBAC (Role-Based Access Control)

**Modelos Legacy**:
- `TipoCelula` - LEGACY model (deprecated, use NotebookItemType)
- `CanonicalArtifact` - Artefato canônico genérico
- `InstantiatedArtifact` - Artefato runtime genérico

**Modelos de Sistema**:
- `Usuario` - Usuário/jogador
- `Sessao` - Sessão de trabalho

**APIs REST - Células**:
- `POST /api/cells/create` - Criar célula (instanciar de tipo) [Requer: cells.create]
- `GET /api/cells/{id}` - Obter célula [Requer: cells.read_own ou cells.read_any]
- `POST /api/cells/{id}/execute` - Executar célula [Requer: cells.update_own ou cells.update_any]
- `PUT /api/cells/{id}` - Atualizar célula [Requer: cells.update_own ou cells.update_any]
- `DELETE /api/cells/{id}` - Deletar célula [Requer: cells.delete_own ou cells.delete_any]

**APIs REST - Livros**:
- `POST /api/books/create` - Criar livro [Requer: books.create]
- `GET /api/books/{id}` - Obter livro [Requer: books.read_own ou books.read_any]
- `POST /api/books/{id}/add-cell` - Adicionar célula a livro [Requer: books.update_own ou books.update_any]
- `PUT /api/books/{id}` - Atualizar livro [Requer: books.update_own ou books.update_any]

**APIs REST - Modelos de IA**:
- `GET /api/ai-models/list` - Listar modelos disponíveis [Requer: ai_models.use]
- `POST /api/ai-models/create` - Criar novo modelo [Requer: ai_models.manage]
- `GET /api/ai-models/{id}` - Obter configuração de modelo [Requer: ai_models.use]
- `PUT /api/ai-models/{id}` - Atualizar modelo [Requer: ai_models.manage]

**APIs REST - Agents**:
- `GET /api/agents/list` - Listar agentes disponíveis
- `POST /api/agents/{id}/invoke` - Invocar agente
- `GET /api/agent-types/list` - Listar tipos de agente

**APIs REST - Segurança**:
- `GET /api/roles/list` - Listar funções [Requer: system.configure]
- `GET /api/permissions/list` - Listar permissões [Requer: system.configure]
- `GET /api/users/{id}/permissions` - Obter permissões do usuário [Requer: users.read_own ou users.read_any]

**APIs REST - Segurança (Experimental)**:
- `POST /api/notebooks/sync` - Sincronizar definições de artefatos
- `GET /api/notebook-item-types/list` - Listar tipos de notebook item

**Legacy APIs** (still functional):
- `POST /api/celulas/criar` - Maps to /api/cells/create
- `GET /api/celulas/{id}` - Maps to /api/cells/{id}
- `POST /api/modelos-ia/listar` - Maps to /api/ai-models/list

Documentação completa: [backend/docs/](../backend/docs/)

## 🎮 Uso no Jogo

### Criação via Intenção
```python
# Usuário expressa intenção
intencao = "Criar um script que lista arquivos"

# IA processa e cria artefato
POST /api/chat/processar
{
  "intencao": "Criar um script que lista arquivos",
  "assignee_id": "uuid-do-usuario",
  "modelo": "mistral"
}

# Sistema:
# 1. Classifica intenção
# 2. Seleciona tipo de célula apropriado (canônico)
# 3. Instancia célula para usuário
# 4. Retorna célula criada (runtime)
```

### Estrutura de Dados

**Canônico (Git)**:
```json
{
  "id": "uuid-tipo-celula",
  "descricao": "Gerador de Código",
  "scripts": {
    "python": "# código template",
    "js": "// código template"
  },
  "versao": "1.0.0"
}
```

**Runtime (MongoDB)**:
```json
{
  "id": "uuid-celula-instanciada",
  "tipoCelulaId": "uuid-tipo-celula",
  "assignee_id": "uuid-usuario",
  "fragmentos": [
    {"tipo": "execucao", "resultado": "output"}
  ],
  "estado": "finalizado"
}
```

## 🔐 Isolamento e Segurança (Nova Arquitetura)

### Por Usuário/Agente (assignee_id)
Cada usuário/agente tem seu próprio namespace de artefatos runtime via `assignee_id`. Impossível acessar artefatos de outro usuário sem permissões explícitas.

### Por Tipo (NotebookItemType)
Políticas de override (`allow_instance_override_refs`) controlam se instâncias podem sobrescrever comportamentos do tipo, garantindo consistência quando necessário.

### Separação de Contexto
**NotebookItem** mantém dados permanentes. **PipelineItem** mantém contexto de execução temporário, garantindo que dados e estado sejam gerenciados independentemente.

### Versionamento
Artefatos canônicos (NotebookItemType) são versionados em Git, garantindo auditoria, rollback e rastreabilidade.

## 📖 Schemas Detalhados e Documentação

Cada subdiretório contém:
- **README.md**: Documentação do tipo de artefato
- **SCHEMA.md**: Schema JSON/Pydantic detalhado com exemplos

### Documentação Canônica
- **[NotebookItemType](./canonicos/tipos_celula/README.md)** - Blueprints de tipos de células
- **[NotebookItemType Schema](./canonicos/tipos_celula/SCHEMA.md)** - Schema completo
- **[Modelos de IA](./canonicos/modelos_ia/README.md)** - Modelos configurados
- **[Workflows](./canonicos/workflows/README.md)** - Workflows canônicos

### Documentação Runtime
- **[Células Runtime](./runtime/celulas/README.md)** - Instâncias de Celula (NotebookItem)
- **[Células Schema](./runtime/celulas/SCHEMA.md)** - Schema completo de Celula
- **[Livros Runtime](./runtime/livros/README.md)** - Instâncias de Livro (NotebookItem)
- **[Livros Schema](./runtime/livros/SCHEMA.md)** - Schema completo de Livro
- **[Sessões](./runtime/sessoes/README.md)** - Gerenciamento de sessões
- **[Usuários](./runtime/usuarios/README.md)** - Gestão de usuários

## 📋 Padrões de Nomenclatura e Versionamento

### Convenções de ID

1. **Slugs Descritivos (Recomendado)**:
   - Formato: `kebab-case` ou `kebab-case-v1` (com versionamento)
   - Exemplo: `png-generator-cell`, `agent-type-ollama-llm-processor-v1`
   - Uso: Tipos comuns, agentes principais, tipos conhecidos

2. **UUIDs Aleatórios**:
   - Formato: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   - Exemplo: `68221e1e-f9b1-4157-9b5b-2fdcdf81afc2`
   - Uso: Modelos de IA, permissões, customizações esotéricas

3. **Arquivo vs ID**:
   - Arquivo: `agent-type-ollama-llm-processor-v1.json`
   - ID no JSON: `"id": "agent-type-ollama-llm-processor-v1"`
   - Arquivo: `68221e1e-f9b1-4157-9b5b-2fdcdf81afc2.json`
   - ID no JSON: `"id": "68221e1e-f9b1-4157-9b5b-2fdcdf81afc2"`

### Versionamento Semântico

Todos os artefatos seguem **SemVer**:
- `version: "1.0.0"` - Formato padrão
- Stored in: `version` field no JSON
- Rastreamento: Via Git commit history
- Rollback: Suportado via Git checkout

### Campos Universais

Todo artefato canônico deve ter:
```json
{
  "id": "unique-identifier",
  "name": "Descriptive Name",
  "description": "Detailed description of the artifact",
  "version": "1.0.0",
  "createdAt": "2024-11-17T10:30:00Z",
  "updatedAt": "2024-11-17T10:30:00Z"
}
```

## 🔐 Segurança e Isolamento

### Criptografia de Credentials

API keys em `ai_models/` são criptografadas com **Fernet (AES-128-CBC + HMAC)**:
```bash
# Definir em .env
ENCRYPTION_KEY=your-fernet-key
```

### Isolamento por assignee_id

Cada usuário/agente tem namespace isolado:
- Impossível acessar artefatos de outro sem permissões explícitas
- Verificação em runtime via RBAC
- Audit trail em MongoDB

### Controle de Override

```json
{
  "allow_instance_override_refs": true,
  "allow_instance_override_workflow": false
}
```

## 🚀 Adicionando Novos Tipos

### 1. Criar NotebookItemType

```python
# backend/app/models/content.py ou seed_data.py
novo_tipo = NotebookItemType(
    id="novo-tipo-name",  # ou UUID
    name="Novo Tipo",
    description="Descrição do novo tipo",
    category="processing|visualization|utility",
    default_refs={
        "view": ["frontend/View.vue"],
        "scripts": ["backend/scripts/main.py"],
        "docs": ["docs/README.md"]
    },
    default_initial_data={"config": "default"},
    allow_instance_override_refs=True,
    properties_schema={...}
)

# Salvar em MongoDB (via seed_data ou API)
db.insert("notebook_item_types", novo_tipo, is_canonical=True)
```

### 2. Registrar em Git

1. Criar arquivo em `artifacts/canonical/notebook_item_types/{id}.json`
2. Commit com mensagem: `feat: Add new NotebookItemType {id}`

### 3. Documentar

1. Atualizar [canonical/notebook_item_types/README.md](./canonical/notebook_item_types/README.md)
2. Adicionar entrada em [SCHEMA.md](./canonical/notebook_item_types/SCHEMA.md)
3. Atualizar este README com referência
4. Criar documentação no diretório do tipo se necessário

### 4. Implementar e Testar

1. Implementar endpoints no backend se necessário
2. Frontend: Se tiver `can_render_dynamically`, criar Vue component
3. Adicionar testes unitários: `tests/unit/backend/test_notebook_item_type_{id}.py`
4. Testar via API: `POST /api/cells/create` com o novo tipo

## 📊 Estrutura Exemplo: PNG Generator Cell

Veja um tipo real implementado:

```json
{
  "id": "png-generator-cell",
  "name": "PNG Generator Cell",
  "description": "Interactive cell for generating PNG images from text prompts using Stable Diffusion AI",
  "category": "visualization",
  "version": "1.0.0",
  "can_render_dynamically": true,
  "default_refs": {
    "view": ["cell_types/png-generator-cell/frontend/View.vue"],
    "scripts": ["cell_types/png-generator-cell/backend/scripts/main.py"],
    "docs": ["cell_types/png-generator-cell/docs/README.md"]
  },
  "default_initial_data": {
    "category": "ephemeral",
    "prompt": "",
    "generatedPng": null,
    "isGenerating": false,
    "generationParams": {
      "width": 512,
      "height": 512,
      "steps": 20,
      "cfg_scale": 7.0,
      "seed": -1
    }
  },
  "allow_instance_override_refs": true,
  "properties_schema": {
    "type": "object",
    "properties": {
      "prompt": {"type": "string"},
      "generationParams": {"type": "object"}
    }
  }
}
```

## 🔗 Links Úteis e Referências

### 📐 Arquitetura
- **[NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)** - Arquitetura completa NotebookItem/NotebookItemType/PipelineItem
- **[Conceitos Centrais](../docs/concept/conceito_central_e_mecanicas.md)** - Teoria dos artefatos
- **[ScareVerse Project](../ScareVerse_Project.md)** - Visão geral do projeto

### 🛠️ Backend - Implementação
- **[backend/app/models/content.py](../backend/app/models/content.py)** - Modelos Pydantic (Cell, Book, NotebookItemType)
- **[backend/app/models/security.py](../backend/app/models/security.py)** - Modelos de segurança (Role, Permission, RBAC)
- **[backend/app/models/ai_models.py](../backend/app/models/ai_models.py)** - Configuração de modelos de IA
- **[backend/app/models/agents.py](../backend/app/models/agents.py)** - Definição de agentes (Agent, AgentType)
- **[backend/app/core/models.py](../backend/app/core/models.py)** - Classes base (NotebookItem, PipelineItem)
- **[backend/app/models/adapters.py](../backend/app/models/adapters.py)** - Adapters para execução dinâmica
- **[Backend API Docs](../backend/docs/)** - Documentação completa de APIs REST

### 🎯 Documentação Canônica
- **[canonical/README.md](./canonical/README.md)** - Overview de artefatos canônicos
- **[canonical/notebook_item_types/README.md](./canonical/notebook_item_types/README.md)** - Tipos de célula disponíveis
- **[canonical/ai_models/README.md](./canonical/ai_models/README.md)** - Documentação de modelos (v1.2)
- **[canonical/ai_models/SCHEMA.md](./canonical/ai_models/SCHEMA.md)** - Schema detalhado (Pydantic)
- **[canonical/agent_types/README.md](./canonical/agent_types/README.md)** - Tipos de agentes
- **[canonical/roles/README.md](./canonical/roles/README.md)** - Funções do sistema
- **[canonical/permissions/README.md](./canonical/permissions/README.md)** - Permissões disponíveis
- **[canonical/workflows/README.md](./canonical/workflows/README.md)** - Workflows canônicos

### 🧪 Testes
- **[tests/unit/backend/test_notebook_item_type.py](../tests/unit/backend/test_notebook_item_type.py)** - Testes unitários
- **[tests/unit/backend/test_adapter_dynamic_loading.py](../tests/unit/backend/test_adapter_dynamic_loading.py)** - Testes de workflows dinâmicos
- **[tests/unit/backend/test_rbac.py](../tests/unit/backend/test_rbac.py)** - Testes de controle de acesso
- **[tests/integration/test_artifact_lifecycle.py](../tests/integration/test_artifact_lifecycle.py)** - Testes de ciclo de vida

### 📝 Como Migrar de Legacy

- **[cell_types/README.md](./canonical/cell_types/README.md)** - Guia de migração de TipoCelula para NotebookItemType
- **[LEGACY_TO_CURRENT_MIGRATION.md](./LEGACY_TO_CURRENT_MIGRATION.md)** - Mapeamento completo

### 🔓 Seeding de Dados

Todos os artefatos canônicos são auto-carregados na inicialização:
```bash
# Localização dos seeders
backend/app/seed_data/
├── notebook_item_types_seeder.py
├── ai_models_seeder.py
├── roles_seeder.py
├── permissions_seeder.py
└── agents_seeder.py

# Disparador automático em backend startup
backend/app/core/startup.py
```

---

## 📌 Resumo Executivo

**ScareVerse Artifacts** é um sistema **type-driven** baseado em **NotebookItem/NotebookItemType/PipelineItem** que gerencia:

- **25 Tipos de Células** - Componentes reutilizáveis (visualização, processamento, utilidade)
- **10 Modelos de IA** - Ollama, Gemini, OpenAI, Aider, Interpreter
- **4 Agentes Especializados** - Task executor, code analyzer, document ingestor, orchestrator
- **22 Permissões Granulares** - RBAC com 4 funções (user, admin, viewer, guest)
- **2 Livros Canônicos** - Sistema para organizar e rastrear conversas e issues
- **100% Versionado em Git** - Auditoria completa, rollback suportado
- **MongoDB Runtime** - Isolamento por assignee_id, separação Data/Context via PipelineItem

**Padrão Central**: Artefatos canônicos (Git) → Instâncias runtime (MongoDB) → Execução isolada (PipelineItem)

---

**Última Atualização**: 2026-02-02 (Atualizado com estatísticas reais de artefatos definidos)
**Versão**: 2.1 (Type-Driven Architecture + Complete Artifact Catalog)
**Status**: ✅ Produção - 70+ artefatos canônicos definidos e funcionais
**Compatibilidade**: Campos legacy mantidos com sincronização automática
