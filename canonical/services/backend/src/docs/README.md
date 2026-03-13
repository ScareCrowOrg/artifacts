---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - documentation
  - overview
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Backend Documentation

Este diretório contém a documentação do backend do ScareVerse, um sistema baseado em FastAPI para gerenciamento de artefatos, autenticação e integração com IA.

## Estrutura da Documentação

### 📁 [auth/](./auth/)
Documentação relacionada à autenticação e autorização:
- `AUTH_IMPLEMENTATION.md` - Implementação completa de OAuth2 com Google
- `E2E_AUTH_IMPLEMENTATION.md` - Testes end-to-end de autenticação
- `OAUTH_PR_SUMMARY.md` - Resumo da integração OAuth2
- `TOKEN_EXPIRATION_IMPLEMENTATION.md` - Implementação de expiração de tokens
- `IMPLEMENTATION_SUMMARY_AUTH.md` - Resumo geral da implementação de autenticação

### 📁 [chat-ia/](./chat-ia/)
Documentação sobre integrações de chat com IA:
- `CHAT_IA_INTEGRATION.md` - Integração do chat IA no Cockpit
- `OLLAMA_CHAT_INTEGRATION.md` - Integração com Ollama para IA local
- `LANGCHAIN_LANGGRAPH_IMPLEMENTATION.md` - Orquestração com LangChain e LangGraph
- `MODEL_SELECTION_GUIDE.md` - Guia de seleção de modelos de IA
- `QUICK_START_OLLAMA.md` - Início rápido com Ollama
- `QUICK_START_CHAT_IA.md` - Início rápido com Chat IA
- `IMPLEMENTATION_SUMMARY_OLLAMA.md` - Resumo da implementação Ollama
- `IMPLEMENTATION_SUMMARY_MODEL_SELECTION.md` - Resumo da seleção de modelos
- `IMPLEMENTATION_SUMMARY_ORCHESTRATION.md` - Resumo da orquestração

### 📄 Arquivos Principais
- `CANONICAL_BOOK_ARCHITECTURE.md` - Arquitetura de livros canônicos (reference-only books)
- `FUNCTION_CALLING.md` - Suporte a anexos de documentos grandes via Function Calling
- `BASE_DIR_GUIDELINES.md` - Guia de uso do BASE_DIR para paths de arquivos
- `IDEMPOTENT_CELL_GENERATION.md` - Geração idempotente de células
- `CANONICAL_CELL_CLEANUP.md` - Limpeza de células canônicas duplicadas
- `SECURITY_MIGRATION.md` - Migração de segurança e criptografia
- `ASYNC_MIGRATION_SURVEY.md` - Async migration survey and status
- `TEST_REMEDIATION_SESSION_REPORT.md` - Test remediation session report

### 📁 [api/](./api/)
Documentação de APIs e contratos:
- `API_CONTRACT_TESTS_IMPLEMENTATION.md` - Implementação de testes de contrato de API
- `INTEGRATION_TEST_ARCHITECTURE.md` - Arquitetura de testes de integração

## Arquivos Principais no Módulo Backend

- `README.md` - Documentação principal do backend (raiz do módulo backend)
- `requirements.txt` - Dependências Python
- `start.sh` - Script de inicialização
- `test_auth_flow.sh` - Script de teste do fluxo de autenticação
- `test_mvp1_flow.sh` - Script de teste do fluxo MVP1

## Estrutura do Código

```
backend/
├── app/           # Código-fonte da aplicação
├── docs/          # Documentação (este diretório)
├── scripts/       # Scripts utilitários
└── tests/         # Testes automatizados
```

## Links Úteis

- [README Principal do Projeto](../../README.md)
- [Documentação Oficial do Projeto](../../docs/official/SCAREVERSE_PROJECT.md)
- [Documentação Frontend (Cockpit Vue)](../../cockpit-vue/docs/)
- [Conceitos Arquivados](../../docs/archive/2025/12/concept/) (histórico)

## Como Contribuir

Ao adicionar ou modificar funcionalidades no backend:
1. Atualize a documentação correspondente neste diretório
2. Adicione testes apropriados em `backend/tests/`
3. Atualize este README se criar novas seções de documentação
4. Siga as diretrizes em [copilot_instructions.md](../../copilot_instructions.md)
