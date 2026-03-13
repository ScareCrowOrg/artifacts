---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - api
  - llm
  - function-calling
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Function Calling para Documentos Grandes

## Visão Geral

Esta funcionalidade permite que o ChatOrchestrator processe documentos grandes de forma eficiente através do OpenAI Function Calling, evitando problemas de payload HTTP e otimizando o uso da janela de contexto do LLM.

## Como Funciona

### Arquitetura

```
Usuário
  ↓
  "Analise o arquivo docs/README.md"
  ↓
ChatOrchestrator.process_async()
  ↓
OpenAI API (com tools definidas)
  ↓
LLM decide chamar read_local_document
  ↓
Backend executa read_local_document("docs/README.md")
  ↓
Conteúdo do documento enviado ao LLM
  ↓
LLM processa e retorna resposta final
  ↓
Resposta retornada ao usuário
```

### Componentes

1. **document_tools.py**
   - `read_local_document(file_path)` - Lê arquivo local com validações
   - `get_read_document_tool_definition()` - Define ferramenta para OpenAI
   - `execute_tool_call(tool_name, arguments)` - Executa chamada de ferramenta

2. **openai_service.py**
   - `processar_com_function_calling()` - Loop de function calling
   - Suporta até 5 iterações de tool calls

3. **langgraph_orchestrator.py**
   - `process_async()` - Método assíncrono com function calling
   - `_process_with_function_calling()` - Lógica interna de processamento

## Uso

### Exemplo Básico

```python
from app.langgraph_orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# Processar com function calling (assíncrono)
result = await orchestrator.process_async(
    mensagem="Por favor, leia e resuma o arquivo docs/ARCHITECTURE.md",
    responsavel_id="user123",
    modelo="gpt-4o",  # Modelo OpenAI
    enable_function_calling=True
)

print(result["resposta"])
```

### Exemplo via API Endpoint

Se você tem um endpoint que usa o orchestrator:

```python
from fastapi import FastAPI, HTTPException
from app.langgraph_orchestrator import get_orchestrator

app = FastAPI()

@app.post("/chat/async")
async def chat_with_function_calling(
    mensagem: str,
    responsavel_id: str,
    modelo: str = "gpt-4o"
):
    orchestrator = get_orchestrator()
    
    try:
        result = await orchestrator.process_async(
            mensagem=mensagem,
            responsavel_id=responsavel_id,
            modelo=modelo,
            enable_function_calling=True
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Exemplo de Interação

**Entrada do usuário:**
```
"Revise o documento backend/app/config.py e me diga se há algum problema de segurança"
```

**Fluxo interno:**
1. LLM recebe a mensagem e decide chamar `read_local_document`
2. Backend lê o arquivo `backend/app/config.py`
3. Conteúdo do arquivo é enviado ao LLM
4. LLM analisa o código e identifica problemas
5. LLM retorna resposta final: "Encontrei os seguintes problemas..."

## Configuração

### Variáveis de Ambiente

```bash
# Tamanho máximo de arquivo (bytes)
MAX_DOCUMENT_SIZE_BYTES=10485760  # 10 MB

# API Key da OpenAI (necessária para function calling)
OPENAI_API_KEY=sk-...

# Modelo padrão OpenAI
OPENAI_DEFAULT_MODEL=gpt-4o
```

### Diretórios Permitidos

Por padrão, apenas estes diretórios podem ser acessados:

```python
ALLOWED_DOCUMENT_DIRS = [
    "backend/app",
    "backend/docs",
    "backend/tests",
    "docs",
    "scripts",
    "cockpit",
    "cockpit-vue"
]
```

Para modificar, edite `backend/app/document_tools.py`.

## Segurança

### Proteções Implementadas

1. **Path Traversal Prevention**
   - Paths são normalizados e validados
   - Tentativas de `../` são bloqueadas
   - Acesso restrito ao BASE_DIR

2. **Whitelist de Diretórios**
   - Apenas diretórios explicitamente permitidos
   - Previne acesso a arquivos sensíveis do sistema

3. **Limite de Tamanho**
   - Arquivos maiores que 10 MB são rejeitados por padrão
   - Previne consumo excessivo de memória

4. **Tratamento de Erros**
   - Erros são retornados como strings para o LLM
   - Logs detalhados para auditoria
   - Não expõe informações sensíveis ao usuário

### Exemplos de Bloqueios

```python
# ❌ Bloqueado: Path traversal
read_local_document("docs/../../../etc/passwd")
# Erro: "Security error: path traversal attack"

