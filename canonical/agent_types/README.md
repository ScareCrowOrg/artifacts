# Agent Types - Tipos de Agentes

Este diretório contém as definições JSON dos tipos de agentes (agent types) disponíveis no sistema ScareVerse. Agent types definem os blueprints para agentes que processam diferentes tipos de tarefas.

(This directory contains JSON definitions for agent types available in the ScareVerse system. Agent types define the blueprints for agents that process different task types.)

## Índice

### Arquivos
- `agent-type-ollama-llm-processor-v1.json` - Definição do tipo de agente para processamento LLM via Ollama
- `agent-type-workflow-orchestrator-v1.json` - Definição do tipo de agente para orquestração de workflows
- `.gitkeep` - Arquivo para manter o diretório no Git

### Subdiretórios
Este diretório não possui subdiretórios.

## Visão Geral

Agent Types são templates reutilizáveis que definem:
- **Capacidades**: Quais operações o agente pode executar
- **Configuração**: Parâmetros necessários para instanciar o agente
- **Modelo**: Qual modelo de IA será utilizado (ex: ollama/mistral, ollama/deepseek-coder)
- **Comportamento**: Como o agente processa inputs e gera outputs

### Agent Types Disponíveis

#### 1. Ollama LLM Processor
**Arquivo**: `agent-type-ollama-llm-processor-v1.json`

Tipo de agente responsável por processar requisições de linguagem natural usando modelos Ollama locais.

**Características**:
- Processa textos e queries usando LLMs locais
- Suporta múltiplos modelos Ollama (mistral, phi, deepseek-coder)
- Configuração de temperatura e parâmetros customizáveis

#### 2. Workflow Orchestrator
**Arquivo**: `agent-type-workflow-orchestrator-v1.json`

Tipo de agente responsável por orquestrar workflows complexos coordenando outros agentes.

**Características**:
- Coordena execução sequencial ou paralela de agentes
- Gerencia fluxo de dados entre agentes
- Suporta decisões condicionais baseadas em resultados

## Estrutura JSON de Agent Type

```json
{
  "id": "unique-agent-type-id",
  "name": "Agent Type Name",
  "version": "1.0.0",
  "description": "Description of what this agent type does",
  "capabilities": ["capability1", "capability2"],
  "config_schema": {
    "model": "string",
    "temperature": "number",
    "other_params": "..."
  }
}
```

## Uso

Agent types são utilizados para criar instâncias de agentes no diretório `../agents/`:

```python
# Exemplo de criação de agente a partir de um tipo
from backend.app.services.agent_factory import create_agent

agent = create_agent(
    agent_type_id="agent-type-ollama-llm-processor-v1",
    config={
        "model": "ollama/mistral",
        "temperature": 0.7
    }
)
```

## Criando Novos Agent Types

Para criar um novo agent type:

1. Defina a estrutura JSON seguindo o schema acima
2. Adicione o arquivo neste diretório com nomenclatura: `agent-type-{name}-v{version}.json`
3. Documente as capacidades e configurações
4. Atualize este README com a descrição do novo tipo
5. Implemente o handler correspondente no código backend

## Relacionado

- [../agents/](../agents/) - Instâncias de agentes baseadas nestes tipos
- [../workflows/](../workflows/) - Workflows que utilizam estes agentes
- [../../runtime/](../../runtime/) - Dados de runtime de execuções de agentes
- [Artefatos README](../../README.md) - Documentação do sistema de artefatos

## Notas

- Todos os IDs devem ser únicos no sistema
- Versões seguem SemVer (Semantic Versioning)
- Mudanças breaking requerem nova versão major
- Novos agent types devem ser compatíveis com o orquestrador existente

---

**Última Atualização**: 15 de Novembro de 2024  
**Versão**: 1.0 (Implementação inicial com 2 tipos de agentes)
