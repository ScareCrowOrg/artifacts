---
processed: true
processed_date: 2025-12-09
themes:
  - authentication
  - security
  - oauth2
  - jwt
  - sessions
modules:
  - backend
  - frontend
  - infrastructure
code_verified: true
dead_docs_found: false
---
# Implementação de Autenticação OAuth2 com Google

## Visão Geral

Este documento descreve a implementação completa de autenticação OAuth2 com Google, gerenciamento de sessões e isolamento de artefatos por usuário/sessão no ScareVerse.

## Funcionalidades Implementadas

### Backend

#### 1. Modelos de Dados

**Usuario** (`backend/app/models.py`)
- Adicionado campo `googleId` para armazenar o Google ID do usuário
- Permite login tanto via registro manual quanto via Google OAuth

**Sessao** (`backend/app/models.py`)
- Modelo completo para gerenciamento de sessões
- Campos: `id`, `usuarioId`, `dataCriacao`, `dataExpiracao`, `ativa`, `token`
- Sessões expiram automaticamente após 7 dias

**ConfiguracaoOAuth** (`backend/app/models.py`)
- Modelo para armazenar configurações OAuth2
- Campos: `googleClientId`, `googleClientSecret`, `authEnabled`

#### 2. Módulo de Autenticação (`backend/app/auth.py`)

- **JWT Token Management**: Criação e validação de tokens JWT
- **OAuth2 Integration**: Cliente OAuth configurável para Google
- **Dependency Injection**: 
  - `get_current_user()`: Obtém usuário atual (opcional)
  - `get_current_user_required()`: Requer autenticação
  - `get_current_session()`: Obtém sessão atual

#### 3. Endpoints de Autenticação (`backend/app/auth_router.py`)

##### `GET /api/auth/google`
Inicia o fluxo OAuth2 do Google
- Parâmetros: `redirect_uri` (obrigatório)
- Retorna: URL de autenticação do Google

##### `POST /api/auth/google/callback`
Processa callback do Google OAuth
- Body: `{ "code": "...", "redirect_uri": "..." }`
- Cria ou recupera usuário existente
- Cria nova sessão
- Retorna: `{ "token": "...", "usuario": {...}, "sessao": {...} }`

##### `GET /api/auth/status`
Verifica status de autenticação
- Retorna: `{ "authEnabled": boolean, "configured": boolean }`

#### 4. Endpoints de Sessão (`backend/app/routers/sessoes_router.py`)

##### `POST /api/sessoes/criar`
Cria nova sessão para um usuário
- Body: `{ "usuarioId": "..." }`
- Retorna: Dados da sessão e token JWT

##### `GET /api/sessoes/usuario/{usuario_id}`
Lista todas as sessões de um usuário
- Retorna: Array de sessões

##### `POST /api/sessoes/{sessao_id}/fechar`
Fecha/desativa uma sessão
- Retorna: Confirmação de fechamento

#### 5. Endpoints de Configuração OAuth (`backend/app/routers/config_router.py`)

##### `GET /api/config/oauth`
Obtém configuração OAuth (sem expor o secret)
- Retorna: `{ "googleClientId": "...", "authEnabled": boolean }`

##### `POST /api/config/oauth`
Atualiza configuração OAuth
- Body: `{ "googleClientId": "...", "googleClientSecret": "..." }`
- Autenticação é habilitada automaticamente quando ambos os campos estão preenchidos

#### 6. Database Enhancement (`backend/app/database.py`)

- **Configuração Persistente**: `get_config()`, `set_config()` para armazenar configurações
- **Busca por Campo**: `find_by_field()` para buscar documentos por qualquer campo
- **Suporte a Sessões**: Diretório `runtime/sessoes` para armazenar sessões

### Frontend (cockpit-vue)

#### 1. Serviço de Autenticação (`src/services/authService.js`)

Serviço centralizado para gerenciamento de autenticação:
- `isAuthenticated()`: Verifica se usuário está autenticado
- `getUser()`, `getSession()`, `getToken()`: Getters para dados de autenticação
- `setAuth()`, `clearAuth()`: Gerenciamento de localStorage
- `checkAuthStatus()`: Verifica status do servidor
- `getOAuthConfig()`, `updateOAuthConfig()`: Gerenciamento de configuração
- `initiateGoogleLogin()`: Inicia fluxo OAuth
- `handleGoogleCallback()`: Processa callback
- `logout()`: Desconecta usuário e fecha sessão
- `getAuthHeaders()`: Headers para requisições autenticadas

