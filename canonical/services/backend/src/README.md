---
processed: true
processed_date: 2025-12-08
themes:
  - backend
  - api
  - fastapi
  - architecture
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# ScareVerse - Backend API

Backend FastAPI do ScareVerse, fornecendo API REST completa para gerenciamento de artefatos, autenticação, persistência e integração com modelos de IA.

> 📖 **Documentação Completa**: [backend/docs/](./docs/)  
> 📁 **Diretrizes de Caminhos de Arquivos**: [BASE_DIR Guidelines](./docs/BASE_DIR_GUIDELINES.md)

## 📋 Índice

### Arquivos Principais
- `README.md` - Este arquivo (visão geral e quick start)
- `pyproject.toml` - Configuração do projeto Poetry
- `requirements.txt` - Dependências Python
- `pytest.ini` - Configuração de testes
- `start.sh` - Script de inicialização

### Diretórios
- [app/](./app/) - Código-fonte principal da aplicação
  - [core/](./app/core/) - Configurações e dependências principais
  - [database/](./app/database/) - Conexão e configuração MongoDB
  - [file_processors/](./app/file_processors/) - Processadores de arquivos para RAG
  - [models/](./app/models/) - Modelos Pydantic (schemas de dados)
  - [orchestrator/](./app/orchestrator/) - Orquestrador LangGraph
  - [routers/](./app/routers/) - Endpoints FastAPI
  - [scripts/](./app/scripts/) - Scripts utilitários
  - [services/](./app/services/) - Lógica de negócio e integrações
  - [utils/](./app/utils/) - Funções utilitárias
  - [workflows/](./app/workflows/) - Workflows de processamento
- [docs/](./docs/) - Documentação detalhada
  - [api/](./docs/api/) - Documentação de APIs
  - [auth/](./docs/auth/) - Documentação de autenticação
  - [chat-ia/](./docs/chat-ia/) - Documentação do Chat IA
  - [CHROMADB_TELEMETRY.md](./docs/CHROMADB_TELEMETRY.md) - Guia de configuração de telemetria ChromaDB
- [scripts/](./scripts/) - Scripts de teste e validação

## 🎯 Funcionalidades Implementadas

### Autenticação e Segurança
- **Google OAuth2**: Autenticação via Google com JWT tokens ([docs/auth/](./docs/auth/))
- **RBAC Security Lockdown v2**: Enterprise-grade role-based access control
  - Token Revocation: < 1 second logout (Redis-based blacklist)
  - User Caching: High-performance cache with active invalidation
  - User-Level RBAC: Collection + operation permissions
  - Protected Fields: Admin-only modification enforcement
  - Audit Logging: Complete security event tracking
  - **Documentation**: [RBAC Lockdown v2](../docs/official/backend/security/rbac-lockdown-v2.md)
- **Gestão de Sessões**: Isolamento de dados por usuário e sessão
- **Endpoints Protegidos**: Validação automática de tokens
- **CORS**: Configurado para acesso seguro do frontend

### APIs REST (FastAPI)

#### Routers Disponíveis
- **auth_router** (`/api/auth/...`) - Authentication, OAuth2 callbacks and status
- **books_router** (`/api/books/...`) - CRUD for books (master and volatile)
- **layout_books_router** (`/api/layout-books/...`) - Layout Books for workspace configuration management
- **cells_router** (`/api/cells/...`) - CRUD and execution for cells
- **chat_router** (`/api/chat/...`) - AI-powered intention processing
- **config_router** (`/api/config/...`) - System configuration
- **file_ops_router** (`/api/...`) - File operations (save, list, load, move)
- **issues_router** (`/api/issues/...`) - Issue management
- **issues_dashboard_router** (`/api/issues/dashboard/...`) - Issues dashboard
- **ai_models_router** (`/api/ai-models/...`) - AI models CRUD
- **ngrok_router** (`/api/share/...`) - Temporary sharing via ngrok
- **router** (`/api/...`) - General endpoints (health, tree, persist)
- **services_router** (`/api/services/...`) - External services management
- **sessions_router** (`/api/sessions/...`) - Work sessions CRUD
- **system_router** (`/api/system/...`) - Status and seed data
- **users_router** (`/api/users/...`) - Users CRUD

**API Examples:**

Create a new book:
```bash
curl -X POST http://localhost:5051/api/books/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Book",
    "purpose": "Documentation",
    "type": "VOLATILE"
  }'
```

Create a new cell:
```bash
curl -X POST http://localhost:5051/api/cells/create \
  -H "Content-Type: application/json" \
  -d '{
    "notebook_item_type_id": "uuid",
    "source_book_id": "uuid",
    "assignee_id": "uuid"
  }'
```

Execute a cell:
```bash
curl -X POST http://localhost:5051/api/cells/{cell_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {}
  }'
```

