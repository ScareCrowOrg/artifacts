---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - ai
  - chat
  - features
modules:
  - backend
  - ai-integration
code_verified: true
dead_docs_found: false
---
# Melhorias do Chat IA - Novembro 2025

## Visão Geral

Este documento descreve as melhorias implementadas no Chat IA do ScareVerse em novembro de 2025, incluindo validação dinâmica de modelos, melhorias visuais e controle de classificação de intenção.

## 1. Validação Dinâmica de Modelos IA

### Problema Anterior
O endpoint `/api/chat/processar` validava modelos usando arrays fixos do `.env` (`OLLAMA_MODELS`, `GEMINI_MODELS`), ignorando os artefatos JSON registrados no banco de dados.

### Solução Implementada
**Backend (`chat_router.py`)**:
- Validação de modelos agora consulta os artefatos JSON registrados no banco (`modelos_ia`)
- Verifica se o modelo está ativo antes de permitir uso
- Mantém fallback para arrays do `.env` quando banco está vazio
- Determina automaticamente o provider (ollama/gemini) baseado no modelo

**Benefícios**:
- ✅ Modelos podem ser gerenciados via API sem alterar `.env`
- ✅ Suporte a novos modelos sem reiniciar o backend
- ✅ Controle fino de modelos ativos/inativos
- ✅ Validação consistente entre frontend e backend

**Código Relevante**:
```python
# Get available models from database
modelos_disponiveis = db.find_many("modelos_ia", ModeloIA, is_canonical=True)
modelos_ativos = [m for m in modelos_disponiveis if m.ativo]

# Check if the requested model exists and is active
modelo_encontrado = None
for m in modelos_ativos:
    if m.modeloId.lower() == modelo.lower():
        modelo_encontrado = m
        break
```

## 2. Melhorias Visuais das Mensagens

### Problema Anterior
- Mensagens do usuário usavam `opacity: 0.15`, resultando em texto muito claro e difícil de ler
- Baixo contraste dificultava acessibilidade
- Indicadores de células criadas também tinham baixa visibilidade

### Solução Implementada
**Frontend (`ChatIA.vue`)**:

**Mensagens do Usuário**:
```css
.message.user {
  background: rgba(98, 0, 234, 0.08);
  border: 1px solid rgba(98, 0, 234, 0.2);
  margin-left: var(--space-lg);
}
```

**Células Criadas**:
```css
.celula-created {
  margin-top: var(--space-sm);
  padding: var(--space-xs);
  background: rgba(0, 200, 0, 0.08);
  border: 1px solid rgba(0, 200, 0, 0.2);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-sm);
  color: rgba(0, 150, 0, 0.9);
}
```

**Benefícios**:
- ✅ Melhor contraste e legibilidade
- ✅ Acessibilidade aprimorada (WCAG)
- ✅ Diferenciação clara entre mensagens de usuário e IA
- ✅ Feedback visual mais claro para células criadas

## 3. Controle de Classificação de Intenção

### Problema Anterior
O chat sempre tentava classificar automaticamente a intenção da mensagem (ação, célula, etc.) usando o LangGraph orchestrator, mesmo quando o usuário queria apenas conversar.

### Solução Implementada

**Frontend (`ChatIA.vue`)**:
- Novo checkbox: "🎯 Classificar intenção e executar ações (criar células, etc.)"
- Texto de ajuda: "Quando desmarcado, funciona apenas como conversa direta com o modelo."
- Estado padrão: `enableIntentionClassification: true`
- Checkbox incluído no request: `classificarIntencao: this.enableIntentionClassification`

**Backend (`chat_router.py` e `models.py`)**:
- Novo campo no request: `classificarIntencao: bool = Field(default=True)`
- Lógica condicional:
  - **Se `classificarIntencao == false`**: Pula o orquestrador e vai direto para o LLM (Ollama ou Gemini)
  - **Se `classificarIntencao == true`**: Usa o LangGraph orchestrator para classificar intenção e executar ações

**Código Relevante**:
```python
if not request.classificarIntencao:
    # Direct conversation mode - skip orchestrator
    if usar_ollama:
        resposta_base = await processar_chat_com_ollama(...)
    else:
        resposta_base = await processar_chat_com_gemini(...)
    celula_criada = None
else:
    # Use orchestrator with intention classification
    orchestrator = get_orchestrator()
    resultado = orchestrator.process(...)
```

**Benefícios**:
- ✅ Usuário controla quando quer criar células vs. apenas conversar
- ✅ Performance melhor em modo conversa direta (pula orquestrador)
- ✅ Flexibilidade para diferentes casos de uso
- ✅ Experiência mais previsível

## 4. Tree View de Arquivos

### Problema Anterior
O botão "🌳 Árvore" não exibia uma tree view hierárquica adequada - apenas mudava a forma de exibição dos arquivos sem mostrar subdiretórios.

### Causa Raiz
- `FileTree.vue` usava endpoint `/api/listar_arquivos` que retornava apenas arquivos
- Endpoint não incluía diretórios na resposta
- Estrutura hierárquica não era construída