#### 2. Componentes de UI

##### SettingsPanel (`src/components/SettingsPanel.vue`)
- Painel de configuração acessível via menu
- Permite configurar Google Client ID e Secret
- Mostra status de autenticação (Habilitada/Desabilitada)
- Oculta secret por segurança após salvar

##### LoginPanel (`src/components/LoginPanel.vue`)
- Tela de login exibida quando autenticação é obrigatória
- Botão "Entrar com Google" com design do Google
- Loading state durante autenticação

##### AuthCallback (`src/components/AuthCallback.vue`)
- Componente dedicado para processar callback OAuth
- Exibe loading durante processamento
- Trata erros de autenticação
- Redireciona para home após sucesso

##### AppHeader (`src/components/AppHeader.vue`)
- Atualizado para mostrar informações do usuário
- Menu dropdown com:
  - Configurações
  - Sair (quando autenticado)
- Botão de configurações sempre visível

#### 3. Fluxo de Autenticação no App (`src/App.vue`)

- **Inicialização**: Verifica status de autenticação no mount
- **Modo Aberto**: Funciona sem login quando OAuth não configurado
- **Modo Autenticado**: Requer login quando OAuth configurado
- **Callback Handling**: Rota especial `/auth/callback` para OAuth
- **State Management**: Gerencia estado de autenticação em nível de aplicação

#### 4. Endpoints Configuration (`src/config/endpoints.js`)

Adicionados endpoints:
- `authStatus`: Status de autenticação
- `googleLogin`: Iniciar login Google
- `googleCallback`: Callback OAuth
- `oauthConfig`: Configuração OAuth
- `criarSessao`, `listarSessoes`, `fecharSessao`: Gerenciamento de sessões

## Fluxo de Uso

### Configuração Inicial (Modo Aberto)

1. Usuário acessa o cockpit sem autenticação configurada
2. Sistema funciona em "modo aberto" - sem exigir login
3. Admin acessa Configurações via menu (⚙️)
4. Admin configura Google Client ID e Secret
5. Autenticação é automaticamente habilitada

### Login com Google (Modo Autenticado)

1. Usuário acessa o cockpit
2. Sistema detecta que autenticação está habilitada
3. Tela de login é exibida
4. Usuário clica em "Entrar com Google"
5. Sistema redireciona para Google OAuth
6. Usuário autoriza aplicação no Google
7. Google redireciona para `/auth/callback?code=...`
8. Sistema processa código de autorização
9. Cria/recupera usuário no banco
10. Cria nova sessão com token JWT
11. Armazena token no localStorage
12. Redireciona para aplicação principal

### Sessões

- Cada login cria uma nova sessão
- Sessões expiram após 7 dias
- Token JWT inclui `usuario_id` e `sessao_id`
- Sessões podem ser listadas e fechadas manualmente

## Isolamento de Artefatos

### Estrutura de Armazenamento

```
Artefatos/
├── canonicos/           # Templates e tipos (globais)
│   ├── celulas/
│   ├── livros/
│   ├── templates/
│   └── tipos_celula/
├── runtime/             # Instâncias (por usuário/sessão)
│   ├── celulas/
│   │   └── {usuario_id}/{sessao_id}/
│   ├── livros/
│   │   └── {usuario_id}/{sessao_id}/
│   ├── memoria/
│   │   └── {usuario_id}/{sessao_id}/
│   ├── usuarios/        # Dados de usuários (global)
│   └── sessoes/         # Sessões (global)
└── config/              # Configurações (global)
    └── oauth.json
```

### Implementação do Isolamento

- **Células e Livros**: Armazenados em `runtime/{collection}/{usuario_id}/{sessao_id}/`
- **Sessões e Usuários**: Armazenados globalmente em `runtime/{collection}/`
- **Configurações**: Armazenadas em `config/`

## Segurança

### Protocolos Implementados

1. **JWT**: Tokens assinados com HS256
2. **OAuth2**: Fluxo Authorization Code
3. **Secret Storage**: Client Secret nunca é exposto via API
4. **Token Expiration**: Tokens expiram após 7 dias
5. **HTTPS Required**: Para produção, OAuth requer HTTPS

