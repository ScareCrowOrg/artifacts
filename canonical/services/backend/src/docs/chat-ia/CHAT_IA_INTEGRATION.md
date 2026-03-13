---
processed: true
processed_date: 2025-12-09
themes:
  - chat
  - ai
  - nlp
  - conversational-ui
  - cell-creation
modules:
  - backend
  - frontend
  - ai-integration
code_verified: true
dead_docs_found: false
---
# Integração de Chat IA no Cockpit - Etapa 1

## Visão Geral

Esta implementação adiciona um componente de chat IA ao cockpit Vue.js, permitindo que usuários interajam com o sistema através de linguagem natural para criar células e artefatos.

## Arquitetura

### Frontend (cockpit-vue)

#### Novo Componente: `ChatIA.vue`
Localização: `cockpit-vue/src/components/ChatIA.vue`

**Características**:
- Interface de chat moderna e responsiva
- Histórico de mensagens com timestamps
- Indicador de digitação durante processamento
- Sugestões de intenções pré-definidas
- Integração com notebook para exibir células criadas
- Tema dark consistente com o cockpit

**Props e Eventos**:
- **Evento emitido**: `celula-criada` - Quando uma célula é criada pela IA
- **API**: Chama `POST /api/chat/processar`

#### Integração no App.vue
O componente foi adicionado à aplicação principal:
```vue
<ChatIA @celula-criada="onCelulaCriada" />
```

### Backend (FastAPI)

#### Novo Endpoint: `/api/chat/processar`
Localização: `backend/app/routers/chat_router.py`

**Request**:
```json
{
  "intencao": "string - Intenção do usuário em linguagem natural",
  "assignee_id": "string - UUID do usuário"
}
```

**Response**:
```json
{
  "resposta": "string - Resposta da IA para o usuário",
  "celula": {
    "id": "string - UUID da célula criada",
    "tipo": "string - Tipo da célula",
    "conteudo": "string - Conteúdo markdown da célula"
  }
}
```

#### Lógica de Processamento (Current Implementation)
Para a primeira etapa, implementamos uma lógica básica de parsing por palavras-chave:

**Palavras-chave suportadas**:
- `editor`, `editar`, `modificar` → Célula de "Editor de Artefatos"
- `memoria`, `memorizar`, `lembrar`, `salvar` → Célula de "Memória"
- `executar`, `rodar`, `script`, `codigo` → Célula de "Executor de Scripts"
- `decompo`, `dividir`, `separar` → Célula de "Decomposição"
- `visualiz`, `exibir`, `mostrar` → Célula de "Visualizador"

**Fallback**: Se nenhuma palavra-chave for encontrada, cria uma célula genérica.

## Fluxo de Interação

```
1. Usuário digita intenção no chat
   ↓
2. Frontend envia POST /api/chat/processar
   ↓
3. Backend analisa intenção (keywords matching)
   ↓
4. Backend seleciona tipo de célula apropriado
   ↓
5. Backend cria célula com fragmento de memória
   ↓
6. Backend retorna resposta + dados da célula
   ↓
7. Frontend exibe resposta no chat
   ↓
8. Frontend emite evento para adicionar célula ao notebook
   ↓
9. Célula aparece no notebook para edição
```

## Como Usar

### 1. Iniciar o Backend
```bash
cd backend
./start.sh
# Ou manualmente:
python3 -m app.main
```

O backend estará disponível em: `http://localhost:5051`

### 2. Inicializar Dados Seed
```bash
curl -X POST http://localhost:5051/api/seed-data
```

### 3. Criar um Usuário
```bash
curl -X POST http://localhost:5051/api/usuarios/registrar \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Usuario Teste",
    "email": "teste@scareverse.com"
  }'
```

Anote o `id` retornado.

### 4. Iniciar o Frontend
```bash
cd cockpit-vue
npm run dev
```

O frontend estará disponível em: `http://localhost:5173`

### 5. Interagir com o Chat
1. Abra o navegador em `http://localhost:5173`
2. O chat IA estará visível no topo da página
3. Digite uma intenção, por exemplo: "Criar um sistema de login"
4. A IA processará e criará uma célula apropriada
5. A célula aparecerá no notebook abaixo

