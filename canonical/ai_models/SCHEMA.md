# Schema: ModeloIA

## 📋 Visão Geral

Este documento define o schema completo de um **Modelo de IA** como artefato canônico no ScareVerse.

## 🎯 Propósito

Modelos de IA são artefatos que representam engines de processamento de linguagem natural disponíveis no sistema, sejam locais (Ollama) ou cloud (Gemini, OpenAI).

## 📊 Schema Pydantic

```python
class AIModelProvider(str, Enum):
    """AI model provider."""
    OLLAMA = "ollama"  # Local Ollama
    GEMINI = "gemini"  # Google Gemini API
    OPENAI = "openai"  # OpenAI API
    GROQ = "groq"      # Groq API


class AIModel(BaseModel):
    """AI model registered as artifact."""
    id: str = Field(default_factory=generate_uuid, description="Model UUID")
    name: str = Field(..., description="Model name (e.g., Mistral, Gemini)")
    description: str = Field(..., description="Model description")
    type: str = Field(..., description="Model type (cloud, local, byok, etc)")
    provider: AIModelProvider = Field(..., description="Model provider (openai, gemini, ollama, groq)")
    modelId: str = Field(..., description="Model ID in provider (e.g., mistral, gemini-pro)")
    apiKey: Optional[str] = Field(None, description="Model API Key (encrypted in storage, decrypted on read)")
    version: str = Field(default="1.0.0", description="Model version")
    active: bool = Field(default=True, description="Whether the model is active/available")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Model-specific configurations")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    createdAt: datetime = Field(default_factory=datetime.utcnow, description="Creation date")
    updatedAt: datetime = Field(default_factory=datetime.utcnow, description="Update date")
```

## 📝 Campos Detalhados

### `id` (string, obrigatório)
UUID único do modelo no sistema.

**Formato**: UUID v4  
**Exemplo**: `"550e8400-e29b-41d4-a716-446655440000"`  
**Geração**: Automática via `generate_uuid()`

### `name` (string, obrigatório)
Nome amigável do modelo exibido na interface.

**Exemplos**:
- `"Mistral"`
- `"DeepSeek Code"`
- `"Gemini Pro"`

### `description` (string, obrigatório)
Descrição detalhada do modelo, suas capacidades e casos de uso.

**Exemplo**: `"Modelo de propósito geral otimizado para conversação e geração de código"`

### `type` (string, obrigatório)
Tipo de deployment do modelo.

**Valores**:
- `"local"` - Executado localmente via Ollama
- `"cloud"` - API externa (Gemini, OpenAI)
- `"byok"` - Bring Your Own Key/Model (usuário configura)

### `provider` (string, obrigatório)
Provedor/plataforma que serve o modelo.

**Valores suportados**:
- `"ollama"` - Ollama local
- `"gemini"` - Google Gemini
- `"openai"` - OpenAI (futuro)

### `modeloId` (string, obrigatório)
Identificador do modelo no provider.

**Exemplos**:
- Ollama: `"mistral"`, `"deepseek-coder"`, `"phi"`
- Gemini: `"gemini-pro"`, `"gemini-pro-vision"`

### `apiKey` (string, opcional)
API Key específica do modelo para autenticação.

**Segurança**:
- Sempre criptografada usando Fernet (AES-128-CBC + HMAC) antes de salvar nos arquivos JSON
- Automaticamente descriptografada ao ler o modelo da base de dados
- Nunca exposta em texto puro nos arquivos JSON
- Requer `ENCRYPTION_KEY` configurada no `.env`

**Uso**:
- Para modelos cloud (Gemini, OpenAI): API key específica do modelo tem prioridade sobre a chave global do `.env`
- Para modelos locais (Ollama): geralmente não necessário (pode ser `null`)

**Exemplo de uso no Gemini**:
```python
model = AIModel(
    name="Gemini Pro",
    provider="gemini",
    modelId="gemini-pro",
    apiKey="AIzaSy..."  # Será criptografada automaticamente
)
```

### `version` (string, opcional)
Versão do artefato de modelo (não confundir com versão do modelo LLM).

**Padrão**: `"1.0.0"`  
**Formato**: Semantic Versioning

### `active` (boolean, opcional)
Se o modelo está disponível para uso.

**Padrão**: `true`  
**Uso**: Permite desativar modelos sem deletá-los

### `configuration` (object, opcional)
Configurações específicas do modelo para inferência.

