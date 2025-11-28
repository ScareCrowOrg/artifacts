# Workflows - Fluxos de Trabalho

Este diretório contém as definições JSON de workflows (fluxos de trabalho) do sistema ScareVerse. Workflows orquestram sequências de operações envolvendo múltiplos agentes e processos.

(This directory contains JSON definitions for workflows in the ScareVerse system. Workflows orchestrate sequences of operations involving multiple agents and processes.)

## Índice

### Arquivos
Atualmente, este diretório está vazio e pronto para receber definições de workflows.

- `.gitkeep` - Arquivo para manter o diretório no Git (se presente)

### Subdiretórios
Este diretório não possui subdiretórios no momento.

## Visão Geral

Workflows no ScareVerse são definições declarativas de processos complexos que:
- **Orquestram Agentes**: Coordenam múltiplos agentes trabalhando em conjunto
- **Definem Fluxo de Dados**: Especificam como dados fluem entre etapas
- **Gerenciam Estado**: Mantêm contexto durante a execução
- **Suportam Decisões**: Incluem lógica condicional baseada em resultados

### Tipos de Workflows

1. **Sequenciais**: Etapas executadas em ordem linear
2. **Paralelos**: Múltiplas etapas executadas simultaneamente
3. **Condicionais**: Fluxo baseado em decisões dinâmicas
4. **Iterativos**: Loops e repetições baseadas em condições

## Estrutura de Workflow

### Estrutura JSON

```json
{
  "id": "unique-workflow-id",
  "name": "Workflow Name",
  "version": "1.0.0",
  "description": "O que este workflow faz",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "metadata": {
    "category": "data-processing|analysis|automation",
    "tags": ["tag1", "tag2"],
    "author": "author-name"
  },
  "input_schema": {
    "type": "object",
    "properties": {
      "input_param1": {"type": "string"},
      "input_param2": {"type": "number"}
    },
    "required": ["input_param1"]
  },
  "steps": [
    {
      "id": "step-1",
      "name": "Step Name",
      "type": "agent|function|condition|loop",
      "agent_id": "reference-to-agent",
      "config": {
        "param1": "value1"
      },
      "inputs": {
        "from": "workflow.input",
        "mapping": {
          "agent_param": "input_param1"
        }
      },
      "outputs": {
        "to": "step-1-output",
        "store_in_state": true
      },
      "error_handling": {
        "retry": 3,
        "on_failure": "continue|stop|fallback",
        "fallback_step": "step-fallback"
      }
    }
  ],
  "output_schema": {
    "type": "object",
    "properties": {
      "result": {"type": "string"},
      "metadata": {"type": "object"}
    }
  }
}
```

## Componentes de Workflow

### 1. Steps (Etapas)

#### Agent Step
Executa um agente específico:
```json
{
  "id": "analyze-code",
  "type": "agent",
  "agent_id": "agent-deepseek-code-analyzer-v1",
  "inputs": {
    "from": "workflow.input",
    "mapping": {
      "code": "source_code"
    }
  }
}
```

#### Function Step
Executa uma função customizada:
```json
{
  "id": "transform-data",
  "type": "function",
  "function": "backend.app.workflows.transforms.normalize_data",
  "inputs": {
    "from": "previous-step-output"
  }
}
```

#### Condition Step
Decisão condicional:
```json
{
  "id": "check-quality",
  "type": "condition",
  "condition": "step-1-output.quality_score > 0.8",
  "if_true": "step-high-quality",
  "if_false": "step-needs-improvement"
}
```

#### Loop Step
Iteração sobre coleção:
```json
{
  "id": "process-files",
  "type": "loop",
  "iterate_over": "workflow.input.files",
  "step": "process-single-file",
  "collect_results": true
}
```

### 2. Data Flow

#### Input Mapping
Define como inputs do workflow mapeiam para steps:
```json
{
  "inputs": {
    "from": "workflow.input",
    "mapping": {
      "agent_param": "workflow_input.field"
    }
  }
}
```

#### Output Handling
Define como outputs são armazenados:
```json
{
  "outputs": {
    "to": "step-output-key",
    "store_in_state": true,
    "expose_as": "workflow.output.result"
  }
}
```

### 3. Error Handling

```json
{
  "error_handling": {
    "retry": 3,
    "retry_delay": 1000,
    "on_failure": "fallback",
    "fallback_step": "error-handler-step",
    "log_errors": true
  }
}
```

## Exemplos de Workflows

### 1. Code Analysis Workflow

