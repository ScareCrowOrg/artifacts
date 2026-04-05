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
# Notebook Item Types - Canonical Type Definitions

Este diretório contém as definições canônicas de tipos de itens de notebook no sistema ScareVerse. NotebookItemTypes são especificações reutilizáveis que definem o comportamento, estrutura e metadados de células (Celulas) e livros (Livros).

(This directory contains canonical definitions of notebook item types in the ScareVerse system. NotebookItemTypes are reusable specifications that define the behavior, structure, and metadata of cells (Celulas) and books (Livros).)

## Índice

### Arquivos

Tipos de item disponíveis neste diretório:

- `conversation-trace-item.json` - Tipo para rastreamento estruturado de conversas através do pipeline RAG
- `book-type-generic-v1.json` - Tipo genérico para livros de conhecimento
- `unclassified.json` - Tipo genérico de célula não classificada
- `ingestion-issue.json` - Tipo para issues de ingestão de documentos
- `file_editor.json` - Tipo para células de edição de arquivos
- Outros tipos UUID - Tipos customizados para casos específicos

### Subdiretórios

Este diretório não possui subdiretórios no momento.

## Visão Geral

NotebookItemTypes no sistema ScareVerse representam especificações reutilizáveis que definem:
- **Estrutura de Dados**: Propriedades, campos e tipos de dados
- **Referências Padrão**: Workflows, scripts Python, documentação
- **Comportamento Inicial**: Ícones, categorias, valores padrão
- **Herança**: Instâncias podem sobrescrever ou herdar configurações

### Propósito

NotebookItemTypes servem múltiplos propósitos no sistema:
1. **Reutilização**: Evitar duplicação de especificações
2. **Consistência**: Garantir comportamento uniforme entre instâncias
3. **Extensibilidade**: Permitir customização de instâncias específicas
4. **Tipagem**: Validar estrutura de dados em tempo de execução

## Estrutura de NotebookItemType

### Estrutura JSON

```json
{
  "id": "unique-type-id",
  "name": "Type Name",
  "description": "Detailed description of the type purpose and usage",
  "default_refs": {
    "workflow_graph": ["path/to/workflow.yaml"],
    "python": ["backend/app/services/my_service.py"],
    "docs": ["docs/my_type.md"],
    "javascript": ["frontend/components/MyComponent.vue"],
    "yaml": ["config/my_config.yaml"],
    "attachments": []
  },
  "default_initial_data": {
    "category": "persistida|efemera|volatil",
    "icon": "mdi-icon-name",
    "properties": [
      {
        "name": "property_name",
        "type": "string|number|boolean|text|object|array",
        "label": "Property Label",
        "description": "Property description",
        "required": true|false,
        "default": "default value"
      }
    ],
    "views_components": ["ComponentName"],
    "versao": "1.0.0"
  },
  "allow_instance_override_refs": true|false,
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp"
}
```

### Campos Obrigatórios

- **id**: Identificador único do tipo (string, kebab-case)
- **name**: Nome legível do tipo
- **description**: Descrição detalhada do propósito e uso
- **default_refs**: Referências padrão a recursos externos (dict)
- **default_initial_data**: Dados iniciais aplicados a novas instâncias (dict)
- **allow_instance_override_refs**: Se instâncias podem sobrescrever refs (boolean)

### Campos de Metadados

- **created_at**: Timestamp de criação (ISO 8601)
- **updated_at**: Timestamp de última atualização (ISO 8601)

## Categorias de Tipos

### 1. Tipos de Célula (Cell Types)

Definem estrutura e comportamento de células individuais:
- **Persistida**: Células com persistência de longo prazo (ex: notas, documentos)
- **Efêmera**: Células temporárias (ex: traces, logs)
- **Volátil**: Células transientes (ex: cache, estado temporário)

### 2. Tipos de Livro (Book Types)

Definem estrutura e comportamento de livros (coleções de células):
- **Generic Book**: Livro genérico para organização de conteúdo
- **System Book**: Livros do sistema (ex: issues-queue, conversation-traces)
- **Knowledge Book**: Livros de conhecimento para RAG

### 3. Tipos Especializados

Tipos para casos de uso específicos:
- **conversation-trace-item**: Rastreamento estruturado de conversas
- **ingestion-issue**: Issues de ingestão de documentos
- **file_editor**: Edição de arquivos no sistema

## Uso

### Criando um Novo NotebookItemType

1. **Definir Estrutura**:
```bash
# Criar arquivo JSON do tipo
touch Artefatos/canonicos/notebook_item_types/my-type-v1.json
```

2. **Configurar Metadados**:
```json
{
  "id": "my-type-v1",
  "name": "My Custom Type",
  "description": "A custom type for specific use case",
  "default_refs": {
    "python": ["backend/app/services/my_service.py"]
  },
  "default_initial_data": {
    "category": "persistida",
    "icon": "mdi-file-document",
    "properties": [
      {
        "name": "title",
        "type": "string",
        "label": "Title",
        "required": true
      }
    ],
    "versao": "1.0.0"
  },
  "allow_instance_override_refs": true
}
```

