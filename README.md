# Artefatos - NotebookItem/NotebookItemType Architecture

## 📋 Visão Geral

**Artefatos** são a base fundamental do ScareVerse. Tudo no sistema é um artefato - código, texto, configurações, workflows. A nova arquitetura usa **type-driven behavior** baseado em NotebookItem e NotebookItemType.

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

**Localização**: `Artefatos/canonicos/`  
**Armazenamento**: Sistema de arquivos (Git)  
**Uso**: NotebookItemType, modelos de IA, workflows, livros mestres

### Artefatos Instanciados (NotebookItem Runtime)
Artefatos **criados durante execução**, baseados em NotebookItemType. Isolados por usuário/agente (`assignee_id`). Armazenados em **MongoDB**.

**Localização**: MongoDB (collection por tipo)  
**Armazenamento**: MongoDB + Storage para arquivos grandes  
**Uso**: Células ativas (Celula), livros voláteis (Livro), PipelineItem para execução

## 📁 Estrutura do Módulo

```
Artefatos/
├── README.md                          # Este arquivo
├── canonicos/                         # Artefatos canônicos (Git)
│   ├── README.md                      # Doc de artefatos canônicos
│   ├── tipos_celula/                  # NotebookItemType (blueprints de tipos)
│   │   ├── README.md
│   │   ├── SCHEMA.md
│   │   └── *.json
│   ├── agent_types/                   # Tipos de agentes
│   │   ├── README.md
│   │   └── *.json
│   ├── agents/                        # Instâncias de agentes canônicos
│   │   ├── README.md
│   │   └── *.json
│   ├── celulas/                       # Células canônicas (templates)
│   │   ├── README.md
│   │   └── *.json
│   ├── livros/                        # Livros canônicos (mestres)
│   │   ├── README.md
│   │   └── *.json
│   ├── modelos_ia/                    # Modelos de IA configurados
│   │   ├── README.md
│   │   ├── SCHEMA.md
│   │   └── *.json
│   └── workflows/                     # Workflows canônicos
│       ├── README.md
│       └── *.json
│
└── runtime/                           # Docs de artefatos runtime
    ├── README.md                      # Doc de artefatos runtime (NotebookItem/PipelineItem)
    ├── celulas/                       # Células instanciadas (Celula - NotebookItem)
    │   ├── README.md
    │   ├── SCHEMA.md
    │   ├── SANDBOX_CELL_QUICK_REF.md
    │   └── sandbox_guide/             # 🆕 Guia sandbox modularizado
    │       └── *.md
    ├── livros/                        # Livros (Livro - NotebookItem)
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

> **🆕 Evolução para Células Sandbox**: O sistema de células está sendo expandido para suportar runtime dinâmico, metadados avançados e controle de lifecycle. Consulte:
> - [Análise de Gaps](../docs/project/SANDBOX_CELLS_GAP_ANALYSIS.md) - Identificação de 8 gaps críticos
> - [Plano de Implementação](../docs/project/SANDBOX_CELLS_IMPLEMENTATION_PLAN.md) - Roadmap de 8 fases
> - [Referência Rápida](./runtime/celulas/SANDBOX_CELL_QUICK_REF.md) - Guia de uso dos novos recursos

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

## 📚 Documentação por Tipo

### Artefatos Canônicos
- [canonicos/README.md](./canonicos/README.md) - Documentação completa
- [canonicos/tipos_celula/](./canonicos/tipos_celula/) - Tipos de células
- [canonicos/modelos_ia/](./canonicos/modelos_ia/) - Modelos de IA (Ollama, Gemini, OpenAI)
- [canonicos/agent_types/](./canonicos/agent_types/) - Tipos de agentes
- [canonicos/agents/](./canonicos/agents/) - Instâncias de agentes
- [canonicos/workflows/](./canonicos/workflows/) - Workflows
- [canonicos/livros/](./canonicos/livros/) - Livros canônicos
- [canonicos/celulas/](./canonicos/celulas/) - Células canônicas

### Artefatos Runtime
- [runtime/README.md](./runtime/README.md) - Documentação completa
- [runtime/celulas/](./runtime/celulas/) - Células instanciadas
- [runtime/livros/](./runtime/livros/) - Livros voláteis
- [runtime/sessoes/](./runtime/sessoes/) - Sessões
- [runtime/usuarios/](./runtime/usuarios/) - Usuários

## 🔗 Integração com Backend

Os schemas de artefatos são implementados no backend:

**Arquivo**: `backend/app/models.py`

**Modelos Implementados**:
- `TipoCelula` - Template de tipo de célula (canônico)
- `Celula` - Célula instanciada (runtime)
- `Livro` - Livro de células (runtime/canônico)
- `ModeloIA` - Modelo de IA (canônico)
- `ArtefatoCanonico` - Artefato canônico genérico
- `ArtefatoInstanciado` - Artefato runtime genérico
- `Usuario` - Usuário/jogador
- `Sessao` - Sessão de trabalho

**APIs REST**:
- `POST /api/celulas/criar` - Criar célula (instanciar de tipo)
- `GET /api/celulas/{id}` - Obter célula
- `POST /api/celulas/{id}/executar` - Executar célula
- `POST /api/livros/criar` - Criar livro
- `POST /api/livros/{id}/adicionar_celula` - Adicionar célula a livro
- `GET /api/modelos-ia/listar` - Listar modelos de IA disponíveis
- `POST /api/modelos-ia/criar` - Criar novo modelo de IA

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

## 🚀 Adicionando Novos Tipos

### 1. Criar NotebookItemType

```python
# backend/app/models/content.py ou seed_data.py
novo_tipo = NotebookItemType(
    id="novo-tipo-uuid",
    name="Novo Tipo",
    description="Descrição do novo tipo",
    default_refs={
        "workflow_graph": ["app.workflows.novo_workflow"],
        "docs": ["docs/novo_tipo.md"]
    },
    default_initial_data={"config": "default"},
    allow_instance_override_refs=True
)