📚 **Documentação Detalhada**: [docs/api/README.md](./docs/api/README.md)

### Integrações de IA
- **Ollama**: Modelos locais (llama2, mistral, codellama, deepseek-coder, phi)
- **Gemini**: API do Google para modelos externos
  - **Gemini Files API**: Upload de arquivos otimizado para economia de tokens ([docs/chat-ia/GEMINI_FILES_API.md](./docs/chat-ia/GEMINI_FILES_API.md))
  - Suporte a anexos em conversas com processamento eficiente
- **OpenAI**: GPT-3.5 Turbo e GPT-4o com suporte BYOK
- **LangChain**: Framework para chains e prompts
- **LangGraph**: Orquestração de workflows com grafos
- **Classificador de Intenções**: Análise automática de intenções do usuário

📚 **Documentação Detalhada**: [docs/chat-ia/README.md](./docs/chat-ia/README.md)

### Persistência e Dados
- **MongoDB**: Armazenamento de células, livros, usuários, sessões e modelos IA
- **Sistema de Arquivos**: Persistência de artefatos em ScareFeraLab/
- **Cache**: Cache de árvore de diretórios para performance
- **Atomic Writes**: Escrita atômica de arquivos para prevenir corrupção

### Modelos de Dados (Pydantic)
Localizados em `app/models/`:
- **agents.py** - Agentes e tipos de agentes
- **ai_models.py** - ModeloIA (configurações de modelos de IA)
- **artifacts.py** - Artefatos canônicos e instanciados
- **auth.py** - Schemas de autenticação
- **base.py** - Modelos base reutilizáveis
- **chat.py** - Schemas do chat
- **content.py** - TipoCelula, Celula, Livro (artefatos de conteúdo)
- **oauth_config.py** - Configuração OAuth
- **sessions.py** - Sessões de trabalho
- **users.py** - Usuários

### Testes
- ✅ **OAuth Flow**: Testes de autenticação completa
- ✅ **Classificação de Intenções**: Validação do classificador
- ✅ **Seleção de Modelos**: Testes de escolha de modelo IA
- ✅ **Orquestração**: Testes de LangGraph
- ✅ **Gemini Service**: Testes unitários e de integração para Files API (15 unit + 5 integration tests)
- ✅ **Integração**: Testes end-to-end completos
- ✅ **Configuração**: Validação de variáveis de ambiente

📊 **Documentação de Testes**: [docs/api/README.md](./docs/api/README.md) | [../tests/README.md](../tests/README.md)

## 💾 Database Architecture

### HybridDatabase System

O backend utiliza um sistema de banco de dados híbrido que roteia dados entre **MongoDB** e **sistema de arquivos** baseado no tipo de coleção:

**Runtime Collections** (MongoDB ONLY - required for production):
- `books` - Livros de células criados pelos usuários
- `cells` - Células de conteúdo
- `sessoes` - Sessões de trabalho
- `usuarios` - Dados de usuários
- `memoria` - Memória persistente
- `traces` - Logs de execução

**Canonical Collections** (File System - version controlled):
- `cell_types` - Tipos de célula disponíveis
- `ai_models` - Configurações de modelos IA
- `agent_types` - Tipos de agentes
- `notebook_item_types` - Tipos de itens de notebook
- `permissions` - Definições de permissões
- `roles` - Definições de papéis
- `workflows` - Workflows disponíveis
- `templates` - Templates de artefatos

### ⚠️ MongoDB is MANDATORY for Production

**IMPORTANT**: As of PR #881 (Issue #880), MongoDB is **required** for production deployments. Runtime data can NO LONGER fall back to disk storage.

**Why this change?**
- Eliminates "invisible bugs" where tests pass but app doesn't work
- Enforces proper data storage for runtime data (scalable, queryable)
- Provides clear error messages instead of silent failures

**Configuration Required**:
```bash
# MANDATORY for production
MONGODB_ENABLED=true
MONGODB_URI=mongodb://localhost:27017/scareverse
MONGODB_DB_NAME=scarechat
```

**Error Behavior**:
- ✅ **MongoDB enabled**: Runtime data stored in MongoDB, canonical in files
- ❌ **MongoDB disabled**: RuntimeError raised for any runtime data operation

📚 **Migration Guide**: See [docs/issues/MIGRATION_GUIDE_ISSUE_880.md](../docs/issues/MIGRATION_GUIDE_ISSUE_880.md)

---

## 🔐 Autenticação

O backend usa **Google OAuth2** para autenticação. Endpoints protegidos requerem um token JWT válido do Google no header `Authorization`.

### Fluxo de Autenticação

