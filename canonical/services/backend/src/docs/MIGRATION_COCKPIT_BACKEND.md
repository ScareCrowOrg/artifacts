---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - migration
  - cockpit
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Migração do Cockpit Backend

**Data**: 2025-11-03  
**Status**: ✅ Completo

## Resumo

Os endpoints de operações de arquivo do `cockpit/backend` (Flask) foram migrados para o backend FastAPI principal (`/backend`). O módulo `cockpit/backend` foi completamente removido.

## Endpoints Migrados

Todos os endpoints agora estão disponíveis em `/api` no backend FastAPI:

### POST /api/salvar
Salva conteúdo de arquivo no sistema.

**Request Body:**
```json
{
  "folder": "scripts",
  "filename": "hello.js",
  "content": "console.log('Hello World');"
}
```

**Response:**
```json
{
  "status": "ok",
  "mensagem": "Arquivo salvo com sucesso",
  "caminho": "scripts/hello.js"
}
```

### GET /api/listar_arquivos
Lista arquivos em um diretório.

**Query Params:**
- `folder` (opcional): Pasta relativa para listar

**Response:**
```json
{
  "status": "ok",
  "arquivos": ["file1.txt", "file2.js"],
  "pasta": "scripts"
}
```

### GET /api/carregar_arquivo
Carrega conteúdo de um arquivo.

**Query Params:**
- `folder` (opcional): Pasta do arquivo (vazia para raiz)
- `filename` (obrigatório): Nome do arquivo

**⚠️ Importante**: O endpoint espera `folder` e `filename` como parâmetros **separados**, não um único parâmetro `path`. Esta é a especificação do contrato que deve ser respeitada pelo frontend.

**Exemplo Correto:**
```bash
GET /api/carregar_arquivo?folder=scripts&filename=hello.js
GET /api/carregar_arquivo?folder=&filename=README.md  # raiz
```

**Exemplo Incorreto (não usar):**
```bash
GET /api/carregar_arquivo?path=scripts/hello.js  # ❌ ERRADO
```

**Response:**
```json
{
  "status": "ok",
  "conteudo": "file content here...",
  "caminho": "scripts/hello.js"
}
```

**Fix Histórico (2025-11-04):** O frontend originalmente enviava um parâmetro `path` ao invés de `folder` + `filename`. Isso foi corrigido em `FileBrowserRefactored.vue` para respeitar o contrato do backend.

### POST /api/mover_item
Move arquivo ou pasta de origem para destino.

**Request Body:**
```json
{
  "source": "old_folder/file.txt",
  "destination": "new_folder/file.txt"
}
```

**Response:**
```json
{
  "status": "ok",
  "mensagem": "Item movido com sucesso",
  "origem": "old_folder/file.txt",
  "destino": "new_folder/file.txt"
}
```

## Endpoints Descontinuados

Os seguintes endpoints relacionados à integração com AutoHotkey foram descontinuados:

- `GET /status_ahk` - Verificar status do AutoHotkey
- `POST /ativar` - Ativar AutoHotkey
- `POST /captura` - Capturar conteúdo via AutoHotkey
- WebSocket connections para AutoHotkey

## Mudanças de Arquitetura

### Antes
- **Framework**: Flask + Flask-SocketIO
- **Porta**: 5052
- **Localização**: `/cockpit/backend/`
- **Servidor**: Werkzeug (development) / eventlet (production)

### Depois
- **Framework**: FastAPI
- **Porta**: 5051
- **Localização**: `/backend/`
- **Servidor**: Uvicorn
- **Router**: `/backend/app/file_ops_router.py`

## Compatibilidade

A migração mantém **compatibilidade total** com o comportamento original:
- Mesmos formatos de request/response
- Mesmas validações de segurança
- Mesma lógica de negócio
- Mesmos códigos de status HTTP

## Frontend

O frontend (`cockpit-vue`) foi atualizado automaticamente:
- Arquivo: `/cockpit-vue/src/config/endpoints.js`
- Todos os endpoints agora apontam para `/api/*` no backend FastAPI
- Nenhuma mudança necessária nos componentes (usam configuração centralizada)

## Segurança

As funções de validação foram mantidas e aprimoradas:
- `validate_and_sanitize_path()` - Previne path traversal
- `validate_filename_extension()` - Valida extensões permitidas
- `write_file_atomically()` - Garante escrita atômica
- Base path configurável via `SCAREFERA_LAB_DIR`

## Testes

Todos os testes existentes continuam passando:
```bash
cd backend
python -m pytest tests/ -v
```

## Módulos Removidos

Além do `cockpit/backend`, os seguintes módulos experimentais foram removidos:
- **lab/** - Laboratório experimental
- **electron-viewer/** - Visualizador Electron (experimental)

Estes módulos eram experimentais e foram descontinuados conforme decisão de arquitetura.

## Próximos Passos

1. ✅ Migração completa dos endpoints
2. ✅ Remoção de módulos experimentais
3. ✅ Atualização da documentação
4. [ ] Testes E2E com novos endpoints
5. [ ] Atualização de docker-compose (se necessário)

## Referências

- Issue: #[número da issue]
- PR: #[número do PR]
- Documentação do Backend: `/backend/README.md`
- Documentação do Frontend: `/cockpit-vue/README.md`
