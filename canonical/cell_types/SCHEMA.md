# Schema: TipoCelula (LEGACY Format)

## ⚠️ LEGACY NOTICE

**This schema describes the OLD TipoCelula format, which is DEPRECATED.**

For the **current schema**, see: **[../notebook_item_types/README.md](../notebook_item_types/README.md)**

### Migration

The `TipoCelula` model has been replaced by `NotebookItemType`. Key changes:

| TipoCelula Field | NotebookItemType Field | Type | Notes |
|------------------|------------------------|------|-------|
| `name` | `name` | string | ✅ Unchanged |
| `descricao` | `description` | string | 🔄 Renamed |
| `docs_refs` | `default_refs["docs"]` | List[str] | 🔄 Grouped in default_refs |
| `python_refs` | `default_refs["python"]` | List[str] | 🔄 Grouped in default_refs |
| `javascript_refs` | `default_refs["javascript"]` | List[str] | 🔄 Grouped in default_refs |
| `yaml_refs` | `default_refs["yaml"]` | List[str] | 🔄 Grouped in default_refs |
| `views_components` | `default_refs["views_components"]` | List[str] | 🔄 Grouped in default_refs |
| `workflows` | `default_refs["workflow_graph"]` | List[str] | 🔄 Restructured |
| `properties` | `default_initial_data` (schema) | Dict | 🔄 Restructured |
| *(not present)* | `allow_instance_override_refs` | bool | 🆕 New field |

For full NotebookItemType schema, see: **[../notebook_item_types/README.md](../notebook_item_types/README.md)**

---

## 📋 Visão Geral (LEGACY Documentation)

Este documento define o schema completo para **Tipos de Célula (LEGACY)** - artefatos canônicos que serviam como templates para células instanciadas no formato TipoCelula.

## 🔧 Schema Pydantic

```python
# backend/app/models.py
from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field

class TipoCelula(BaseModel):
    id: str = Field(..., description="Identificador único (UUID) do tipo de célula.")
    name: str = Field(..., description="Nome curto e legível do tipo de célula para exibição na UI.")
    description: str = Field(..., alias="descricao", description="Descrição detalhada do que este tipo de célula faz. Exibida ao usuário na seleção de tipos.")
    category: Literal["persistida", "efemera"] = Field(..., description="Define a categoria de persistência da célula: 'persistida' para armazenamento no JSONDatabase, 'efemera' para células temporárias (ex: editor de arquivo).")
    icon: Optional[str] = Field(None, description="Nome de um ícone (e.g., MDI icon name) para representação visual na UI.")
    properties: List[Dict[str, Any]] = Field(default_factory=list, description="Lista de definições de propriedades dinâmicas que as instâncias deste tipo de célula podem conter em seu campo 'data'. Cada dicionário define 'name', 'type', 'label', 'required', 'default'.")
    docs_refs: List[str] = Field(default_factory=list, description="Lista de referências (caminhos/IDs) a documentos Markdown ou outros arquivos de documentação associados ao Tipo de Célula.")
    python_refs: List[str] = Field(default_factory=list, description="Lista de referências (caminhos/IDs) a arquivos de script Python associados ao Tipo de Célula.")
    javascript_refs: List[str] = Field(default_factory=list, description="Lista de referências (caminhos/IDs) a arquivos de script JavaScript associados ao Tipo de Célula.")
    yaml_refs: List[str] = Field(default_factory=list, description="Lista de referências (caminhos/IDs) a arquivos YAML de configuração associados ao Tipo de Célula.")
    attachment_refs: List[str] = Field(default_factory=list, description="Lista de referências (caminhos/IDs) a outros arquivos anexos genéricos associados ao Tipo de Célula.")
    views_components: List[str] = Field(default_factory=list, description="Lista de nomes de componentes Vue (strings) que compõem a interface deste Tipo de Célula na UI.")
    workflows: Optional[str] = Field(None, description="Workflow em formato YAML definindo sequência de execução ou orquestração.")
    versao: str = Field(..., description="Versão semântica do tipo (ex: '1.0.0').")
```

## 📝 Campos Detalhados

### `id` (string, obrigatório)
- **Tipo**: String UUID
- **Formato**: UUID v4 lowercase
- **Obrigatório**: Sim
- **Único**: Sim
- **Geração**: `uuidgen | tr '[:upper:]' '[:lower:]'`
- **Exemplo**: `"unclassified"` (para tipos fixos) ou `"45666a57-b1a2-486c-91ac-c8ea2ab5649b"` (para tipos dinâmicos)
- **Descrição**: Identificador único do tipo de célula.

### `name` (string, obrigatório)
- **Tipo**: String
- **Obrigatório**: Sim
- **Min Length**: 3
- **Max Length**: 100
- **Exemplo**: `"Célula Não Classificada"`
- **Descrição**: Nome curto e legível do tipo de célula, para exibição na UI.

### `description` (string, obrigatório)
- **Tipo**: String
- **Obrigatório**: Sim
- **Min Length**: 3
- **Max Length**: 500
- **Exemplo**: `"Um tipo de célula genérico e persistido..."`
- **Descrição**: Descrição detalhada do que este tipo de célula faz. (Corresponde ao campo `descricao` no modelo Pydantic).

### `category` (string, obrigatório)
- **Tipo**: String
- **Obrigatório**: Sim
- **Valores Permitidos**: `"persistida"`, `"efemera"`
- **Exemplo**: `"persistida"`
- **Descrição**: Define a categoria de persistência da célula. `persistida` para armazenamento no `JSONDatabase`, `efemera` para células temporárias (ex: editor de arquivo).