1. **Frontend Login**: Usuário faz login via Google OAuth2 no frontend
2. **Aquisição de Token**: Frontend recebe um JWT token do Google após autenticação bem-sucedida
3. **Requisições API**: Frontend envia o token Google no header `Authorization: Bearer <token>`
4. **Validação Backend**: Backend valida o token Google usando o `GOOGLE_CLIENT_ID`
5. **Gestão de Usuário**: Se o usuário não existe, o backend cria automaticamente uma conta

### Configuração

Configure as seguintes variáveis de ambiente (veja `.env.example`):

```bash
# Obtenha estes valores no Google Cloud Console
# https://console.cloud.google.com/ > APIs & Services > Credentials
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# MongoDB (REQUIRED for production)
MONGODB_ENABLED=true
MONGODB_URI=mongodb://localhost:27017/scareverse
MONGODB_DB_NAME=scarechat

# Encryption (para API keys de modelos IA)
ENCRYPTION_KEY=sua-chave-fernet-gerada
```

### Endpoints Protegidos vs Públicos

**Endpoints Públicos** (sem autenticação):
- `GET /api/health` - Health check
- `GET /api/status` - Status do sistema
- `GET /api/tree` - Árvore de diretórios
- `GET /api/ScareFeraLab/{file_path}` - Servir arquivos
- `GET /api/modelos-ia/listar` - Listar modelos de IA disponíveis
- `POST /api/usuarios/registrar` - Registro de usuário

**Endpoints Protegidos** (requerem autenticação):
- Todos os endpoints de criação, atualização e deleção
- Endpoints de chat e processamento de IA
- Endpoints de sessões e gestão de usuários

📚 **Documentação Completa**: [docs/auth/README.md](./docs/auth/README.md)

## 📦 Instalação

### Pré-requisitos

- Python 3.8 ou superior
- pip ou Poetry
- MongoDB (local ou remoto)
- Ollama (opcional, para modelos locais)

### Setup

1. Navegue até o diretório backend:
```bash
cd backend
```

2. Instale as dependências:
```bash
# Com pip
pip install -r requirements.txt

# Ou com Poetry
poetry install
```

3. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite .env com suas configurações
```

**Importante - Telemetria ChromaDB**: O ChromaDB (usado para RAG/embeddings) inclui telemetria anônima via PostHog por padrão. Para desabilitar (recomendado para evitar chamadas externas não esperadas):
```bash
# Adicione ao seu .env
ANONYMIZED_TELEMETRY=false
```

4. Inicie o MongoDB (se local):
```bash
mongod --dbpath /caminho/para/db
```

## 🚀 Executando o Servidor

### Modo Desenvolvimento

```bash
# A partir do diretório backend
python -m app.main
```

Ou usando uvicorn diretamente:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A API estará disponível em:
- **API Base**: http://localhost:8000/api
- **Docs Interativos**: http://localhost:8000/api/docs
- **Docs Alternativos**: http://localhost:8000/api/redoc

### Modo Produção

```bash
# Desabilitar debug mode
export API_DEBUG=false
export LOG_LEVEL=WARNING

# Executar com configurações de produção
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📚 Documentação de APIs

### Quick Reference

**Health Check**:
```bash
curl http://localhost:8000/api/health
```

**Listar Modelos de IA**:
```bash
curl http://localhost:8000/api/modelos-ia/listar
```

**Criar Livro** (requer autenticação):
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"titulo":"Meu Livro","descricao":"Livro de exemplo","celulas":[]}' \
  http://localhost:8000/api/livros
```

**Processar Chat** (requer autenticação):
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mensagem":"Olá, como posso criar uma célula?","assignee_id":"user-id"}' \
  http://localhost:8000/api/chat/processar
```

**Árvore de Diretórios**:
```bash
curl "http://localhost:8000/api/tree?format=tree&max_depth=2"
```

📚 **Documentação Completa de APIs**: Veja [docs/api/README.md](./docs/api/README.md) para referência detalhada de todos os endpoints

## 🔒 Segurança

### Validação de Paths
Todos os caminhos de arquivo são validados e sanitizados para prevenir:
- Ataques de directory traversal (`../`, `../../`)
- Injeção de caminho absoluto
- Injeção de null byte
- Acesso fora do diretório ScareFeraLab

