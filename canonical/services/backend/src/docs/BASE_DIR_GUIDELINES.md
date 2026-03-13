---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - configuration
  - filesystem
  - best-practices
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Diretrizes para Referência de Caminho de Arquivos no Backend

## Objetivo

Garantir que todos os módulos do backend utilizem uma referência centralizada e consistente para caminhos de arquivos, evitando problemas em diferentes ambientes (local, produção, testes, CI/CD).

## Regra Principal: Use BASE_DIR

**Sempre que qualquer módulo/router do backend precisar gravar, localizar ou fazer referência a arquivos**, use a variável `BASE_DIR` definida no `config.py` como referência base do repositório.

### ✅ Forma Correta

```python
from .config import BASE_DIR
import os

# Para construir caminhos relativos ao repositório
# BASE_DIR é um Path object, então converta para string ao usar os.path.join()
caminho_arquivo = os.path.join(str(BASE_DIR), 'models', 'meu_modelo.pt')
caminho_logs = os.path.join(str(BASE_DIR), 'backend', 'logs', 'app.log')
caminho_data = os.path.join(str(BASE_DIR), 'data', 'usuarios.json')
```

Ou usando `pathlib.Path` (recomendado):

```python
from .config import BASE_DIR

# BASE_DIR já é um Path object, use o operador /
caminho_arquivo = BASE_DIR / 'models' / 'meu_modelo.pt'
caminho_logs = BASE_DIR / 'backend' / 'logs' / 'app.log'
caminho_data = BASE_DIR / 'data' / 'usuarios.json'
```

### ❌ Formas Incorretas

**NÃO defina caminhos absolutos:**
```python
# ERRADO - caminho absoluto hardcoded
caminho = "/home/runner/work/ScareVerseLab/ScareVerseLab/backend/backend.log"
```

**NÃO calcule paths individualmente em cada módulo:**
```python
# ERRADO - cada módulo calculando BASE_DIR separadamente
base_path = os.getenv("BASE_DIR") or str(Path(__file__).parent.parent.parent)
```

**NÃO use caminhos relativos sem BASE_DIR:**
```python
# ERRADO - caminho relativo sem referência clara
caminho = "../../../models/meu_modelo.pt"
```

## Como BASE_DIR é Definido

No arquivo `backend/app/config.py`:

```python
from pathlib import Path
import os

# Base directory for all file operations (ScareFeraLab directory)
# This should be the root of the workspace/project
BASE_DIR = Path(os.getenv("BASE_DIR", Path(__file__).parent.parent.parent))
SCAREFERA_LAB_DIR = BASE_DIR  # Alias para compatibilidade
```

### Variável de Ambiente (Opcional)

Você pode sobrescrever `BASE_DIR` via variável de ambiente se necessário:

```bash
export BASE_DIR=/caminho/customizado/do/projeto
```

Isso é útil para:
- Testes automatizados
- Ambientes de CI/CD
- Containers Docker
- Ambientes de produção com estruturas diferentes

## Motivos para Esta Convenção

### 1. **Centralização**
Uma única fonte de verdade para o diretório raiz do projeto, facilitando manutenção.

### 2. **Rastreabilidade**
Fácil de identificar de onde vêm os caminhos de arquivos ao revisar código.

### 3. **Portabilidade**
Funciona em diferentes ambientes sem necessidade de mudanças:
- Local (Windows, Linux, macOS)
- Docker containers
- CI/CD pipelines
- Produção

### 4. **Evita Bugs Recorrentes**
Elimina problemas comuns como:
- Caminhos relativos quebrados ao executar de diretórios diferentes
- Paths hardcoded que não funcionam em outros ambientes
- Inconsistências entre módulos

### 5. **Compatibilidade com Agentes de IA**
Arquivos pequenos e modulares são mais fáceis de processar para agentes de IA. Esta convenção promove modularização sem duplicação de lógica de paths.

## Exemplos Práticos

### Salvando Modelos de IA

```python
from .config import BASE_DIR
import os

def salvar_modelo(nome_modelo: str, dados: bytes):
    # Diretório de modelos
    modelos_dir = os.path.join(BASE_DIR, 'models')
    
    # Garantir que o diretório existe
    os.makedirs(modelos_dir, exist_ok=True)
    
    # Caminho completo do arquivo
    caminho_modelo = os.path.join(modelos_dir, f"{nome_modelo}.pt")
    
    # Salvar
    with open(caminho_modelo, 'wb') as f:
        f.write(dados)
    
    return caminho_modelo
```

### Lendo Arquivos de Log

```python
from .config import BASE_DIR
from pathlib import Path

def ler_logs_backend(linhas: int = 100):
    # Caminho do log do backend
    log_path = BASE_DIR / 'backend' / 'backend.log'
    
    if not log_path.exists():
        return []
    
    with open(log_path, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
        return all_lines[-linhas:]
```

### Operações com Arquivos do Usuário

```python
from .config import BASE_DIR
from .utils import validate_and_sanitize_path

def salvar_arquivo_usuario(caminho_relativo: str, conteudo: str):
    # Validar e sanitizar o caminho (previne path traversal)
    is_valid, caminho_seguro, erro = validate_and_sanitize_path(
        str(BASE_DIR),
        caminho_relativo
    )
    
    if not is_valid:
        raise ValueError(f"Caminho inválido: {erro}")
    
    # Escrever arquivo
    with open(caminho_seguro, 'w', encoding='utf-8') as f:
        f.write(conteudo)
    
    return caminho_seguro
```

## Checklist de Conformidade

Ao criar ou revisar PRs que manipulam caminhos de arquivos, verifique:

- [ ] Importa `BASE_DIR` de `config.py`
- [ ] Não usa caminhos absolutos hardcoded
- [ ] Não calcula `BASE_DIR` localmente usando `__file__`
- [ ] Usa `os.path.join()` ou `Path` / para construir caminhos
- [ ] Valida/sanitiza paths de entrada de usuário
- [ ] Funciona corretamente em qualquer diretório de execução
- [ ] Inclui tratamento de erro para arquivos não encontrados

## Referências

- **Configuração**: `backend/app/config.py`
- **Utilitários**: `backend/app/utils.py` (funções de validação de paths)
- **Exemplos**: 
  - `backend/app/router.py` ✅
  - `backend/app/ngrok_router.py` ✅
  - `backend/app/file_ops_router.py` (após refatoração) ✅

## Suporte e Dúvidas

Para questões sobre implementação desta diretriz:
1. Consulte este documento
2. Revise exemplos nos routers mencionados
3. Abra uma issue com label `backend` e `documentation`
