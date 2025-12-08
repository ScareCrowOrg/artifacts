---
processed: true
processed_date: 2025-12-08
themes:
  - architecture
  - canonical-artifacts
  - templates
  - data-modeling
  - versioning
modules:
  - artifacts
  - architecture
code_verified: true
dead_docs_found: false
---
# Artefatos Canônicos

## 📋 Visão Geral

Artefatos **canônicos** são templates/blueprints imutáveis armazenados em **Git**. Servem como base para criar artefatos runtime instanciados para cada usuário/sessão.

## 🎯 Características

- **Imutáveis**: Não mudam após criação (versionamento via Git)
- **Versionados**: Controle total de versões via Git
- **Compartilhados**: Todos os usuários usam os mesmos canônicos
- **Templates**: Base para instanciação de artefatos runtime

## 📁 Estrutura

```
canonical/
├── README.md              # Este arquivo
├── agent_types/           # Tipos de agentes (blueprints AgentType)
│   ├── README.md
│   └── *.json             # Definições de tipos de agentes
├── agents/                # Instâncias de agentes (Agent)
│   ├── README.md
│   └── *.json             # Agentes específicos
├── cells/                 # Células canônicas (Cell templates)
│   ├── README.md
│   └── *.json             # Células base
├── books/                 # Livros canônicos (Book templates)
│   ├── README.md
│   └── *.json             # Livros mestres
├── ai_models/             # Modelos de IA (AIModel)
│   ├── README.md
│   ├── SCHEMA.md
│   └── *.json             # Configurações de modelos
├── cell_types/            # ⚠️ LEGACY: Tipos de células (TipoCelula format)
│   ├── README.md          # Redirects to notebook_item_types/
│   ├── SCHEMA.md          # Legacy schema documentation
│   └── *.json             # Legacy cell type files
├── notebook_item_types/   # ✅ CURRENT: Tipos de células (NotebookItemType format)
│   ├── README.md          # Current implementation docs
│   └── *.json             # Current cell type definitions
└── workflows/             # Workflows canônicos
    ├── README.md
    └── *.json             # Definições de workflows
```

### Important Notes

**Cell Types Duplication**:
- `cell_types/` = **LEGACY** directory (old TipoCelula format, maintained for backward compatibility)
- `notebook_item_types/` = **CURRENT** directory (new NotebookItemType format)
- All new cell types should be created in `notebook_item_types/`
- See [cell_types/README.md](./cell_types/README.md) for migration guide

## 🔧 Tipos de Artefatos Canônicos

### 1. Notebook Item Types (Cell Types)
**Localização**: `notebook_item_types/` (current) / `cell_types/` (legacy)  
**Schema**: [notebook_item_types/README.md](./notebook_item_types/README.md)  
**Pydantic Model**: `NotebookItemType` in `backend/app/models/content.py`  
**Quantidade**: 7+ tipos implementados

Templates que definem comportamento e estrutura de células (NotebookItem instances). Cada tipo define:
- `default_refs`: Workflows, docs, scripts, componentes
- `default_initial_data`: Dados padrão para novas instâncias
- `allow_instance_override_refs`: Política de sobrescrita

**Exemplos**:
- Ingestion Cell
- Code Generator Cell
- Artifact Editor Cell
- Conversation Memory Cell

**Migration Note**: The old `TipoCelula` format in `cell_types/` has been replaced by `NotebookItemType` in `notebook_item_types/`.

### 2. AI Models
**Localização**: `ai_models/`  
**Schema**: [ai_models/SCHEMA.md](./ai_models/SCHEMA.md)  
**Pydantic Model**: `AIModel` in `backend/app/models/ai_models.py`  
**Quantidade**: 10+ modelos implementados

Configurações de modelos de IA disponíveis no sistema (Ollama, Gemini, OpenAI, Groq).

**Modelos**:
- Ollama: Mistral, DeepSeek Coder, Phi, Gemma 7B, Phi-3, Qwen2.5 Coder 14B
- Google Cloud: gemini-2.5-flash
- OpenAI: GPT-3.5 Turbo, GPT-4o

### 3. Agent Types
**Localização**: `agent_types/`  
**Pydantic Model**: `AgentType` in `backend/app/models/agents.py`  
**Quantidade**: 2+ tipos implementados

Definições de tipos de agentes que processam diferentes tipos de tarefas.

**Tipos**:
- Ollama LLM Processor
- Workflow Orchestrator

### 4. Agents
**Localização**: `agents/`  
**Pydantic Model**: `Agent` in `backend/app/models/agents.py`  
**Quantidade**: 4+ agentes implementados

Instâncias específicas de agentes baseadas nos agent types.

**Agentes**:
- DeepSeek Code Analyzer
- Mistral General Ingestor
- Phi Task Executor
- Main Workflow Orchestrator

