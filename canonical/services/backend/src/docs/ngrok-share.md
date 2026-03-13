---
processed: true
processed_date: 2025-12-09
themes:
  - ngrok
  - file-sharing
  - api
modules:
  - backend
code_verified: true
dead_docs_found: false
generated_docs:
  - docs/official/backend/api/ngrok-file-sharing.md
---
# Compartilhamento de Arquivos via Ngrok

## Visão Geral

O módulo de compartilhamento via ngrok permite que usuários compartilhem temporariamente arquivos e pastas do repositório através de uma URL pública gerada dinamicamente. Esta funcionalidade é útil para colaboração remota, demonstrações e compartilhamento de artefatos com agentes externos.

## Arquitetura

### Componentes

1. **Backend Router** (`ngrok_router.py`): Gerencia a lógica de compartilhamento
2. **Pasta Temporária** (`/tmp/scareverse-share`): Armazena cópias dos arquivos compartilhados
3. **HTTP Server**: Servidor Python simples que serve a pasta temporária
4. **Ngrok**: Cria túnel público para o servidor HTTP local

### Fluxo de Funcionamento

```
1. Usuário seleciona arquivos no frontend
2. Frontend envia requisição POST /api/share/start
3. Backend:
   a. Valida e sanitiza caminhos dos arquivos
   b. Cria pasta temporária /tmp/scareverse-share
   c. Copia arquivos selecionados para pasta temporária
   d. Inicia servidor HTTP na porta 9000
   e. Inicia túnel ngrok
   f. Retorna URL pública para o frontend
4. Arquivos ficam acessíveis via URL pública
5. Usuário pode adicionar/remover arquivos dinamicamente
6. Usuário encerra compartilhamento quando terminar
```

## API Endpoints

### GET /api/share/status

Retorna o status atual do compartilhamento.

**Response:**
```json
{
  "status": "ok",
  "active": true,
  "url": "https://xyz123.ngrok.io",
  "shared_files": [
    "backend/app/main.py",
    "docs/README.md"
  ]
}
```

### POST /api/share/start

Inicia um novo compartilhamento.

**Request:**
```json
{
  "files": [
    "backend/app/main.py",
    "docs/README.md"
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Share started successfully",
  "url": "https://xyz123.ngrok.io",
  "shared_files": [
    "backend/app/main.py",
    "docs/README.md"
  ],
  "errors": null
}
```

### POST /api/share/add

Adiciona arquivos a um compartilhamento ativo.

**Request:**
```json
{
  "files": [
    "backend/app/models.py"
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Added 1 files to share",
  "url": "https://xyz123.ngrok.io",
  "shared_files": [
    "backend/app/main.py",
    "docs/README.md",
    "backend/app/models.py"
  ],
  "added": [
    "backend/app/models.py"
  ],
  "errors": null
}
```

### POST /api/share/remove

Remove arquivos de um compartilhamento ativo.

**Request:**
```json
{
  "files": [
    "backend/app/main.py"
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Removed 1 files from share",
  "url": "https://xyz123.ngrok.io",
  "shared_files": [
    "docs/README.md",
    "backend/app/models.py"
  ],
  "removed": [
    "backend/app/main.py"
  ],
  "errors": null
}
```

### POST /api/share/stop

Encerra o compartilhamento ativo.

**Response:**
```json
{
  "status": "ok",
  "message": "Share stopped successfully"
}
```

## Segurança

### Validações Implementadas

1. **Path Traversal Protection**: Todos os caminhos são validados usando `validate_and_sanitize_path()` para prevenir acesso fora do repositório
2. **Whitelist de Extensões**: Apenas arquivos com extensões permitidas podem ser compartilhados
3. **Cópias Isoladas**: Arquivos são copiados para pasta temporária separada, evitando exposição do repositório completo
4. **Controle de Acesso**: Apenas arquivos explicitamente selecionados são compartilhados
5. **Limpeza Automática**: Pasta temporária é limpa ao encerrar compartilhamento

### Limitações de Segurança

