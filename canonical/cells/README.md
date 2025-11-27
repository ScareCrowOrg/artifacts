# Células - Cell Definitions

Este diretório contém as definições JSON de células (cells) criadas no sistema ScareVerse. Células são unidades de conteúdo estruturado no sistema de notebooks.

(This directory contains JSON definitions for cells created in the ScareVerse system. Cells are structured content units in the notebook system.)

## Índice

### Arquivos
- `3121dff9-988d-4801-bd3e-c14d49495347.json` - Definição de célula individual
- Outros arquivos JSON representando células criadas pelo sistema

### Subdiretórios
Este diretório não possui subdiretórios.

## Visão Geral

Células são as unidades fundamentais de conteúdo no sistema de notebooks do ScareVerse. Cada célula contém:
- **ID único (UUID)**: Identificador universalmente único
- **Tipo**: Tipo de célula conforme definido em `../tipos_celula/`
- **Conteúdo**: Dados da célula (texto, código, markdown, etc.)
- **Metadados**: Informações sobre criação, modificação, tags
- **Fragmentos de Memória**: Versões ou partes do conteúdo

## Estrutura de Célula

### Estrutura JSON Básica

```json
{
  "id": "uuid-v4",
  "cell_type": "tipo_celula_id",
  "content": {
    "main": "conteúdo principal da célula",
    "metadata": {
      "language": "python",
      "tags": ["tag1", "tag2"]
    }
  },
  "memory_fragments": [
    {
      "id": "fragment-uuid",
      "content": "fragmento de conteúdo",
      "timestamp": "ISO-8601",
      "version": 1
    }
  ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "notebook_id": "notebook-uuid"
}
```

## Tipos de Células

As células são baseadas nos tipos definidos em `../tipos_celula/`:
- **Texto (Text)**: Conteúdo textual simples
- **Código (Code)**: Código executável (Python, JavaScript, etc.)
- **Markdown**: Texto formatado em Markdown
- **Imagem (Image)**: Referência ou dados de imagem
- **Output**: Resultado de execução de código

Para detalhes completos sobre tipos de células, consulte [../tipos_celula/README.md](../tipos_celula/README.md).

## Uso

### Criando Células

Células são criadas através do frontend (cockpit-vue) ou API backend:

```python
# Exemplo de criação via API
from backend.app.services.cell_service import create_cell

cell = create_cell(
    cell_type="text",
    content={
        "main": "Exemplo de célula de texto",
        "metadata": {"tags": ["exemplo"]}
    },
    notebook_id="notebook-uuid"
)
```

### Recuperando Células

```python
# Exemplo de recuperação de célula
from backend.app.services.cell_service import get_cell

cell = get_cell(cell_id="uuid-da-celula")
```

### Atualizando Células

```python
# Exemplo de atualização
from backend.app.services.cell_service import update_cell

updated_cell = update_cell(
    cell_id="uuid-da-celula",
    content={"main": "novo conteúdo"}
)
```

## Fragmentos de Memória (Memory Fragments)

Células podem ter múltiplos fragmentos de memória representando:
- Versões anteriores do conteúdo
- Variações do conteúdo
- Sugestões de IA
- Outputs de execução

### Estrutura de Fragmento

```json
{
  "id": "fragment-uuid",
  "content": "conteúdo do fragmento",
  "timestamp": "2025-11-14T10:30:00Z",
  "version": 1,
  "source": "user|ai|execution",
  "metadata": {
    "type": "version|suggestion|output",
    "parent_fragment_id": "uuid-se-aplicavel"
  }
}
```

## Integração com Sistema

### Frontend (Cockpit-Vue)
- Componente: `cockpit-vue/src/components/NotebookCell.vue`
- Visualização e edição de células
- Gerenciamento de fragmentos de memória
- Envio de células para chat IA

### Backend
- Service: `backend/app/services/cell_service.py`
- Validação de células
- Persistência em banco de dados
- Processamento de conteúdo

### Persistência
Células são armazenadas de duas formas:
1. **Banco de Dados**: MongoDB para acesso rápido
2. **Arquivo JSON**: Este diretório para backup e versionamento

## Lifecycle de Células

1. **Criação**: Usuário cria célula no notebook
2. **Edição**: Conteúdo é modificado, gerando novos fragmentos
3. **Execução**: (Se código) célula é executada gerando output
4. **Arquivamento**: Células antigas são mantidas para histórico
5. **Deletação**: Remoção soft ou hard dependendo do caso

## Relacionado

- [../tipos_celula/](../tipos_celula/) - Definições dos tipos de células
- [../../runtime/celulas/](../../runtime/celulas/) - Estado de runtime das células
- [Backend Cell Service](../../../backend/app/services/) - Lógica de negócio
- [Frontend Notebook Components](../../../cockpit-vue/src/components/) - Interface de usuário
- [Notebook Documentation](../../../cockpit-vue/docs/features/notebook-cells.md) - Documentação de uso

## Manutenção e Limpeza

### Backup
- Células são automaticamente salvas neste diretório
- Arquivos JSON servem como backup e auditoria

### Limpeza
- Células órfãs (sem notebook) podem ser removidas
- Fragmentos antigos podem ser arquivados
- Retenção padrão: 90 dias para células deletadas

### Migração
Ao atualizar estrutura de células:
1. Crie script de migração em `backend/scripts/`
2. Aplique transformação em todas as células
3. Valide integridade após migração
4. Mantenha backup antes da migração

## Notas

- IDs de células são UUIDs v4 para garantir unicidade
- Células pertencem a um notebook específico
- Fragmentos de memória mantêm histórico de alterações
- Conteúdo sensível não deve ser commitado ao Git
- Use `.gitignore` para células geradas em testes