## Exemplos de Uso

### Exemplo 1: Criar Memória
```
Usuário: "Memorizar os requisitos do projeto"
IA: Cria célula de "Memória de Conversação"
```

### Exemplo 2: Executar Código
```
Usuário: "Executar um script Python para análise de dados"
IA: Cria célula de "Executor de Scripts" com template Python
```

### Exemplo 3: Editar Artefato
```
Usuário: "Editar o componente de login"
IA: Cria célula de "Editor de Artefatos"
```

## Configuração

### Portas
- **Backend**: 5051 (configurável em `backend/app/config.py`)
- **Frontend**: 5173 (configurável em `cockpit-vue/vite.config.js`)

Veja [PORTS_CONFIGURATION.md](./PORTS_CONFIGURATION.md) para detalhes completos.

### Usuário Padrão
O componente usa localStorage para armazenar o ID do usuário:
- Chave: `scareverse_user_id`
- Valor: UUID do usuário registrado

## Testes Realizados

### ✅ Testes de Compilação
- [x] Backend compila sem erros
- [x] Frontend builda sem erros
- [x] Imports corretos nos componentes

### ✅ Testes de API
- [x] Endpoint `/api/chat/processar` responde
- [x] Criação de célula funciona
- [x] Parsing de intenções funciona
- [x] Validação de usuário funciona

### ✅ Testes de Integração
- [x] Chat exibe mensagens corretamente
- [x] Células criadas aparecem no notebook
- [x] Indicador de loading funciona
- [x] Sugestões de intenção funcionam

## Limitações Conhecidas (Current Implementation)

1. **Parsing Simples**: Usa matching de palavras-chave, não IA generativa real
2. **Sem Contexto**: Cada mensagem é processada independentemente
3. **Sem Decomposição Automática**: Cria apenas uma célula por intenção
4. **Sem Histórico Persistente**: Mensagens do chat não são salvas
5. **Usuário Fixo**: Usa ID armazenado em localStorage

## Próximas Etapas (Etapa 2+)

### Prioridade Alta
- [ ] Integrar com modelo de IA generativa (OpenAI/Anthropic/Claude)
- [ ] Implementar decomposição automática de intenções complexas
- [ ] Adicionar contexto de conversação (histórico)
- [ ] Persistir histórico de chat

### Prioridade Média
- [ ] Implementar sistema de sessões explícitas
- [ ] Adicionar suporte a workflows YAML
- [ ] Melhorar sugestões baseadas em histórico
- [ ] Adicionar visualização de mapas de intenção

### Prioridade Baixa
- [ ] Sistema de autenticação completo
- [ ] Chat em tempo real via WebSocket
- [ ] Suporte a múltiplos usuários simultâneos
- [ ] Avatar e personalização do mascote

## Estrutura de Arquivos Modificados/Criados

```
cockpit-vue/
├── src/
│   ├── components/
│   │   └── ChatIA.vue              [NOVO]
│   └── App.vue                     [MODIFICADO]
└── vite.config.js                  [MODIFICADO]

backend/
├── app/
│   ├── models.py                   [MODIFICADO - novos modelos]
│   ├── chat_router.py               [MODIFICADO - novo endpoint]
│   └── config.py                   [MODIFICADO - porta]
└── start.sh                        [MODIFICADO - mensagens]

[RAIZ]/
├── CHAT_IA_INTEGRATION.md          [NOVO]
└── PORTS_CONFIGURATION.md          [NOVO]
```

## Referências

- [ScareVerse_Project.md](./ScareVerse_Project.md) - Documento principal do projeto
- [Current Implementation_PROXIMOS_PASSOS.md](../REFACTORING_SUMMARY.md) - Roadmap completo
- [Issue #40](https://github.com/Scare-Inc/ScareVerseLab/issues/40) - Issue original
- [PR #39](https://github.com/Scare-Inc/ScareVerseLab/pull/39) - PR base do Current Implementation

---

**Status**: ✅ Etapa 1 Completa - Chat IA integrado com lógica básica  
**Data**: 2025-10-30  
**Próxima Etapa**: Integração com IA generativa real