### `icon` (string, opcional)
- **Tipo**: String (Nome MDI)
- **Obrigatório**: Não
- **Exemplo**: `"mdi-text-box"`
- **Descrição**: Nome de um ícone (e.g., MDI icon name) para representação visual na UI.

### `properties` (array de objetos, obrigatório)
- **Tipo**: Array de objetos
- **Obrigatório**: Sim
- **Default**: `[]`
- **Campos de cada objeto**:
  - `name` (string, obrig obrigatório): Nome da propriedade (e.g., "title", "content").
  - `type` (string, obrigatório): Tipo de dado (e.g., "string", "text", "number", "boolean", "code").
  - `label` (string, obrigatório): Label para exibição na UI.
  - `required` (boolean, obrigatório): Se a propriedade é obrigatória.
  - `default` (any, opcional): Valor padrão da propriedade.
- **Descrição**: Lista de definições de propriedades dinâmicas que as instâncias deste tipo de célula podem conter em seu campo `data`.

#### Exemplo de `properties`
```json
{
  "properties": [
    {
      "name": "title",
      "type": "string",
      "label": "Título da Célula",
      "required": true,
      "default": "Nova Célula Sem Título"
    },
    {
      "name": "content",
      "type": "text",
      "label": "Conteúdo da Célula",
      "required": false,
      "default": ""
    }
  ]
}
```

### `docs_refs` (array de strings, obrigatório)
- **Tipo**: Array de strings
- **Obrigatório**: Sim
- **Default**: `[]`
- **Exemplo**: `["docs/unclassified_usage.md", "docs/example.md"]`
- **Descrição**: Lista de referências (caminhos/IDs) a documentos Markdown ou outros arquivos de documentação associados ao Tipo de Célula.

### `python_refs` (array de strings, obrigatório)
- **Tipo**: Array de strings
- **Obrigatório**: Sim
- **Default**: `[]`
- **Exemplo**: `["scripts/unclassified_handler.py", "scripts/common_utils.py"]`
- **Descrição**: Lista de referências (caminhos/IDs) a arquivos de script Python associados ao Tipo de Célula.

### `javascript_refs` (array de strings, obrigatório)
- **Tipo**: Array de strings
- **Obrigatório**: Sim
- **Default**: `[]`
- **Exemplo**: `["scripts/frontend_logic.js"]`
- **Descrição**: Lista de referências (caminhos/IDs) a arquivos de script JavaScript associados ao Tipo de Célula.

### `yaml_refs` (array de strings, obrigatório)
- **Tipo**: Array de strings
- **Obrigatório**: Sim
- **Default**: `[]`
- **Exemplo**: `["config/celula_settings.yaml"]`
- **Descrição**: Lista de referências (caminhos/IDs) a arquivos YAML de configuração associados ao Tipo de Célula.

### `attachment_refs` (array de strings, obrigatório)
- **Tipo**: Array de strings
- **Obrigatório**: Sim
- **Default**: `[]`
- **Exemplo**: `["assets/image.png", "data/template.txt"]`
- **Descrição**: Lista de referências (caminhos/IDs) a outros arquivos anexos genéricos (imagens, templates, etc.) associados ao Tipo de Célula.

### `views_components` (array de strings, obrigatório)
- **Tipo**: Array de strings
- **Obrigatório**: Sim
- **Default**: `[]`
- **Exemplo**: `["CellView_Unclassified", "CellView_DetailsPanel"]`
- **Descrição**: Lista de nomes de componentes Vue (strings) que compõem a interface deste Tipo de Célula na UI. O frontend usa esses nomes para carregar dinamicamente os componentes correspondentes.

### `workflows` (string, opcional)
- **Tipo**: String (YAML)
- **Obrigatório**: Não
- **Exemplo**:
  ```yaml
  steps:
    - name: "Validar entrada"
      action: "run_python_ref"
      ref: "validation_script.py"
    - name: "Processar dados"
      action: "call_external_api"
      endpoint: "/api/process"
  ```
- **Descrição**: Workflow em formato YAML definindo sequência de execução, orquestração de ações ou lógica de automação para a célula.

### `versao` (string, obrigatório)
- **Tipo**: String
- **Obrigatório**: Sim
- **Formato**: SemVer (e.g., "1.0.0", "0.5.2")
- **Exemplo**: `"1.0.0"`
- **Descrição**: Versão semântica do tipo de célula, útil para controle de compatibilidade e evolução.

## 📊 Exemplo de `TipoCelula` Completo (JSON)

```json
{
  "id": "file_editor",
  "name": "Editor de Arquivo",
  "description": "Uma célula efêmera que permite editar diretamente arquivos do repositório. Não é persistida no sistema de células, mas interage com o sistema de arquivos.",
  "category": "efemera",
  "icon": "mdi-file-edit",
  "properties": [
    {
      "name": "fileName",
      "type": "string",
      "label": "Nome do Arquivo",
      "required": true
    },
    {
      "name": "filePath",
      "type": "string",
      "label": "Caminho do Arquivo",
      "required": true
    }
  ],
  "docs_refs": [],
  "python_refs": [],
  "javascript_refs": [],
  "yaml_refs": [],
  "attachment_refs": [],
  "views_components": ["CellView_FileEditor"],
  "workflows": "",
  "versao": "1.0.0"
}