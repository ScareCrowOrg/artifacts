---
processed: true
processed_date: 2025-12-09
themes:
  - authentication
  - password
  - bcrypt
  - security
modules:
  - backend
  - security
code_verified: true
dead_docs_found: false
---
# Autenticação por Senha - ScareVerse

## Visão Geral

Este documento descreve a implementação de autenticação por email/senha como alternativa ao Google OAuth2 no ScareVerse. A autenticação por senha é **opcional** e complementar ao sistema OAuth existente.

## Conceitos-Chave

- **Login Primário**: Google OAuth2 (obrigatório para primeiro cadastro)
- **Login Alternativo**: Email/Senha (opcional, cadastrado após login Google)
- **Mesmo Usuário**: Ambos os métodos levam ao mesmo usuário (cruzamento por email)
- **Segurança**: Senhas são hash + salt com bcrypt, nunca armazenadas em plain text

## Fluxo de Uso

### Fluxo 1: Cadastro Inicial (Google OAuth)

```
1. Usuário → Cockpit: Clica em "Login com Google"
2. Cockpit → Backend: GET /api/auth/google?redirect_uri=...
3. Backend → Google: Redireciona para OAuth
4. Google → Cockpit: Retorna com código de autorização
5. Cockpit → Backend: POST /api/auth/google/callback {code, redirect_uri}
6. Backend → Google: Troca código por token
7. Backend → Database: Cria/atualiza usuário
8. Backend → Cockpit: Retorna {token, usuario, sessao}
9. Cockpit: Armazena token e exibe dashboard
```

### Fluxo 2: Cadastro de Senha (Após Login Google)

```
1. Usuário → Cockpit: Acessa "Configurações" > "Cadastrar Senha"
2. Cockpit → Backend: POST /api/auth/password/register
   Headers: Authorization: Bearer <token>
   Body: {password: "senha_segura"}
3. Backend: Valida token JWT
4. Backend: Hash da senha com bcrypt
5. Backend: Atualiza usuario.hashedPassword
6. Backend → Cockpit: {message: "Senha cadastrada com sucesso"}
7. Cockpit: Exibe confirmação
```

### Fluxo 3: Login por Email/Senha

```
1. Usuário → Cockpit: Preenche email/senha
2. Cockpit → Backend: POST /api/auth/password/login
   Body: {email, password}
3. Backend: Busca usuário por email
4. Backend: Verifica senha com bcrypt
5. Backend: Cria sessão e gera token JWT
6. Backend → Cockpit: {token, usuario, sessao}
7. Cockpit: Armazena token e exibe dashboard
```

## Endpoints da API

### POST /api/auth/password/register

Cadastra senha para usuário autenticado.

**Autenticação**: Requerida (JWT token)

**Request:**
```json
{
  "password": "senha_minimo_8_caracteres"
}
```

**Response (200):**
```json
{
  "message": "Senha cadastrada com sucesso",
  "email": "usuario@example.com"
}
```

**Erros:**
- `401 Unauthorized`: Token inválido ou ausente
- `422 Unprocessable Entity`: Senha muito curta (mínimo 8 caracteres)
- `500 Internal Server Error`: Erro ao salvar senha

**Exemplo com curl:**
```bash
curl -X POST http://localhost:5051/api/auth/password/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <seu_token_jwt>" \
  -d '{"password": "SenhaSegura123!"}'
```

### POST /api/auth/password/login

Login com email/senha.

**Autenticação**: Não requerida

**Request:**
```json
{
  "email": "usuario@example.com",
  "password": "SenhaSegura123!"
}
```

