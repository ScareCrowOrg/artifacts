# Modelos de IA - Artefatos Canônicos

## 📋 Visão Geral

Este diretório contém os **artefatos canônicos** dos modelos de IA disponíveis no ScareVerse. Cada modelo é registrado como um artefato, facilitando curadoria, integração e governança.

## 🎯 Objetivo

Permitir o gerenciamento centralizado de modelos de IA como artefatos, incluindo:
- Cadastro e edição de modelos
- Ativação/desativação
- Versionamento
- Metadados completos
- Configurações específicas por modelo

## 📁 Estrutura

```
modelos_ia/
├── README.md                                        # Este arquivo
├── SCHEMA.md                                        # Schema detalhado do ModeloIA
├── 68221e1e-f9b1-4157-9b5b-2fdcdf81afc2.json       # Modelo Mistral (Ollama)
├── 918410bc-ad22-4c2b-b4b6-aa175a96b22f.json       # Modelo DeepSeek Code (Ollama)
├── c5564f01-5a48-4fac-9e24-e7765a51df57.json       # Modelo Phi (Ollama)
├── 425c6960-5e4f-4b2f-87a5-9d3b5542713f.json       # Modelo gemini-2.5-flash (Google Cloud)
├── bf42960f-2297-487b-9477-f8d71bc9989b.json       # Modelo GPT-3.5 Turbo (OpenAI)
└── e866b850-0610-444d-b933-9f6bb7fb5e34.json       # Modelo GPT-4o (OpenAI)
```

## 🔧 Tipos de Modelos

### Local (Ollama)
Modelos executados localmente via Ollama. Não requerem API keys externas.

**Exemplos**: Mistral, DeepSeek Code, Phi

**Características**:
- Privacidade total
- Sem custos por chamada
- Requer recursos locais (GPU/CPU)

### Cloud (API Externa)
Modelos acessados via API de provedores externos.

**Exemplos**: Google Gemini, OpenAI GPT-3.5, OpenAI GPT-4o

**Características**:
- Escalabilidade
- Modelos de última geração
- Requer API key

### BYOK (Bring Your Own Key/Model)
Modelos configuráveis pelo usuário com suas próprias credenciais.

**Exemplos**: Gemini com chave personalizada, GPT-3.5 Turbo, GPT-4o

**Características**:
- Configuração individual por usuário
- Segurança de credenciais
- Flexibilidade total

## 📊 Schema do Modelo

Cada modelo IA é definido com:

```json
{
  "id": "uuid",
  "nome": "Nome do Modelo",
  "descricao": "Descrição detalhada",
  "tipo": "local|cloud|byok",
  "provider": "ollama|gemini|openai",
  "modeloId": "id-no-provider",
  "apiKey": "gAAAAABhN...",  // Criptografado automaticamente (opcional)
  "versao": "1.0.0",
  "ativo": true,
  "configuracao": {
    "temperatura": 0.7,
    "maxTokens": 2048
  },
  "metadados": {
    "parametros": "7B",
    "contexto": "8K tokens"
  }
}
```

Veja [SCHEMA.md](./SCHEMA.md) para detalhes completos.

## 🚀 Uso no Sistema

### Backend
Os modelos são carregados na inicialização e disponibilizados via:
- `GET /api/modelos-ia/listar` - Lista modelos ativos
- `POST /api/modelos-ia/criar` - Cria novo modelo
- `PUT /api/modelos-ia/{id}/atualizar` - Atualiza modelo
- `POST /api/modelos-ia/{id}/ativar` - Ativa/desativa modelo

### Frontend
O componente **ChatIA** busca dinamicamente os modelos disponíveis:

```javascript
// Busca modelos do backend
const response = await fetch('/api/modelos-ia/listar')
const modelos = await response.json()

// Renderiza dropdown dinamicamente
<select v-model="selectedModel">
  <option v-for="modelo in modelos" :value="modelo.modeloId">
    {{ modelo.nome }}
  </option>
</select>
```

## 🔐 Segurança

### Criptografia de API Keys

**Desde Novembro 2024**, o campo `apiKey` dos modelos é automaticamente criptografado:

✅ **Criptografia Automática**:
- Algoritmo: Fernet (AES-128-CBC + HMAC)
- Ativada automaticamente ao salvar modelos
- Transparente para o usuário

