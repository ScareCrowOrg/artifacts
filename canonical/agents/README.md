---
processed: true
processed_date: 2025-12-08
themes:
  - agents
  - instances
  - configuration
modules:
  - artifacts
  - agents
code_verified: true
dead_docs_found: false
---
# Agents - Agent Instances

Este diretório contém as configurações JSON de agentes individuais instanciados no sistema ScareVerse. Cada agente é uma instância concreta de um agent type, configurado para executar tarefas específicas.

**Pydantic Model**: `backend/app/models/agents.py::Agent`

(This directory contains JSON configurations for individual agents instantiated in the ScareVerse system. Each agent is a concrete instance of an agent type, configured to execute specific tasks.)

## Índice

### Arquivos
- `agent-deepseek-code-analyzer-v1.json` - Agente especializado em análise de código usando DeepSeek
- `agent-mistral-general-ingestor-v1.json` - Agente de ingestão geral usando Mistral
- `agent-phi-task-executor-v1.json` - Agente executor de tarefas usando Phi
- `main-workflow-orchestrator-v1.json` - Agente orquestrador principal de workflows
- `.gitkeep` - Arquivo para manter o diretório no Git

### Subdiretórios
Este diretório não possui subdiretórios.

## Visão Geral

Agentes são instâncias configuradas de agent types que executam tarefas específicas no sistema. Cada agente possui:
- **ID único**: Identificador do agente no sistema
- **Agent Type**: Referência ao tipo base (blueprint) do agente
- **Configuração**: Parâmetros específicos da instância
- **Modelo**: Modelo de IA atribuído (ex: ollama/deepseek-coder)
- **Metadados**: Versão, descrição, capabilities

### Agentes Disponíveis

#### 1. DeepSeek Code Analyzer
**Arquivo**: `agent-deepseek-code-analyzer-v1.json`

Agente especializado em análise de código-fonte, detecção de padrões e sugestões de melhorias.

**Capabilities**:
- Análise estática de código
- Detecção de code smells
- Sugestões de refatoração
- Identificação de bugs potenciais

**Modelo**: `ollama/deepseek-coder`

#### 2. Mistral General Ingestor
**Arquivo**: `agent-mistral-general-ingestor-v1.json`

Agente responsável por ingestão e processamento de documentos e conteúdo textual geral.

**Capabilities**:
- Processamento de documentos
- Extração de informações
- Categorização de conteúdo
- Geração de resumos

**Modelo**: `ollama/mistral`

#### 3. Phi Task Executor
**Arquivo**: `agent-phi-task-executor-v1.json`

Agente executor de tarefas gerais e assistente conversacional.

**Capabilities**:
- Execução de tarefas instruídas
- Assistência conversacional
- Geração de respostas contextualizadas
- Processamento de queries

**Modelo**: `ollama/phi`

#### 4. Main Workflow Orchestrator
**Arquivo**: `main-workflow-orchestrator-v1.json`

Agente orquestrador principal que coordena workflows complexos entre múltiplos agentes.

**Capabilities**:
- Orquestração de multi-agentes
- Gerenciamento de fluxo de trabalho
- Roteamento inteligente de tarefas
- Agregação de resultados

## Estrutura JSON de Agent

Baseado no modelo Pydantic `Agent` em `backend/app/models/agents.py`:

```json
{
  "id": "unique-agent-id",
  "name": "Agent Name",
  "description": "What this agent does",
  "agent_type_id": "reference-to-agent-type",
  "ia_model_id": "model-id-from-ai-model",
  "persona_definitions": {
    "tone": "technical",
    "verbosity": "concise"
  },
  "agent_specific_config": {
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "is_active": true,
  "version": "1.0.0",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp"
}
```

**Key Fields** (from Agent Pydantic model):
- `agent_type_id` - UUID of the canonical AgentType
- `ia_model_id` - The `modelId` from AIModel (e.g., 'mistral', 'deepseek-coder')
- `persona_definitions` - Persona characteristics (system_prompt, traits)
- `agent_specific_config` - Operational configurations
- `is_active` - Whether agent is available for processing

## Uso

Agentes são utilizados em workflows e podem ser invocados diretamente:

```python
# Exemplo de uso de agente
from backend.app.services.agent_manager import get_agent

# Carregar agente
agent = get_agent("agent-deepseek-code-analyzer-v1")

# Executar tarefa
result = await agent.execute({
    "task": "analyze_code",
    "code": "def example(): pass"
})
```

## Criando Novos Agentes

Para criar um novo agente:

1. Selecione o agent type apropriado de `../agent_types/`
2. Crie arquivo JSON com nomenclatura: `agent-{name}-{model}-v{version}.json`
3. Configure os parâmetros específicos:
   - ID único do agente
   - Referência ao agent type
   - Modelo de IA a ser usado
   - Parâmetros de configuração (temperature, max_tokens, etc.)
4. Documente as capabilities específicas desta instância
5. Teste o agente em ambiente de desenvolvimento
6. Atualize este README com descrição do novo agente

## Lifecycle Management

### Estado dos Agentes
- **Ativo**: Agente disponível para execução
- **Inativo**: Agente desabilitado temporariamente
- **Deprecated**: Agente mantido por compatibilidade, será removido

### Versionamento
- Agentes seguem versionamento independente dos agent types
- Mudanças de configuração podem incrementar versão minor
- Mudanças de modelo ou capabilities incrementam versão major

### Monitoramento
Dados de execução dos agentes são salvos em:
- `../../runtime/` - Logs de execução e estados
- Métricas de performance e uso

## Relacionado

- [../agent_types/](../agent_types/) - Tipos de agentes (blueprints)
- [../workflows/](../workflows/) - Workflows que utilizam estes agentes
- [../modelos_ia/](../modelos_ia/) - Modelos de IA disponíveis
- [../../runtime/](../../runtime/) - Dados de runtime de execuções
- [Backend Orchestrator](../../../backend/app/orchestrator/) - Código do orquestrador

## Notas

- Todos os IDs devem ser únicos no sistema
- Agentes devem referenciar agent types válidos
- Modelos devem estar disponíveis no Ollama ou provedor configurado
- Configurações sensíveis não devem estar em arquivos versionados