3. **Registrar no Sistema**:
O tipo será automaticamente carregado pela função `seed_notebook_item_types()` no próximo seed do banco de dados.

```python
# Executar seed
python -m backend.app.scripts.seed_data
```

### Usando um NotebookItemType

```python
# Criar uma célula baseada em um tipo
from app.models import Celula
from app.database import db

cell = Celula(
    assignee_id="user-id",
    notebook_item_type_id="conversation-trace-item",  # Referência ao tipo
    tipoCelulaId="conversation-trace-item",
    initial_data={
        "conversation_id": "conv_123",
        "tracing_enabled": True
    }
)

db.insert("celulas", cell, is_canonical=False)
```

### Sobrescrevendo Configurações

Se `allow_instance_override_refs` é `true`, instâncias podem sobrescrever `refs`:

```python
cell = Celula(
    assignee_id="user-id",
    notebook_item_type_id="my-type-v1",
    refs={
        "python": ["custom/path/to/script.py"]  # Sobrescreve default_refs
    }
)
```

## Integração com Seed Data

NotebookItemTypes são carregados automaticamente pelo módulo `seed_data.py`:

```python
# backend/app/scripts/seed_data.py

def seed_notebook_item_types():
    """
    Loads NotebookItemType definitions from:
    1. Artefatos/canonicos/notebook_item_types/ (new structured format)
    2. Artefatos/canonicos/tipos_celula/ (legacy format)
    """
    # Load from both directories
    # ...
```

### Idempotência

A função de seed é idempotente:
- Se um tipo com o mesmo `id` já existe, ele é **reutilizado**
- Se não existe, ele é **criado**
- Isso permite re-executar seed sem duplicar dados

## Versionamento de Tipos

Tipos seguem SemVer (Semantic Versioning) no `id`:
- **Major (v1 → v2)**: Mudanças incompatíveis na estrutura
- **Minor**: Novos campos opcionais
- **Patch**: Correções de bugs, metadados

### Exemplo de Versionamento

```
conversation-trace-item (v1 implícito)
conversation-trace-item-v2 (breaking changes)
```

### Migração de Versões

Ao atualizar versão de tipo:
1. Criar novo arquivo com nova versão
2. Manter versão antiga para compatibilidade
3. Atualizar referências no sistema progressivamente
4. Deprecar versão antiga após período de transição

## Propriedades Especiais

### default_refs

Referências a recursos externos:

```json
{
  "default_refs": {
    "workflow_graph": ["backend/app/workflows/my_workflow.yaml"],
    "python": ["backend/app/services/my_service.py"],
    "docs": ["docs/my_type.md"],
    "javascript": ["frontend/components/MyComponent.vue"],
    "yaml": ["config/my_config.yaml"],
    "attachments": []
  }
}
```

### default_initial_data

Dados iniciais aplicados a novas instâncias:

```json
{
  "default_initial_data": {
    "category": "persistida",
    "icon": "mdi-notebook",
    "properties": [
      {
        "name": "title",
        "type": "string",
        "label": "Título",
        "required": true,
        "default": "Nova Célula"
      }
    ],
    "views_components": ["CellView_MyType"],
    "versao": "1.0.0"
  }
}
```

## Tipos Disponíveis

### conversation-trace-item

Tipo para rastreamento estruturado de conversas através do pipeline RAG e LLM.

**Propósito**: Observabilidade e debugging de conversas.

**Propriedades**:
- `conversation_id`: Identificador único da conversa
- `session_id`: ID da sessão
- `tracing_enabled`: Se tracing está ativo
- `user_message`: Mensagem original do usuário
- `target_llm`: LLM alvo (openai, gemini, ollama)

**Categoria**: Efêmera (dados temporários)

**Uso**: Criado automaticamente quando tracing é habilitado em uma conversa.

### book-type-generic-v1

Tipo genérico para livros de conhecimento.

**Propósito**: Organização de células em livros.

**Categoria**: Persistida (dados de longo prazo)

**Uso**: Base para todos os livros no sistema.

## Relacionado

- [../livros/](../livros/) - Livros canônicos que usam estes tipos
- [../tipos_celula/](../tipos_celula/) - Legacy cell types (backward compatibility)
- [Backend Seed Data](../../../backend/app/scripts/seed_data.py) - Script de seed
- [Models](../../../backend/app/models/) - Modelos Pydantic

## Exemplos

### Tipo de Trace de Conversa

Ver `conversation-trace-item.json` para exemplo completo de tipo para tracing.

### Tipo de Livro Genérico

Ver `book-type-generic-v1.json` para exemplo de tipo de livro.

## Notas

- IDs devem ser únicos no sistema
- Use kebab-case para IDs (ex: `my-type-v1`)
- Nomes técnicos em inglês (Rule 4.3 do RULESET)
- Descrições podem ser em português
- Timestamps em formato ISO 8601
- Considere versionamento para mudanças incompatíveis
- Documente o propósito e uso do tipo claramente
- Mantenha arquivos abaixo de 500 linhas (Rule 1.1)