```json
{
  "id": "code-analysis-workflow-v1",
  "name": "Code Analysis Pipeline",
  "version": "1.0.0",
  "description": "Analisa código fonte usando múltiplos agentes",
  "input_schema": {
    "type": "object",
    "properties": {
      "repository_path": {"type": "string"},
      "files": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["repository_path", "files"]
  },
  "steps": [
    {
      "id": "analyze-code",
      "type": "agent",
      "agent_id": "agent-deepseek-code-analyzer-v1",
      "inputs": {
        "from": "workflow.input",
        "mapping": {
          "files": "files"
        }
      }
    },
    {
      "id": "generate-report",
      "type": "agent",
      "agent_id": "agent-mistral-general-ingestor-v1",
      "inputs": {
        "from": "analyze-code.output",
        "mapping": {
          "analysis_results": "results"
        }
      }
    }
  ]
}
```

### 2. Document Processing Workflow

```json
{
  "id": "document-ingestion-workflow-v1",
  "name": "Document Ingestion Pipeline",
  "version": "1.0.0",
  "description": "Processa e ingere documentos no sistema RAG",
  "steps": [
    {
      "id": "load-documents",
      "type": "function",
      "function": "backend.app.workflows.loaders.load_documents"
    },
    {
      "id": "chunk-documents",
      "type": "function",
      "function": "backend.app.workflows.chunking.chunk_documents"
    },
    {
      "id": "generate-embeddings",
      "type": "agent",
      "agent_id": "agent-mistral-general-ingestor-v1"
    },
    {
      "id": "store-vectors",
      "type": "function",
      "function": "backend.app.services.rag_service.store_vectors"
    }
  ]
}
```

## Execução de Workflows

### Via API Backend

```python
from backend.app.orchestrator.workflow_executor import execute_workflow

result = await execute_workflow(
    workflow_id="code-analysis-workflow-v1",
    inputs={
        "repository_path": "/path/to/repo",
        "files": ["file1.py", "file2.py"]
    }
)
```

### Via LangGraph Orchestrator

O sistema usa LangGraph para orquestração avançada:

```python
from backend.app.orchestrator.langgraph_orchestrator import LangGraphOrchestrator

orchestrator = LangGraphOrchestrator()
result = await orchestrator.run_workflow(
    workflow_id="code-analysis-workflow-v1",
    inputs={"repository_path": "/path/to/repo"}
)
```

## Monitoramento e Logs

### Execution Logs
Logs de execução são salvos em `../../runtime/`:
- Estado de cada step
- Inputs e outputs
- Erros e retries
- Tempo de execução

### Métricas
- Tempo total de execução
- Taxa de sucesso/falha
- Uso de recursos por step
- Latência por agente

## Criando Novos Workflows

### 1. Planejamento
- Identificar objetivo do workflow
- Listar agentes necessários
- Definir fluxo de dados
- Considerar tratamento de erros

### 2. Definição
- Criar arquivo JSON seguindo estrutura
- Definir schema de input/output
- Configurar steps e dependências
- Adicionar error handling

### 3. Validação
- Validar JSON contra schema
- Testar com dados de exemplo
- Verificar tratamento de erros
- Otimizar performance

### 4. Documentação
- Adicionar descrição clara
- Documentar inputs esperados
- Especificar outputs produzidos
- Atualizar este README

## Integração com Sistema

### Backend
- **Workflow Executor**: `backend/app/orchestrator/workflow_executor.py`
- **LangGraph Integration**: `backend/app/orchestrator/langgraph_orchestrator.py`
- **Step Handlers**: `backend/app/workflows/handlers/`

### Frontend
- Pode disparar workflows via API
- Monitora progresso via WebSocket
- Exibe resultados em UI

## Relacionado

- [../agents/](../agents/) - Agentes utilizados nos workflows
- [../agent_types/](../agent_types/) - Tipos de agentes disponíveis
- [../../runtime/](../../runtime/) - Logs e estado de execuções
- [Backend Orchestrator](../../../backend/app/orchestrator/) - Código do orquestrador
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)

## Versionamento

Workflows seguem SemVer:
- **Major**: Mudanças incompatíveis na estrutura
- **Minor**: Novos steps ou capabilities
- **Patch**: Correções e otimizações

## Notas

- IDs de workflows devem ser únicos
- Workflows devem referenciar agentes válidos
- Considerar idempotência de steps
- Implementar retry logic apropriado
- Documentar side effects de cada step
- Testar workflows end-to-end antes de produção