**Campos comuns**:
```json
{
  "temperature": 0.7,
  "max_tokens": 2048,
  "topP": 0.95,
  "timeout": 30
}
```

### `metadata` (object, opcional)
Metadados adicionais sobre o modelo.

**Campos comuns**:
```json
{
  "parametros": "7B",
  "contexto": "8K tokens",
  "arquitetura": "Transformer",
  "linguagens": ["pt", "en", "es"]
}
```

### `createdAt` (datetime, automático)
Timestamp de quando o modelo foi registrado.

**Formato**: ISO 8601  
**Geração**: Automática

### `updatedAt` (datetime, automático)
Timestamp da última atualização.

**Formato**: ISO 8601  
**Geração**: Automática em updates

## 📄 Exemplos JSON

### Mistral (Ollama Local)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "name": "Mistral",
  "description": "Modelo de propósito geral equilibrado entre velocidade e qualidade",
  "type": "local",
  "provider": "ollama",
  "modelId": "mistral",
  "version": "1.0.0",
  "active": true,
  "configuration": {
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 30
  },
  "metadata": {
    "parametros": "7B",
    "contexto": "8K tokens",
    "arquitetura": "Transformer",
    "especialidade": "Conversação geral"
  },
  "createdAt": "2024-11-03T00:00:00Z",
  "updatedAt": "2024-11-03T00:00:00Z"
}
```

### DeepSeek (Ollama Local)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "name": "DeepSeek Code",
  "description": "Modelo especializado em código e tarefas técnicas",
  "type": "local",
  "provider": "ollama",
  "modelId": "deepseek-coder",
  "version": "1.0.0",
  "active": true,
  "configuration": {
    "temperature": 0.5,
    "max_tokens": 4096,
    "timeout": 30
  },
  "metadata": {
    "parametros": "6.7B",
    "contexto": "16K tokens",
    "arquitetura": "Transformer",
    "especialidade": "Código e desenvolvimento"
  },
  "createdAt": "2024-11-03T00:00:00Z",
  "updatedAt": "2024-11-03T00:00:00Z"
}
```

### Phi (Ollama Local)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "name": "Phi",
  "description": "Modelo compacto e rápido, ideal para tarefas simples",
  "type": "local",
  "provider": "ollama",
  "modelId": "phi",
  "version": "1.0.0",
  "active": true,
  "configuration": {
    "temperature": 0.8,
    "max_tokens": 2048,
    "timeout": 20
  },
  "metadata": {
    "parametros": "2.7B",
    "contexto": "4K tokens",
    "arquitetura": "Transformer",
    "especialidade": "Tarefas rápidas"
  },
  "createdAt": "2024-11-03T00:00:00Z",
  "updatedAt": "2024-11-03T00:00:00Z"
}
```

### Gemini (Google Cloud)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440004",
  "name": "Gemini Pro",
  "description": "Modelo cloud de última geração do Google",
  "type": "cloud",
  "provider": "gemini",
  "modelId": "gemini-pro",
  "version": "1.0.0",
  "active": true,
  "configuration": {
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 30,
    "requiresApiKey": true
  },
  "metadata": {
    "contexto": "32K tokens",
    "multimodal": false,
    "especialidade": "Conversação avançada"
  },
  "createdAt": "2024-11-03T00:00:00Z",
  "updatedAt": "2024-11-03T00:00:00Z"
}
```

## 🔄 Ciclo de Vida

### Criação
```
POST /api/modelos-ia/criar
{
  "nome": "Novo Modelo",
  "descricao": "...",
  "tipo": "local",
  "provider": "ollama",
  "modeloId": "novo-modelo"
}
```

### Consulta
```
GET /api/modelos-ia/listar
GET /api/modelos-ia/{id}
```

### Atualização
```
PUT /api/modelos-ia/{id}/atualizar
{
  "descricao": "Nova descrição",
  "ativo": false
}
```

### Ativação/Desativação
```
POST /api/modelos-ia/{id}/ativar
{
  "ativo": true
}
```

## 🔗 Referências

- [Backend Models](../../../backend/app/models.py) - Implementação Pydantic
- [MVP Router](../../../backend/app/mvp_router.py) - Endpoints REST
- [Seed Data](../../../backend/app/seed_data.py) - Dados iniciais

---

**Última Atualização**: Novembro 2024  
**Versão**: 1.0 (Implementação inicial)
