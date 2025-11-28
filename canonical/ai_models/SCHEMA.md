# Schema: ModeloIA

## 📋 Visão Geral

Este documento define o schema completo de um **Modelo de IA** como artefato canônico no ScareVerse.

## 🎯 Propósito

Modelos de IA são artefatos que representam engines de processamento de linguagem natural disponíveis no sistema, sejam locais (Ollama) ou cloud (Gemini, OpenAI).

## 📊 Schema Pydantic

```python
class TipoModeloIA(str, Enum):
    """Tipo de modelo de IA."""
    LOCAL = "local"  # Ollama local
    CLOUD = "cloud"  # API externa como Gemini
    BYOK = "byok"    # Bring Your Own Key/Model


class ModeloIA(BaseModel):
    """Modelo de IA registrado como artefato."""
    id: str = Field(default_factory=generate_uuid, description="UUID do modelo")
    nome: str = Field(..., description="Nome do modelo (ex: Mistral, Gemini)")
    descricao: str = Field(..., description="Descrição do modelo")
    tipo: TipoModeloIA = Field(..., description="Tipo do modelo (local, cloud, byok)")
    provider: str = Field(..., description="Provider do modelo (ollama, gemini, openai)")
    modeloId: str = Field(..., description="ID do modelo no provider (ex: mistral, gemini-pro)")
    apiKey: Optional[str] = Field(None, description="API Key do modelo (criptografada no armazenamento, descriptografada na leitura)")
    versao: str = Field(default="1.0.0", description="Versão do modelo")
    ativo: bool = Field(default=True, description="Se o modelo está ativo/disponível")
    configuracao: Dict[str, Any] = Field(default_factory=dict, description="Configurações específicas do modelo")
    metadados: Dict[str, Any] = Field(default_factory=dict, description="Metadados adicionais")
    dataCriacao: datetime = Field(default_factory=datetime.utcnow, description="Data de criação")
    dataAtualizacao: datetime = Field(default_factory=datetime.utcnow, description="Data de atualização")
```

## 📝 Campos Detalhados

### `id` (string, obrigatório)
UUID único do modelo no sistema.

**Formato**: UUID v4  
**Exemplo**: `"550e8400-e29b-41d4-a716-446655440000"`  
**Geração**: Automática via `generate_uuid()`

### `nome` (string, obrigatório)
Nome amigável do modelo exibido na interface.

**Exemplos**:
- `"Mistral"`
- `"DeepSeek Code"`
- `"Gemini Pro"`

### `descricao` (string, obrigatório)
Descrição detalhada do modelo, suas capacidades e casos de uso.

**Exemplo**: `"Modelo de propósito geral otimizado para conversação e geração de código"`

### `tipo` (TipoModeloIA, obrigatório)
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
modelo = ModeloIA(
    nome="Gemini Pro",
    provider="gemini",
    modeloId="gemini-pro",
    apiKey="AIzaSy..."  # Será criptografada automaticamente
)
```

### `versao` (string, opcional)
Versão do artefato de modelo (não confundir com versão do modelo LLM).

**Padrão**: `"1.0.0"`  
**Formato**: Semantic Versioning

### `ativo` (boolean, opcional)
Se o modelo está disponível para uso.

**Padrão**: `true`  
**Uso**: Permite desativar modelos sem deletá-los

### `configuracao` (object, opcional)
Configurações específicas do modelo para inferência.

**Campos comuns**:
```json
{
  "temperatura": 0.7,
  "maxTokens": 2048,
  "topP": 0.95,
  "timeout": 30
}
```

### `metadados` (object, opcional)
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

### `dataCriacao` (datetime, automático)
Timestamp de quando o modelo foi registrado.

**Formato**: ISO 8601  
**Geração**: Automática

### `dataAtualizacao` (datetime, automático)
Timestamp da última atualização.

**Formato**: ISO 8601  
**Geração**: Automática em updates

## 📄 Exemplos JSON

### Mistral (Ollama Local)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "nome": "Mistral",
  "descricao": "Modelo de propósito geral equilibrado entre velocidade e qualidade",
  "tipo": "local",
  "provider": "ollama",
  "modeloId": "mistral",
  "versao": "1.0.0",
  "ativo": true,
  "configuracao": {
    "temperatura": 0.7,
    "maxTokens": 2048,
    "timeout": 30
  },
  "metadados": {
    "parametros": "7B",
    "contexto": "8K tokens",
    "arquitetura": "Transformer",
    "especialidade": "Conversação geral"
  },
  "dataCriacao": "2024-11-03T00:00:00Z",
  "dataAtualizacao": "2024-11-03T00:00:00Z"
}
```

### DeepSeek (Ollama Local)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "nome": "DeepSeek Code",
  "descricao": "Modelo especializado em código e tarefas técnicas",
  "tipo": "local",
  "provider": "ollama",
  "modeloId": "deepseek-coder",
  "versao": "1.0.0",
  "ativo": true,
  "configuracao": {
    "temperatura": 0.5,
    "maxTokens": 4096,
    "timeout": 30
  },
  "metadados": {
    "parametros": "6.7B",
    "contexto": "16K tokens",
    "arquitetura": "Transformer",
    "especialidade": "Código e desenvolvimento"
  },
  "dataCriacao": "2024-11-03T00:00:00Z",
  "dataAtualizacao": "2024-11-03T00:00:00Z"
}
```

### Phi (Ollama Local)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "nome": "Phi",
  "descricao": "Modelo compacto e rápido, ideal para tarefas simples",
  "tipo": "local",
  "provider": "ollama",
  "modeloId": "phi",
  "versao": "1.0.0",
  "ativo": true,
  "configuracao": {
    "temperatura": 0.8,
    "maxTokens": 2048,
    "timeout": 20
  },
  "metadados": {
    "parametros": "2.7B",
    "contexto": "4K tokens",
    "arquitetura": "Transformer",
    "especialidade": "Tarefas rápidas"
  },
  "dataCriacao": "2024-11-03T00:00:00Z",
  "dataAtualizacao": "2024-11-03T00:00:00Z"
}
```

### Gemini (Google Cloud)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440004",
  "nome": "Gemini Pro",
  "descricao": "Modelo cloud de última geração do Google",
  "tipo": "cloud",
  "provider": "gemini",
  "modeloId": "gemini-pro",
  "versao": "1.0.0",
  "ativo": true,
  "configuracao": {
    "temperatura": 0.7,
    "maxTokens": 2048,
    "timeout": 30,
    "requiresApiKey": true
  },
  "metadados": {
    "contexto": "32K tokens",
    "multimodal": false,
    "especialidade": "Conversação avançada"
  },
  "dataCriacao": "2024-11-03T00:00:00Z",
  "dataAtualizacao": "2024-11-03T00:00:00Z"
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