### 5. Workflows
**Localização**: `workflows/`

Definições de workflows que orquestram múltiplos agentes e tarefas.

### 6. Livros Canônicos
**Localização**: `livros/`

Livros canônicos que agrupam células para objetivos específicos.

**Exemplos**:
- Issues Queue Book

### 7. Células Canônicas
**Localização**: `celulas/`

Células canônicas reutilizáveis.

## 🔄 Fluxo de Uso

```
1. Usuário faz requisição (via intenção ou API)
        ↓
2. Backend busca artefato canônico apropriado
        ↓
3. Artefato canônico é carregado do Git
        ↓
4. Nova instância runtime é criada baseada no canônico
        ↓
5. Instância é personalizada para usuário/sessão
        ↓
6. Instância runtime é salva em MongoDB
```

## 📝 Formato dos Arquivos

Todos os artefatos canônicos são armazenados como **JSON** seguindo o schema Pydantic definido em `backend/app/models.py`.

### Exemplo: Tipo de Célula

```json
{
  "id": "uuid-do-tipo",
  "descricao": "Gerador de Código",
  "scripts": {
    "python": "def generate(): pass",
    "js": "function generate() {}"
  },
  "markup": "<div>Template HTML</div>",
  "views": ["input", "output", "diff"],
  "workflows": "steps:\n  - parse\n  - generate\n  - validate",
  "versao": "1.0.0"
}
```

## ✏️ Criando Novos Artefatos Canônicos

### Passo a Passo

1. **Definir Schema** (se novo tipo):
   ```python
   # Em backend/app/models.py
   class NovoTipoArtifact(BaseModel):
       id: str
       # ... campos
   ```

2. **Criar Diretório**:
   ```bash
   mkdir -p Artefatos/canonicos/novo_tipo
   ```

3. **Documentar**:
   ```bash
   # Criar README.md
   # Criar SCHEMA.md com exemplos
   ```

4. **Criar Instâncias**:
   ```bash
   # Adicionar arquivos JSON
   # Seguir naming: {uuid}.json
   ```

5. **Versionar**:
   ```bash
   git add Artefatos/canonicos/novo_tipo/
   git commit -m "Add novo_tipo canonical artifacts"
   ```

## 🔍 Consulta e Listagem

### Via API
```http
GET /api/celulas/tipos
# Retorna lista de tipos de célula disponíveis
```

### Via Sistema de Arquivos
```bash
# Listar todos os tipos de célula
ls Artefatos/canonicos/tipos_celula/*.json

# Ver conteúdo de um tipo
cat Artefatos/canonicos/tipos_celula/{uuid}.json
```

### Via Backend
```python
# Em backend/app/seed_data.py
def load_canonical_cell_types():
    """Carrega tipos de célula canônicos do disco."""
    # Lê arquivos JSON
    # Retorna lista de TipoCelula
```

## 🔐 Controle de Versão

### Versionamento Semântico
Artefatos canônicos seguem versionamento semântico:
- **Major**: Mudanças incompatíveis
- **Minor**: Novas funcionalidades compatíveis
- **Patch**: Correções de bugs

### Exemplo
```json
{
  "versao": "2.1.3",
  // 2 = major, 1 = minor, 3 = patch
}
```

### Git History
Todo o histórico de mudanças é preservado no Git:
```bash
# Ver histórico de um artefato
git log Artefatos/canonicos/tipos_celula/{uuid}.json

# Ver diferenças
git diff HEAD~1 Artefatos/canonicos/tipos_celula/{uuid}.json
```

## 📊 Estatísticas Atuais

- **Tipos de Célula**: 20+ tipos implementados
- **Modelos de IA**: 6 modelos (3 Ollama + 1 Gemini + 2 OpenAI)
- **Agent Types**: 2 tipos
- **Agents**: 4 agentes
- **Workflows**: Implementados
- **Livros Canônicos**: 1 livro
- **Células Canônicas**: 1 célula
- **Total de Artefatos**: 30+

## 🔗 Referências

- [Schema de Tipos de Célula](./tipos_celula/SCHEMA.md)
- [Schema de Modelos de IA](./modelos_ia/SCHEMA.md)
- [Agent Types](./agent_types/README.md)
- [Agents](./agents/README.md)
- [Workflows](./workflows/README.md)
- [Livros](./livros/README.md)
- [Backend Models](../../backend/app/models.py)
- [Artefatos Runtime](../runtime/README.md)
- [Documentação Principal de Artefatos](../README.md)

---

**Última Atualização**: 15 de Novembro de 2024  
**Versão**: 1.1 (Atualizado com novos tipos de artefatos: agent_types, agents, workflows, livros, celulas)