# ❌ Bloqueado: Diretório não permitido
read_local_document("/etc/hosts")
# Erro: "not in allowed directories"

# ❌ Bloqueado: Arquivo muito grande
read_local_document("large_video.mp4")
# Erro: "File too large"

# ✅ Permitido
read_local_document("docs/README.md")
```

## Limitações

### Modelos Suportados

- **OpenAI**: gpt-3.5-turbo, gpt-4o, gpt-4o-mini ✅
- **Ollama**: mistral, deepseek, phi ❌ (sem function calling)
- **Gemini**: gemini-2.5-flash ⚠️ (usa protocolo próprio de files.upload)

### Limites Técnicos

1. **Máximo de 5 iterações** de function calling por request
2. **Timeout de 60 segundos** por chamada à OpenAI
3. **10 MB de tamanho máximo** por documento
4. Apenas **arquivos de texto** são suportados (UTF-8 ou latin-1)

## Testes

### Executar Testes Unitários

```bash
cd backend
pytest tests/unit/test_document_tools.py -v
```

### Executar Testes de Integração

```bash
cd backend
pytest tests/integration/test_function_calling.py -v
```

### Cobertura de Testes

```bash
cd backend
pytest tests/unit/test_document_tools.py --cov=app.document_tools --cov-report=html
```

## Troubleshooting

### Problema: "OpenAI API Key não configurada"

**Solução:** Configure a variável de ambiente:
```bash
export OPENAI_API_KEY=sk-your-key-here
```

### Problema: "File not found"

**Solução:** Verifique se:
1. O path está correto (relativo ao BASE_DIR)
2. O arquivo existe no repositório
3. O diretório está em ALLOWED_DOCUMENT_DIRS

### Problema: "File too large"

**Solução:** 
1. Divida o arquivo em partes menores
2. Ou aumente MAX_DOCUMENT_SIZE_BYTES (cuidado com memória)

### Problema: "Maximum iterations reached"

**Solução:**
1. Verifique se o LLM está em loop infinito de tool calls
2. Simplifique a instrução do usuário
3. O limite é de 5 iterações para evitar loops

## Performance

### Métricas Esperadas

- **Latência adicional**: ~2-3 segundos por document read
- **Throughput**: Limitado pela API da OpenAI (RPM)
- **Memória**: ~10 MB por documento carregado

### Otimizações

1. **Cache de documentos** (futuro): Cachear documentos frequentemente acessados
2. **Chunking** (futuro): Dividir documentos grandes em chunks menores
3. **Streaming** (futuro): Retornar respostas parciais durante o processamento

## Roadmap

### Próximas Funcionalidades

- [ ] Suporte a múltiplos documentos em paralelo
- [ ] Cache de documentos lidos recentemente
- [ ] Suporte a documentos binários (PDF, DOCX)
- [ ] Integração com Gemini Files API
- [ ] Chunking automático para documentos muito grandes
- [ ] Streaming de respostas
- [ ] Análise de dependências entre documentos
- [ ] Versionamento de documentos

## Referências

- [OpenAI Function Calling Documentation](https://platform.openai.com/docs/guides/function-calling)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Async Documentation](https://fastapi.tiangolo.com/async/)

## Contribuindo

Para adicionar novas ferramentas (tools):

1. Defina a função em `document_tools.py`
2. Adicione a definição da tool no formato OpenAI
3. Registre no `execute_tool_call()`
4. Adicione testes em `test_document_tools.py`
5. Atualize esta documentação

## Licença

Este código faz parte do projeto ScareVerse e segue a mesma licença do projeto principal.