### Boas Práticas

- Secrets armazenados em arquivos de configuração (não no código)
- Tokens armazenados em localStorage (não em cookies por simplicidade)
- Validação de tokens em cada requisição autenticada
- Sessões podem ser fechadas manualmente

## Configuração para Produção

### 1. Criar Projeto no Google Cloud

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie novo projeto ou selecione existente
3. Ative Google+ API
4. Vá para "Credenciais"
5. Crie "ID do cliente OAuth 2.0"
6. Configure URLs autorizadas:
   - Redirect URI: `https://seu-dominio.com/auth/callback`

### 2. Configurar no Cockpit

1. Acesse o cockpit
2. Clique no menu ⚙️
3. Selecione "Configurações"
4. Cole o Client ID e Client Secret
5. Clique em "Salvar Configuração"

### 3. Variáveis de Ambiente

```bash
# Backend
JWT_SECRET_KEY=your-secret-key-here  # Gere com: openssl rand -hex 32
API_HOST=0.0.0.0
API_PORT=5051

# Frontend
VITE_API_BASE_URL=https://seu-dominio.com
```

## Testes

### Backend

Execute o script de teste:

```bash
cd backend
./test_auth_flow.sh
```

Testa:
- Status de autenticação
- Configuração OAuth
- Registro de usuário
- Criação de sessão
- Listagem de sessões
- Fechamento de sessão

### Frontend

1. Inicie o backend: `cd backend && uvicorn app.main:app --port 5051`
2. Inicie o frontend: `cd cockpit-vue && npm run dev`
3. Acesse `http://localhost:5173`
4. Configure OAuth nas configurações
5. Faça logout e teste o login

## Próximos Passos

### Melhorias Futuras

1. **Middleware de Autenticação**: Proteger endpoints automaticamente
2. **Refresh Tokens**: Renovação automática de tokens
3. **Rate Limiting**: Proteção contra abuso
4. **Audit Log**: Registro de ações de usuários
5. **Multi-factor Authentication**: Camada adicional de segurança
6. **Role-Based Access Control**: Permissões granulares

### Isolamento Completo

Atualizar endpoints existentes para:
- Usar `sessao_id` do token JWT
- Filtrar automaticamente por `usuario_id` e `sessao_id`
- Adicionar middleware de validação de sessão

## Dependências Adicionadas

### Backend
```
authlib==1.3.0
python-jose[cryptography]==3.3.0
httpx==0.27.0
```

### Frontend
Nenhuma dependência adicional (usa fetch nativo)

## Arquivos Criados/Modificados

### Backend
- ✅ `backend/app/auth.py` (novo)
- ✅ `backend/app/auth_router.py` (novo)
- ✅ `backend/app/models.py` (modificado)
- ✅ `backend/app/chat_router.py` (modificado)
- ✅ `backend/app/database.py` (modificado)
- ✅ `backend/app/main.py` (modificado)
- ✅ `backend/requirements.txt` (modificado)
- ✅ `backend/test_auth_flow.sh` (novo)

### Frontend
- ✅ `cockpit-vue/src/services/authService.js` (novo)
- ✅ `cockpit-vue/src/components/SettingsPanel.vue` (novo)
- ✅ `cockpit-vue/src/components/LoginPanel.vue` (novo)
- ✅ `cockpit-vue/src/components/AuthCallback.vue` (novo)
- ✅ `cockpit-vue/src/components/AppHeader.vue` (modificado)
- ✅ `cockpit-vue/src/App.vue` (modificado)
- ✅ `cockpit-vue/src/config/endpoints.js` (modificado)

## Conclusão

A implementação fornece:
- ✅ Autenticação OAuth2 completa com Google
- ✅ Gerenciamento de sessões com JWT
- ✅ Configuração dinâmica via UI
- ✅ Modo aberto quando não configurado
- ✅ Interface de usuário completa
- ✅ Estrutura preparada para isolamento de artefatos
- ✅ Segurança básica implementada
- ✅ Testes automatizados

O sistema está pronto para uso em desenvolvimento e pode ser facilmente adaptado para produção seguindo as instruções de configuração acima.