### Validação de Nomes de Arquivo
Nomes de arquivo são verificados para:
- Extensões permitidas (veja `utils.py` para lista)
- Caracteres inválidos (`/`, `\`, `..`)
- Extensão obrigatória

### Criptografia de API Keys
API keys de modelos IA são automaticamente criptografadas usando Fernet (AES-128-CBC + HMAC):
- Criptografia transparente ao salvar
- Descriptografia apenas em memória
- Nunca armazenadas em texto puro

📚 **Documentação de Segurança**: [SECURITY.md](./SECURITY.md) | [docs/SECURITY_MIGRATION.md](./docs/SECURITY_MIGRATION.md)

## ⚙️ Configuração

Variáveis de ambiente disponíveis (veja `.env.example` para lista completa):

```bash
# Servidor
API_HOST="0.0.0.0"
API_PORT="8000"
API_DEBUG="true"

# Logging
LOG_LEVEL="INFO"

# MongoDB (REQUIRED for production)
MONGODB_ENABLED="true"
MONGODB_URI="mongodb://localhost:27017/scareverse"
MONGODB_DB_NAME="scarechat"

# Autenticação
GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="your-client-secret"

# Criptografia
ENCRYPTION_KEY="your-fernet-key"

# Integrações IA
GEMINI_API_KEY="your-gemini-key"  # Opcional, global
OPENAI_API_KEY="your-openai-key"  # Opcional, global
OLLAMA_BASE_URL="http://localhost:11434"  # Opcional, padrão
```

## 🧪 Testes

### Executar Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=app --cov-report=html --cov-report=json

# Testes específicos
pytest tests/unit/
pytest tests/integration/
pytest tests/endpoints/
```

### Testes Manuais

Use a documentação interativa:
1. Inicie o servidor
2. Abra http://localhost:8000/api/docs
3. Teste cada endpoint usando o recurso "Try it out"

### Scripts de Teste

```bash
# Teste de autenticação OAuth E2E
./scripts/test_oauth_e2e.py

# Teste de endpoints do backend
./scripts/test_backend_endpoints.py

# Verificação de integração Ollama
./scripts/verify_ollama_integration.py
```

📊 **Documentação de Testes**: [docs/api/README.md](./docs/api/README.md)

## 📖 Documentação Adicional

### Por Categoria
- **Autenticação**: [docs/auth/](./docs/auth/)
  - [AUTH_IMPLEMENTATION.md](./docs/auth/AUTH_IMPLEMENTATION.md)
  - [E2E_AUTH_IMPLEMENTATION.md](./docs/auth/E2E_AUTH_IMPLEMENTATION.md)
  - [TOKEN_EXPIRATION_IMPLEMENTATION.md](./docs/auth/TOKEN_EXPIRATION_IMPLEMENTATION.md)

- **Chat IA**: [docs/chat-ia/](./docs/chat-ia/)
  - [QUICK_START_CHAT_IA.md](./docs/chat-ia/QUICK_START_CHAT_IA.md)
  - [GEMINI_FILES_API.md](./docs/chat-ia/GEMINI_FILES_API.md)
  - [MODEL_SELECTION_GUIDE.md](./docs/chat-ia/MODEL_SELECTION_GUIDE.md)
  - [LANGCHAIN_LANGGRAPH_IMPLEMENTATION.md](./docs/chat-ia/LANGCHAIN_LANGGRAPH_IMPLEMENTATION.md)

- **APIs**: [docs/api/](./docs/api/)
  - [README.md](./docs/api/README.md) - Referência completa de endpoints
  - [MODELOS_IA_API.md](./docs/api/MODELOS_IA_API.md)
  - [INTEGRATION_TEST_ARCHITECTURE.md](./docs/api/INTEGRATION_TEST_ARCHITECTURE.md)

- **Artefatos**: [../Artefatos/](../Artefatos/)
  - [Modelos de IA](../Artefatos/canonicos/modelos_ia/README.md)
  - [Tipos de Célula](../Artefatos/canonicos/tipos_celula/README.md)
  - [Agent Types](../Artefatos/canonicos/agent_types/README.md)

### Por Funcionalidade
- **Canonical Book Architecture**: [docs/CANONICAL_BOOK_ARCHITECTURE.md](./docs/CANONICAL_BOOK_ARCHITECTURE.md)
- **Function Calling**: [docs/FUNCTION_CALLING.md](./docs/FUNCTION_CALLING.md)
- **Idempotent Cell Generation**: [docs/IDEMPOTENT_CELL_GENERATION.md](./docs/IDEMPOTENT_CELL_GENERATION.md)
- **Migration Cockpit Backend**: [docs/MIGRATION_COCKPIT_BACKEND.md](./docs/MIGRATION_COCKPIT_BACKEND.md)
- **Ngrok Share**: [docs/ngrok-share.md](./docs/ngrok-share.md)

## 🔗 Links Úteis

- [Projeto ScareVerse](../ScareVerse_Project.md) - Visão geral do projeto
- [Ruleset](../RULESET.md) - Regras e padrões do projeto
- [Tests Documentation](../tests/README.md) - Documentação de testes
- [Frontend Vue.js](../cockpit-vue/) - Frontend da aplicação
- [Artefatos](../Artefatos/) - Sistema de artefatos

---

**Última Atualização**: 2025-11-15  
**Versão**: 2.1 (Documentation improvements and modularization)
