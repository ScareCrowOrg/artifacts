---
processed: true
processed_date: 2025-12-09
themes:
  - api
  - ai-models
  - integration
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Modelos IA - API Documentation

## Visão Geral

O módulo de Modelos IA (`/api/modelos-ia`) fornece endpoints CRUD para gerenciar modelos de IA como artefatos no sistema ScareVerse. Os modelos podem ser locais (Ollama), cloud (Gemini, OpenAI) ou BYOK (Bring Your Own Key).

## Campos do Modelo

- **id**: UUID do modelo.
- **nome**: Nome do modelo (ex: Mistral, Gemini).
- **descricao**: Descrição do modelo.
- **tipo**: Tipo de execução do modelo (`cloud`, `local`, `byok`, etc).
- **provider**: Provider do modelo, restrito ao Enum `ProviderModeloIA` (`openai`, `gemini`, `ollama`, `groq`).
- **modeloId**: ID do modelo no provider (ex: mistral, gemini-pro).
- **apiKey**: API Key do modelo (criptografada no armazenamento).
- **versao**: Versão do modelo.
- **ativo**: Se o modelo está ativo/disponível.
- **configuracao**: Configurações específicas do modelo.
- **metadados**: Metadados adicionais.
- **dataCriacao**: Data de criação.
- **dataAtualizacao**: Data de atualização.

## Endpoints

### `GET /modelos-ia/listar`

Lista todos os modelos de IA ativos disponíveis.

**Autenticação**: Não requerida (para popular dropdown no frontend antes do login)

**Response**: Array de `ModeloIA`

```json
[
  {
    "id": "uuid",
    "nome": "Gemini",
    "descricao": "Modelo Gemini cloud",
    "tipo": "cloud",
    "provider": "gemini",
    "modeloId": "gemini-pro",
    "apiKey": null,
    "versao": "1.0.0",
    "ativo": true,
    "configuracao": {},
    "metadados": {},
    "dataCriacao": "2025-11-14T18:40:00.992Z",
    "dataAtualizacao": "2025-11-14T18:40:00.992Z"
  }
]
```

---

### `GET /modelos-ia/{id}`

Obtém detalhes de um modelo específico.

**Autenticação**: Não requerida

**Response**: `ModeloIA`

---

### `POST /modelos-ia/criar`

Cria um novo modelo de IA.

**Autenticação**: Requerida

**Request Body**: `CriarModeloIARequest`

```json
{
  "nome": "GPT-4",
  "descricao": "Modelo OpenAI cloud",
  "tipo": "cloud",
  "provider": "openai",
  "modeloId": "gpt-4",
  "apiKey": "********",
  "versao": "1.0.0",
  "ativo": true,
  "configuracao": {},
  "metadados": {}
}
```

**Response**: `ModeloIA` (código 201)

---

### `PUT /modelos-ia/{id}/atualizar`

Atualiza um modelo de IA existente.

**Autenticação**: Requerida

**URL Parameter**: 
- `id` (string) - UUID do modelo

**Request Body**: `AtualizarModeloIARequest`

```json
{
  "nome": "Gemini",
  "descricao": "Modelo Gemini cloud",
  "tipo": "cloud",
  "provider": "gemini",
  "modeloId": "gemini-pro",
  "apiKey": null,
  "versao": "1.0.1",
  "ativo": true,
  "configuracao": {},
  "metadados": {}
}
```

#### Compatibilidade com Frontend

O endpoint é **compatível com payloads que incluem o campo `id` no body**. Este comportamento garante integração transparente com o frontend, que envia o objeto completo do modelo.

---

## Enum ProviderModeloIA

```python
from enum import Enum

class ProviderModeloIA(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    GROQ = "groq"
```

---

## Observações

- O campo `tipo` é livre e indica o modo de execução (`cloud`, `local`, `byok`, etc).
- O campo `provider` é restrito ao Enum `ProviderModeloIA`.
- Para alterações futuras, ajuste apenas o Enum para adicionar/remover providers suportados.