# Salvar em MongoDB
db.insert("notebook_item_types", novo_tipo, is_canonical=True)
```

### 2. Documentar

1. Criar diretório apropriado em `canonicos/` (se novo tipo canônico)
2. Adicionar README.md e SCHEMA.md
3. Atualizar este README com referências
4. Implementar endpoints no backend se necessário
5. Adicionar testes unitários para o novo tipo

## 🔗 Links Úteis e Referências

### Arquitetura
- **[NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md](../docs/NOTEBOOK_ITEM_TYPE_ARCHITECTURE.md)** - Arquitetura completa NotebookItem/NotebookItemType/PipelineItem
- **[Conceitos Centrais](../docs/concept/conceito_central_e_mecanicas.md)** - Teoria dos artefatos
- **[ScareVerse Project](../ScareVerse_Project.md)** - Visão geral do projeto

### Backend
- **[backend/app/models/content.py](../backend/app/models/content.py)** - Implementação Pydantic (Celula, Livro, NotebookItemType)
- **[backend/app/core/models.py](../backend/app/core/models.py)** - Classes base (NotebookItem, PipelineItem)
- **[backend/app/models/adapters.py](../backend/app/models/adapters.py)** - Adapters para execução dinâmica
- **[Backend API Docs](../backend/docs/)** - Documentação completa de APIs

### Testes
- **[tests/unit/backend/test_notebook_item_type.py](../tests/unit/backend/test_notebook_item_type.py)** - Testes unitários
- **[tests/unit/backend/test_adapter_dynamic_loading.py](../tests/unit/backend/test_adapter_dynamic_loading.py)** - Testes de workflows dinâmicos

---

**Última Atualização**: 2024-11-17 (Atualizado para arquitetura NotebookItem/NotebookItemType/PipelineItem)  
**Versão**: 2.0 (Type-Driven Architecture)  
**Compatibilidade**: Campos legacy mantidos com sincronização automática