**Response (200):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "usuario": {
    "id": "uuid-do-usuario",
    "nome": "Nome do Usuário",
    "email": "usuario@example.com",
    "googleId": "google-id-123",
    "dataRegistro": "2024-01-01T00:00:00",
    "galaxia": "GalaxiaPadrao",
    "nivel": 1,
    "mascote": {
      "nome": "ScaryBot",
      "tipo": "IA"
    }
  },
  "sessao": {
    "id": "uuid-da-sessao",
    "usuarioId": "uuid-do-usuario",
    "dataCriacao": "2024-01-01T00:00:00",
    "dataExpiracao": "2024-01-08T00:00:00",
    "ativa": true,
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

**Erros:**
- `401 Unauthorized`: Email ou senha incorretos (mensagem genérica por segurança)
- `500 Internal Server Error`: Erro interno

**Exemplo com curl:**
```bash
curl -X POST http://localhost:5051/api/auth/password/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "usuario@example.com",
    "password": "SenhaSegura123!"
  }'
```

## Modelo de Dados

### Usuario (atualizado)

```python
class Usuario(BaseModel):
    id: str
    nome: str
    email: str
    googleId: Optional[str]  # ID do Google OAuth
    hashedPassword: Optional[str]  # Hash bcrypt da senha (NOVO)
    dataRegistro: datetime
    galaxia: str
    nivel: int
    mascote: Mascote
```

**Campos Relacionados à Autenticação:**
- `email`: Usado como identificador único para login por senha
- `googleId`: Google ID do OAuth2 (opcional se usuário só usa senha)
- `hashedPassword`: Hash bcrypt da senha (opcional se usuário só usa Google)

**Nota**: Um usuário pode ter:
- Apenas `googleId` (só login Google)
- `googleId` + `hashedPassword` (ambos métodos)
- Teoricamente só `hashedPassword`, mas o cadastro inicial sempre usa Google

## Segurança

### Hashing de Senha

**Biblioteca**: `passlib[bcrypt]`

**Algoritmo**: bcrypt com salt automático

**Funções:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

### Boas Práticas Implementadas

1. **Senha Mínima**: 8 caracteres (validação Pydantic)
2. **Hash + Salt**: bcrypt automático
3. **Mensagens Genéricas**: "Email ou senha incorretos" (não revela se user existe)
4. **Token JWT**: Mesmo padrão do OAuth (7 dias de validade)
5. **Autenticação Requerida**: Cadastro de senha requer login Google primeiro

### Considerações de Segurança

⚠️ **Limitações Conhecidas**:
- Não há rate limiting nos endpoints (recomendado para produção)
- Não há bloqueio de conta após tentativas falhadas
- Não há política de complexidade de senha além do tamanho mínimo
- Não há expiração/rotação de senha

✅ **Para Produção**:
- Adicionar rate limiting (ex: 5 tentativas/minuto)
- Implementar bloqueio temporário de conta
- Política de senha mais forte (números, símbolos, maiúsculas)
- Email de confirmação para cadastro de senha
- 2FA (Two-Factor Authentication)

## Variáveis de Ambiente

Nenhuma nova variável é necessária. A funcionalidade usa as configurações existentes:

```bash
# JWT (já existente)
JWT_SECRET_KEY=seu_secret_key_aqui

# OAuth (já existente, ainda necessário para cadastro inicial)
GOOGLE_CLIENT_ID=seu_google_client_id
GOOGLE_CLIENT_SECRET=seu_google_client_secret
```

## Testes

### Executar Testes Automatizados

```bash
cd backend
python3 tests/test_password_auth.py
```

### Teste Manual Completo

**1. Iniciar servidor:**
```bash
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 5051 --reload
```

**2. Login Google (para criar usuário):**
- Acesse o cockpit em http://localhost:3000
- Faça login com Google
- Copie o token JWT do localStorage

**3. Cadastrar senha:**
```bash
TOKEN="seu_token_aqui"
curl -X POST http://localhost:5051/api/auth/password/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"password": "TestPass123!"}'
```

**4. Logout e login por senha:**
```bash
curl -X POST http://localhost:5051/api/auth/password/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "seu_email@gmail.com",
    "password": "TestPass123!"
  }'
```

## Compatibilidade

### Backward Compatibility

✅ **Totalmente compatível** com sistema OAuth existente:
- Usuários antigos continuam funcionando sem mudanças
- Google OAuth continua sendo o método primário
- Campo `hashedPassword` é opcional
- Token JWT usa o mesmo formato e validação

### Migration Path

Não há necessidade de migração. O campo `hashedPassword` é opcional e será `null` para usuários existentes até que cadastrem uma senha.

## Troubleshooting

### Erro: "Not authenticated"
- **Causa**: Token JWT inválido ou expirado ao tentar cadastrar senha
- **Solução**: Faça login com Google novamente para obter novo token

### Erro: "Email ou senha incorretos"
- **Causa 1**: Usuário não cadastrou senha ainda
- **Solução**: Use login Google ou cadastre senha via `/password/register`
- **Causa 2**: Senha incorreta
- **Solução**: Verifique a senha digitada

### Erro: "Validation error" ao cadastrar senha
- **Causa**: Senha muito curta (menos de 8 caracteres)
- **Solução**: Use senha com pelo menos 8 caracteres

### Banco de dados não encontra usuário
- **Causa**: Email não existe no sistema
- **Solução**: Primeiro faça login com Google para criar o usuário

## Referências

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Passlib Documentation](https://passlib.readthedocs.io/)
- [bcrypt Algorithm](https://en.wikipedia.org/wiki/Bcrypt)
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

## Changelog

### v1.0.0 (2024-11-04)
- ✨ Implementação inicial de autenticação por senha
- ✨ Endpoint POST /api/auth/password/register
- ✨ Endpoint POST /api/auth/password/login
- ✨ Hash de senha com bcrypt
- ✨ Validação de senha mínima (8 caracteres)
- ✨ Testes automatizados
- 📝 Documentação completa
