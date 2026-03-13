---
processed: true
processed_date: 2025-12-09
themes:
  - ai-models
  - ollama
  - gemini
  - model-selection
  - api
modules:
  - backend
  - ai-integration
code_verified: true
dead_docs_found: false
---
# Guia de Seleção de Modelo no Chat IA

## Visão Geral

O endpoint `/chat/processar` agora suporta seleção de modelo de IA, permitindo que usuários escolham entre modelos locais (Ollama) e externos (Gemini API do Google).

## Modelos Suportados

### Modelos Locais (Ollama)

Os seguintes modelos Ollama são suportados:

- **mistral** - Modelo padrão, balanceado entre velocidade e qualidade
- **deepseek** - Modelo focado em compreensão profunda
- **phi** - Modelo leve e rápido

### Modelos Externos (Gemini)

- **gemini** - Google Gemini Pro via API

## Configuração

### Backend

#### Variáveis de Ambiente

Adicione as seguintes variáveis ao arquivo `.env` do backend:

```bash
# Ollama Configuration (já existente)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT=30

# Gemini API Configuration (NOVO)
GEMINI_API_KEY=your-api-key-here
GEMINI_API_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_TIMEOUT=30
```

#### Obtendo a API Key do Gemini

1. Acesse [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Faça login com sua conta Google
3. Clique em "Create API Key"
4. Copie a chave gerada
5. Adicione a chave à variável `GEMINI_API_KEY` no `.env`

**Nota:** A integração com Gemini só será ativada quando `GEMINI_API_KEY` estiver configurada.

### Ollama Setup

Para usar modelos Ollama localmente:

1. **Instalar Ollama:**

   **Linux:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

   **macOS:**
   ```bash
   brew install ollama
   ```

   **Windows:**
   Download from https://ollama.com/download

2. **Baixar modelos:**
   ```bash
   ollama pull mistral
   ollama pull deepseek
   ollama pull phi
   ```

3. **Iniciar o serviço:**
   ```bash
   ollama serve
   ```

   O serviço estará disponível em `http://localhost:11434`

## Uso da API

### Request Format

```json
POST /api/chat/processar
Authorization: Bearer <token>
Content-Type: application/json

{
  "intencao": "Criar um sistema de login com JWT",
  "assignee_id": "uuid_do_usuario",
  "modelo": "mistral",
  "historico": [
    {
      "role": "user",
      "content": "Olá"
    },
    {
      "role": "assistant",
      "content": "Olá! Como posso ajudar?"
    }
  ]
}
```

### Parâmetros

- **intencao** (obrigatório): String - Intenção/pergunta do usuário
- **assignee_id** (obrigatório): String - UUID do usuário (gerenciado automaticamente pelo frontend)
- **modelo** (opcional): String - Modelo a ser usado (padrão: "mistral")
  - Ollama: `mistral`, `deepseek`, `phi`
  - Gemini: `gemini`
- **historico** (opcional): Array - Histórico da conversa

### Response Format

```json
{
  "resposta": "Ótimo! Para criar um sistema de login com JWT...",
  "celula": null
}
```

**Nota:** O endpoint agora retorna apenas a resposta do modelo, sem criar células automaticamente. A estruturação de células será implementada em versões futuras.

### Códigos de Status

- **200 OK**: Resposta gerada com sucesso
- **400 Bad Request**: Modelo não suportado ou parâmetros inválidos
- **401 Unauthorized**: Token de autenticação inválido ou ausente
- **503 Service Unavailable**: Serviço de IA (Ollama ou Gemini) indisponível
- **500 Internal Server Error**: Erro interno ao processar a requisição

### Exemplos de Erro

#### Modelo Não Suportado

```json
{
  "detail": "Modelo 'gpt4' não suportado. Modelos disponíveis: Ollama (mistral, deepseek, phi), Gemini (gemini)"
}
```

#### Serviço Indisponível

```json
{
  "detail": "Ollama (mistral) não disponível: Ollama não está disponível. Certifique-se de que o serviço está rodando em http://localhost:11434"
}
```

#### Gemini Não Configurado

```json
{
  "detail": "Gemini não disponível: Gemini não está disponível. Certifique-se de que o GEMINI_API_KEY está configurado corretamente."
}
```

## Frontend

### Componente ChatIA.vue

O componente foi atualizado para incluir um seletor de modelo:

```vue
<select v-model="selectedModel">
  <optgroup label="Modelos Locais (Ollama)">
    <option value="mistral">🏠 Mistral (Ollama)</option>
    <option value="deepseek">🏠 DeepSeek (Ollama)</option>
    <option value="phi">🏠 Phi (Ollama)</option>
  </optgroup>
  <optgroup label="Modelos Externos">
    <option value="gemini">☁️ Gemini (Google)</option>
  </optgroup>
</select>
```

### Uso no Frontend

1. O usuário seleciona o modelo desejado no dropdown
2. O modelo selecionado é enviado junto com a mensagem
3. A resposta é exibida no chat

## Fallback e Tratamento de Erros

### Comportamento de Fallback

O sistema implementa tratamento de erros robusto:

1. **Modelo não disponível**: Retorna erro 503 com mensagem clara
2. **Modelo não suportado**: Retorna erro 400 com lista de modelos disponíveis
3. **Erro de timeout**: Retorna erro após o tempo configurado (30s padrão)
4. **Gemini não configurado**: Retorna erro se API key não estiver configurada

### Logs

Todos os erros são registrados no log do backend:

```
[INFO] Processando intenção do chat: Criar um sistema de login...
[INFO] Resposta gerada pelo Ollama (mistral) com sucesso
```

ou

```
[WARNING] Ollama (mistral) não disponível: Connection refused
[ERROR] Erro ao chamar Ollama (mistral): Connection timeout
```

## Comparação de Modelos

| Modelo | Tipo | Velocidade | Qualidade | Offline | Custo |
|--------|------|------------|-----------|---------|-------|
| mistral | Ollama | ⚡⚡⚡ | ⭐⭐⭐⭐ | ✅ | Grátis |
| deepseek | Ollama | ⚡⚡ | ⭐⭐⭐⭐⭐ | ✅ | Grátis |
| phi | Ollama | ⚡⚡⚡⚡ | ⭐⭐⭐ | ✅ | Grátis |
| gemini | API | ⚡⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ❌ | API Quota |

### Recomendações

- **Desenvolvimento Local**: Use `mistral` ou `phi` (mais rápidos)
- **Produção com Internet**: Use `gemini` (melhor qualidade)
- **Offline/Sem API Key**: Use qualquer modelo Ollama
- **Tarefas Complexas**: Use `deepseek` ou `gemini`

## Troubleshooting

### Ollama não responde

**Sintoma**: Erro 503 ao usar modelos Ollama

**Solução**:
```bash
# Verificar se Ollama está rodando
curl http://localhost:11434/api/tags

# Reiniciar Ollama
pkill ollama
ollama serve
```

### Gemini retorna erro 403

**Sintoma**: Erro ao usar modelo Gemini

**Possíveis causas**:
1. API Key inválida
2. API Key expirada
3. Quota excedida

**Solução**:
1. Verificar API Key em [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Gerar nova API Key se necessário
3. Verificar quota em [Google Cloud Console](https://console.cloud.google.com/)

### Modelo não encontrado no Ollama

**Sintoma**: Ollama retorna "model not found"

**Solução**:
```bash
# Listar modelos instalados
ollama list

# Baixar modelo faltante
ollama pull mistral
ollama pull deepseek
ollama pull phi
```

### Timeout muito curto

**Sintoma**: Requisições são canceladas antes de completar

**Solução**: Aumentar timeout no `.env`:
```bash
OLLAMA_TIMEOUT=60
GEMINI_TIMEOUT=60
```

## Testes

### Testar Ollama

```bash
# Teste direto no Ollama
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Olá, como você pode me ajudar?",
  "stream": false
}'
```

### Testar Gemini

```bash
# Teste via API do backend
curl -X POST http://localhost:5051/api/chat/processar \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "intencao": "Teste de integração",
    "assignee_id": "user-uuid",
    "modelo": "gemini"
  }'
```

### Testar Frontend

1. Acesse `http://localhost:5173`
2. Abra o chat IA
3. Selecione um modelo no dropdown
4. Envie uma mensagem
5. Verifique a resposta

## Segurança

### API Keys

⚠️ **IMPORTANTE**: Nunca commit API keys no código!

- Use variáveis de ambiente (`.env`)
- Adicione `.env` ao `.gitignore`
- Para produção, use secrets management (AWS Secrets Manager, etc.)

### Validação

O endpoint valida:
- Autenticação do usuário (JWT token)
- Modelo solicitado
- Formato da requisição
- Disponibilidade do serviço

## Próximas Etapas

- [ ] Streaming de respostas em tempo real
- [ ] Suporte a mais modelos Ollama
- [ ] Integração com Claude/OpenAI
- [ ] Cache de respostas
- [ ] Rate limiting por usuário
- [ ] Métricas de uso por modelo
- [ ] Auto-seleção de modelo baseado na intenção

## Referências

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Ollama API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Google Gemini API](https://ai.google.dev/docs)
- [ScareVerse Project Documentation](ScareVerse_Project.md)

## Suporte

Para problemas ou dúvidas:
1. Verifique este guia
2. Revise a seção de Troubleshooting
3. Confira os logs do backend
4. Abra uma issue no GitHub