### Solução Implementada

**Backend (`file_ops_router.py`)**:
- Endpoint `/api/listar_arquivos` agora retorna diretórios (com `/` no final) além de arquivos
- Permite navegação adequada na interface

```python
if os.path.isdir(item_path):
    # Add directory with trailing slash
    arquivos.append(item + '/')
elif os.path.isfile(item_path):
    # Check if has allowed extension
    is_valid_ext, _ = validate_filename_extension(item)
    if is_valid_ext:
        arquivos.append(item)
```

**Frontend (`FileTree.vue`)**:
- Agora usa endpoint `/api/tree` com formato flat
- Nova função `buildTreeFromFlatList()` constrói hierarquia correta
- Suporta navegação em múltiplos níveis de subdiretórios
- Removida lógica de carregamento lazy (desnecessária com endpoint tree)

**Código Relevante**:
```javascript
async loadTree(path = '') {
  // Use the tree endpoint which returns proper hierarchical structure
  const url = `${ENDPOINTS.tree}?format=flat&include_hidden=false`
  const response = await apiService.fetch(url)
  const data = await response.json()
  
  // Build tree from flat list
  this.tree = this.buildTreeFromFlatList(items)
}
```

**Benefícios**:
- ✅ Tree view funcional com hierarquia completa
- ✅ Navegação visual em subdiretórios
- ✅ Expand/collapse de diretórios
- ✅ Consistente com endpoint `/tree` existente

## Endpoints Atualizados

### POST `/api/chat/processar`

**Request**:
```json
{
  "intencao": "string - Intenção do usuário",
  "assignee_id": "string - UUID do usuário",
  "historico": [
    {"role": "user|assistant", "content": "string"}
  ],
  "modelo": "string - ID do modelo (ex: mistral, deepseek-coder)",
  "classificarIntencao": "boolean - Se deve classificar intenção (default: true)"
}
```

**Validação de Modelo**:
1. Consulta banco de dados para modelos ativos
2. Verifica se `modeloId` corresponde ao modelo solicitado
3. Fallback para arrays do `.env` se banco vazio
4. Retorna erro 400 se modelo não encontrado ou inativo

### GET `/api/listar_arquivos?pasta={path}`

**Response**:
```json
{
  "status": "ok",
  "arquivos": [
    "subdir/",      // Diretório (com trailing slash)
    "file.txt"      // Arquivo
  ],
  "pasta": "path"
}
```

### GET `/api/tree?format=flat&include_hidden=false`

**Response**:
```json
{
  "status": "ok",
  "format": "flat",
  "root": "/path/to/root",
  "data": [
    "dir1/",
    "dir1/subdir/",
    "dir1/file.txt",
    "file.txt"
  ]
}
```

## Testes Recomendados

### 1. Validação de Modelos
- [ ] Testar com modelo registrado no banco
- [ ] Testar com modelo não registrado
- [ ] Testar com modelo inativo
- [ ] Verificar fallback para `.env`

### 2. Cores e Acessibilidade
- [ ] Verificar contraste das mensagens
- [ ] Testar com diferentes temas
- [ ] Validar WCAG compliance
- [ ] Screenshot das cores atualizadas

### 3. Classificação de Intenção
- [ ] Testar com checkbox marcado (cria células)
- [ ] Testar com checkbox desmarcado (conversa direta)
- [ ] Verificar performance em modo direto
- [ ] Validar resposta do LLM em ambos modos

### 4. Tree View
- [ ] Verificar visualização hierárquica
- [ ] Testar expand/collapse de diretórios
- [ ] Navegar em múltiplos níveis
- [ ] Comparar com modo lista

## Configuração

**Backend (.env)**:
```bash
# Modelos padrão (fallback se banco vazio)
OLLAMA_MODELS=mistral,deepseek,phi
GEMINI_MODELS=gemini
```

**Frontend**:
Nenhuma configuração adicional necessária. O componente ChatIA carrega automaticamente:
1. Modelos disponíveis via `/api/modelos-ia/listar`
2. Agrupa por tipo (local/cloud)
3. Seleciona primeiro modelo disponível por padrão

## Próximos Passos

1. **Testes End-to-End**: Validar fluxo completo com Playwright
2. **Documentação**: Atualizar guias de usuário com novas funcionalidades
3. **Performance**: Monitorar tempo de resposta em modo direto vs. orquestrador
4. **UX**: Coletar feedback sobre cores e usabilidade do checkbox
5. **Tree View**: Adicionar ícones específicos por tipo de arquivo

## Referências

- [Chat IA Integration](./CHAT_IA_INTEGRATION.md)
- [Model Selection Guide](./MODEL_SELECTION_GUIDE.md)
- [LangChain/LangGraph Implementation](./LANGCHAIN_LANGGRAPH_IMPLEMENTATION.md)
- [Backend README](../../README.md)
- [Components README](../../../cockpit-vue/src/components/README.md)