✅ **Armazenamento Seguro**:
- API keys NUNCA são salvas em texto puro nos arquivos JSON
- Criptografadas antes de salvar no disco
- Descriptografadas apenas na memória durante a leitura

✅ **Uso no Gemini**:
- API key específica do modelo tem prioridade sobre `GEMINI_API_KEY` global
- Permite múltiplos modelos Gemini com diferentes chaves
- Suporte BYOK (Bring Your Own Key)

### Configuração

Adicione a chave de criptografia no `.env`:

```bash
# Gere uma chave Fernet
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Adicione ao .env
ENCRYPTION_KEY=sua-chave-gerada-aqui
```

⚠️ **IMPORTANTE**: Nunca commite `ENCRYPTION_KEY` no repositório!

### Documentação Adicional

- [README_CRYPTO.md](../../../backend/app/README_CRYPTO.md) - Guia completo de criptografia
- [crypto_utils.py](../../../backend/app/crypto_utils.py) - Implementação

## 📖 Modelos Implementados

### Mistral (Ollama)
Modelo local de propósito geral, equilibrado entre velocidade e qualidade.

**Arquivo**: `68221e1e-f9b1-4157-9b5b-2fdcdf81afc2.json`  
**Provider**: Ollama  
**Tipo**: Local  
**Características**: 7B parâmetros, contexto de 8K tokens

### DeepSeek Code (Ollama)
Modelo especializado em código e tarefas técnicas. Otimizado para geração, análise e refatoração de código.

**Arquivo**: `918410bc-ad22-4c2b-b4b6-aa175a96b22f.json`  
**Provider**: Ollama  
**Tipo**: Local  
**Características**: 6.7B parâmetros, contexto de 16K tokens

### Phi (Ollama)
Modelo compacto e rápido da Microsoft, ideal para tarefas simples e respostas rápidas com menor consumo de recursos.

**Arquivo**: `c5564f01-5a48-4fac-9e24-e7765a51df57.json`  
**Provider**: Ollama  
**Tipo**: Local  
**Características**: 2.7B parâmetros, contexto de 4K tokens

### gemini-2.5-flash (Google Cloud)
Modelo cloud de última geração do Google.

**Arquivo**: `425c6960-5e4f-4b2f-87a5-9d3b5542713f.json`  
**Provider**: Google Gemini  
**Tipo**: Cloud / BYOK  
**Características**: Contexto de 32K tokens, suporte multimodal

### GPT-3.5 Turbo (OpenAI)
Modelo rápido e eficiente da OpenAI. Suporta BYOK (Bring Your Own Key) para configuração individual por usuário.

**Arquivo**: `bf42960f-2297-487b-9477-f8d71bc9989b.json`  
**Provider**: OpenAI  
**Tipo**: Cloud / BYOK  
**Características**: Contexto de 16K tokens, conversação rápida e eficiente

### GPT-4o (OpenAI)
Modelo multimodal avançado da OpenAI. Suporta BYOK (Bring Your Own Key) para configuração individual por usuário.

**Arquivo**: `e866b850-0610-444d-b933-9f6bb7fb5e34.json`  
**Provider**: OpenAI  
**Tipo**: Cloud / BYOK  
**Características**: Contexto de 128K tokens, suporte multimodal avançado

## 🔗 Integração com Backend

Os modelos são carregados em `backend/app/seed_data.py` e persistidos em MongoDB na collection `modelos_ia`.

**Modelo Pydantic**: `backend/app/models.py::ModeloIA`

## 📝 Adicionando Novos Modelos

1. Crie arquivo JSON com schema correto
2. Adicione seed data em `backend/app/seed_data.py`
3. Configure provider específico se necessário
4. Atualize este README

## 🔗 Links Úteis

- [Backend Models](../../../backend/app/models.py) - Schema ModeloIA
- [Seed Data](../../../backend/app/seed_data.py) - Inicialização dos modelos
- [ChatIA Component](../../../cockpit-vue/src/components/ChatIA.vue) - Uso no frontend

---

**Última Atualização**: 15 de Novembro de 2024  
**Versão**: 1.1 (Adicionados modelos OpenAI GPT-3.5 Turbo e GPT-4o)