- **Atenção**: URLs ngrok são públicas e acessíveis por qualquer pessoa com o link
- **Recomendação**: Não compartilhe arquivos com informações sensíveis (credenciais, tokens, etc.)
- **Duração**: Mantenha compartilhamentos ativos apenas pelo tempo necessário
- **Revisão**: Revise sempre a lista de arquivos antes de iniciar compartilhamento

## Requisitos

### Instalação do Ngrok

O ngrok deve estar instalado e disponível no PATH do sistema:

```bash
# Ubuntu/Debian
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# macOS
brew install ngrok

# Verificar instalação
ngrok version
```

### Autenticação Ngrok (Opcional)

Para funcionalidades avançadas, autentique o ngrok:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

## Uso no Frontend

O frontend (cockpit-vue) fornece interface visual para:

1. **Selecionar Arquivos**: Checkboxes ao lado de cada arquivo
2. **Iniciar Compartilhamento**: Botão "Compartilhar via ngrok"
3. **Gerenciar Compartilhamento**: Modal com URL e controles
4. **Adicionar/Remover Arquivos**: Botões no modal de gerenciamento
5. **Copiar URL**: Botão para copiar URL para área de transferência
6. **Encerrar**: Botão para parar compartilhamento

## Casos de Uso

### 1. Demonstração para Cliente

Compartilhe rapidamente artefatos específicos com cliente externo sem necessidade de configurar acesso ao repositório completo.

### 2. Colaboração com Agente Remoto

Permita que agentes IA remotos acessem arquivos específicos para análise ou processamento.

### 3. Revisão de Código

Compartilhe arquivos com revisores externos de forma temporária e controlada.

### 4. Testes de Integração

Exponha arquivos para ferramentas de teste externas que precisam acessar recursos via HTTP.

## Troubleshooting

### Ngrok não encontrado

**Erro**: `"ngrok not installed. Please install ngrok first."`

**Solução**: Instale o ngrok conforme instruções na seção Requisitos.

### Falha ao iniciar túnel

**Erro**: `"Failed to start ngrok tunnel"`

**Possíveis causas**:
- Porta 4040 (API do ngrok) já em uso
- Porta 9000 (HTTP server) já em uso
- Limite de túneis simultâneos atingido (conta gratuita ngrok)

**Solução**:
- Verifique processos usando as portas: `lsof -i :9000` e `lsof -i :4040`
- Encerre compartilhamentos existentes antes de criar novo
- Considere upgrade da conta ngrok para mais túneis

### Arquivo não encontrado

**Erro**: Arquivo não aparece na URL pública

**Solução**:
- Verifique se arquivo foi realmente adicionado ao compartilhamento
- Confirme estrutura de pastas na URL: `https://xyz.ngrok.io/path/to/file.ext`
- Verifique logs do backend para erros de cópia

## Logs

O módulo registra eventos importantes:

- Início/fim de compartilhamento
- Arquivos adicionados/removidos
- Erros de validação ou operação

Logs podem ser consultados nos logs do backend FastAPI.

## Limitações Conhecidas

1. **Single Share**: Apenas um compartilhamento ativo por vez
2. **Porta Fixa**: HTTP server sempre usa porta 9000
3. **Sem Autenticação**: URLs são públicas sem senha
4. **Sem TTL Automático**: Compartilhamento continua até ser manualmente encerrado
5. **Dependência Externa**: Requer ngrok instalado e funcionando

## Melhorias Futuras

- [ ] Múltiplos compartilhamentos simultâneos
- [ ] TTL configurável para auto-expiração
- [ ] Autenticação básica nas URLs
- [ ] Suporte a outras ferramentas de túnel (localtunnel, expose, etc.)
- [ ] Integração com nginx ao invés de Python HTTP server
- [ ] Logs de acesso aos arquivos compartilhados
- [ ] Notificações quando URLs são acessadas

## Referências

- [Documentação Ngrok](https://ngrok.com/docs)
- [Documentação FastAPI](https://fastapi.tiangolo.com/)
- [Python http.server](https://docs.python.org/3/library/http.server.html)
