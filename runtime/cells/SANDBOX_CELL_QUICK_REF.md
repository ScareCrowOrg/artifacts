# Células Sandbox - Referência Rápida

## 📋 Visão Geral

Referência rápida para o sistema estendido de células sandbox com runtime dinâmico, metadados avançados e controle de lifecycle.

> **📚 Documentação Modularizada**: Para conformidade com o Ruleset.md (limite de 500 linhas por arquivo), esta documentação foi reorganizada em múltiplos arquivos especializados no subdiretório `sandbox_guide/`.

**Documentação Oficial do Projeto**:
- [Análise de Gaps Detalhada](../../../docs/project/SANDBOX_CELLS_GAP_ANALYSIS.md)
- [Plano de Implementação](../../../docs/project/SANDBOX_CELLS_IMPLEMENTATION_PLAN.md)

---

## 📚 Documentação Completa

### **[📖 Guia Completo](./sandbox_guide/README.md)**
Índice principal com navegação para todos os documentos.

### Documentos Disponíveis

| Documento | Descrição |
|-----------|-----------|
| **[METADATA.md](./sandbox_guide/METADATA.md)** | Estrutura de metadados, campos obrigatórios/opcionais, categorias |
| **[ENVIRONMENTS.md](./sandbox_guide/ENVIRONMENTS.md)** | Fluxo de promoção, critérios por ambiente, lifecycle |
| **[ACCESS_CONTROL.md](./sandbox_guide/ACCESS_CONTROL.md)** | Visibilidade, permissões, controle de acesso granular |
| **[RUNTIME_CONFIG.md](./sandbox_guide/RUNTIME_CONFIG.md)** | Runtime dinâmico, microserviços, artefatos externos |
| **[DEPENDENCIES.md](./sandbox_guide/DEPENDENCIES.md)** | Gestão de dependências, schemas I/O, validação |
| **[QUALITY.md](./sandbox_guide/QUALITY.md)** | Métricas de qualidade, cobertura, linting, vulnerabilidades |
| **[API_REFERENCE.md](./sandbox_guide/API_REFERENCE.md)** | Referência completa de APIs REST |
| **[EXAMPLES.md](./sandbox_guide/EXAMPLES.md)** | Exemplos práticos completos |

---

## 🚀 Quick Start

### 1. Criar Célula Simples

```bash
curl -X POST /api/v1/celulas-sandbox \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nome": "Minha Primeira Célula",
    "descricao": "Script de processamento",
    "categoria": "codigo",
    "tipoCelulaId": "tipo-python-script",
    "visibilidade": "privado"
  }'
```

### 2. Executar Célula

```bash
curl -X POST /api/v1/celulas-sandbox/{id}/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "inputs": {"data": "2024-11-01"},
    "runtime": {"timeout": 600}
  }'
```

### 3. Promover para DEV

```bash
curl -X POST /api/v1/celulas-sandbox/{id}/promote \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "para": "dev",
    "comentarios": "Testes básicos passando"
  }'
```

---

## 📊 Resumo de Conceitos

### Categorias de Células

- **codigo** - Scripts (Python, JS, Go)
- **dados** - Datasets (CSV, Parquet)
- **config** - Configurações (YAML, ENV)
- **visualizacao** - Dashboards
- **workflow** - Pipelines/DAGs
- **teste** - Testes automatizados
- **documentacao** - Markdown, Jupyter
- **modelo_ml** - Modelos de ML
- **api** - API endpoints
- **template** - Templates

### Fluxo de Ambientes

```
SANDBOX → DEV → STAGING → PROD → CORE
(privado)  (equipe)  (pré-prod)  (produção)  (base)
```

### Níveis de Visibilidade

- **privado** - Apenas criador
- **equipe** - Time do criador
- **alianca** - Toda aliança
- **publico** - Todos usuários
- **core** - Sistema base (protegido)

### Critérios de Promoção (Resumo)

| Ambiente | Requisitos Principais |
|----------|----------------------|
| **SANDBOX** | Nenhum |
| **DEV** | Testes básicos, sem vulns críticas |
| **STAGING** | Code review, cobertura ≥60%, lint ≥80% |
| **PROD** | ≥2 aprovadores, E2E tests, security scan |
| **CORE** | 30 dias em prod, ≥10 usuários, comitê |

---

## 🔗 Schemas Relacionados

- [Schema Atual de Células](./SCHEMA.md)
- [Schema de Tipos Canônicos](../../canonicos/tipos_celula/SCHEMA.md)
- [Backend Models](../../../backend/app/models.py)

## 🔗 READMEs Relacionados

- [Artefatos README](../../README.md) - Visão geral do sistema
- [Runtime README](../README.md) - Artefatos runtime
- [Células README](./README.md) - Células instanciadas

---

**Última Atualização**: Novembro 2024  
**Versão**: 2.0 (Modularizado)  
**Status**: ✅ Conformidade com Ruleset.md (< 500 linhas)
