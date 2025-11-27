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
canonicos/
├── README.md              # Este arquivo
├── agent_types/           # Tipos de agentes (blueprints)
│   ├── README.md
│   └── *.json             # Definições de tipos de agentes
├── agents/                # Instâncias de agentes
│   ├── README.md
│   └── *.json             # Agentes específicos
├── celulas/               # Células canônicas
│   ├── README.md
│   └── *.json             # Células base
├── livros/                # Livros canônicos (templates)
│   ├── README.md
│   └── *.json             # Livros mestres
├── modelos_ia/            # Modelos de IA
│   ├── README.md
│   ├── SCHEMA.md
│   └── *.json             # Configurações de modelos
├── tipos_celula/          # Tipos de células (templates)
│   ├── README.md
│   ├── SCHEMA.md
│   └── *.json             # Arquivos JSON dos tipos
└── workflows/             # Workflows canônicos
    ├── README.md
    └── *.json             # Definições de workflows
```

## 🔧 Tipos de Artefatos Canônicos

### 1. Tipos de Célula
**Localização**: `tipos_celula/`  
**Schema**: [tipos_celula/SCHEMA.md](./tipos_celula/SCHEMA.md)  
**Quantidade**: 20+ tipos implementados

Templates que definem comportamento e estrutura de células. Cada tipo pode ter:
- Scripts Python/JavaScript
- Markup HTML/Markdown
- Views disponíveis
- Workflows YAML

**Exemplos**:
- Gerador de Código
- Editor de Artefatos
- Executor de Scripts
- Analisador de Dados

### 2. Modelos de IA
**Localização**: `modelos_ia/`  
**Schema**: [modelos_ia/SCHEMA.md](./modelos_ia/SCHEMA.md)  
**Quantidade**: 6 modelos implementados

Configurações de modelos de IA disponíveis no sistema (Ollama, Gemini, OpenAI).

**Modelos**:
- Mistral (Ollama)
- DeepSeek Code (Ollama)
- Phi (Ollama)
- gemini-2.5-flash (Google Cloud)
- GPT-3.5 Turbo (OpenAI)
- GPT-4o mini (OpenAI)

### 3. Agent Types
**Localização**: `agent_types/`  
**Quantidade**: 2 tipos implementados

Definições de tipos de agentes que processam diferentes tipos de tarefas.

**Tipos**:
- Ollama LLM Processor
- Workflow Orchestrator

### 4. Agents
**Localização**: `agents/`  
**Quantidade**: 4 agentes implementados

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
