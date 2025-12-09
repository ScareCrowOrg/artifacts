---
processed: true
processed_date: 2025-12-09
themes:
  - architecture
  - artifacts
  - backend
  - data-models
modules:
  - backend
  - architecture
code_verified: true
dead_docs_found: false
---
# Livros - Canonical Books

Este diretório contém as definições canônicas de "livros" no sistema ScareVerse. Livros são coleções organizadas de conhecimento, documentação ou conteúdo estruturado que servem como referência para o sistema.

(This directory contains canonical definitions of "books" in the ScareVerse system. Books are organized collections of knowledge, documentation, or structured content that serve as reference for the system.)

## Índice

### Arquivos
Atualmente, este diretório está vazio e pronto para receber definições de livros.

- `.gitkeep` - Arquivo para manter o diretório no Git (se presente)

### Subdiretórios
Este diretório não possui subdiretórios no momento.

## Visão Geral

Livros no sistema ScareVerse representam coleções de conhecimento que podem ser:
- **Documentação Técnica**: Manuais, guias, referências de API
- **Base de Conhecimento**: Wikis, tutoriais, best practices
- **Conteúdo Curado**: Artigos, papers, recursos educacionais
- **Contexto de Projeto**: Especificações, arquitetura, decisões de design

### Propósito

Livros servem múltiplos propósitos no sistema:
1. **RAG (Retrieval Augmented Generation)**: Fonte de contexto para LLMs
2. **Documentação Estruturada**: Organização hierárquica de conteúdo
3. **Base de Conhecimento**: Referência para agentes e usuários
4. **Treinamento**: Material para fine-tuning de modelos

## Estrutura de Livro

### Estrutura JSON Proposta

```json
{
  "id": "unique-book-id",
  "title": "Book Title",
  "version": "1.0.0",
  "description": "Descrição do livro e seu propósito",
  "authors": ["author1", "author2"],
  "language": "pt-BR",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "metadata": {
    "category": "technical|knowledge-base|tutorial|reference",
    "tags": ["tag1", "tag2"],
    "visibility": "public|private|internal"
  },
  "chapters": [
    {
      "id": "chapter-1",
      "title": "Capítulo 1: Introdução",
      "order": 1,
      "content_type": "markdown|html|json",
      "content_path": "path/to/content.md"
    }
  ],
  "index": {
    "terms": {
      "termo1": ["chapter-1", "chapter-3"],
      "termo2": ["chapter-2"]
    }
  },
  "search_config": {
    "enable_vector_search": true,
    "embedding_model": "mistral",
    "chunk_size": 1000,
    "chunk_overlap": 200
  }
}
```

## Uso

### Criando um Novo Livro

1. **Definir Estrutura**:
```bash
# Criar arquivo JSON do livro
touch livro-{nome}-v{versao}.json
```

2. **Configurar Metadados**:
```json
{
  "id": "scareverse-architecture-guide",
  "title": "Guia de Arquitetura ScareVerse",
  "version": "1.0.0",
  "description": "Documentação completa da arquitetura do ScareVerse",
  "language": "pt-BR",
  "metadata": {
    "category": "technical",
    "tags": ["architecture", "documentation", "reference"]
  }
}
```

3. **Adicionar Capítulos**:
```json
{
  "chapters": [
    {
      "id": "intro",
      "title": "1. Introdução",
      "order": 1,
      "content_type": "markdown",
      "content_path": "docs/architecture/intro.md"
    },
    {
      "id": "backend",
      "title": "2. Backend Architecture",
      "order": 2,
      "content_type": "markdown",
      "content_path": "docs/architecture/backend.md"
    }
  ]
}
```

4. **Ingerir no Sistema RAG**:
```python
# Exemplo de ingestão
from backend.app.services.book_ingestion import ingest_book

result = ingest_book(
    book_path="Artefatos/canonicos/livros/scareverse-architecture-guide.json",
    collection_name="scareverse_docs"
)
```

### Consultando Livros

```python
# Exemplo de consulta
from backend.app.services.rag_service import get_rag_service

rag = get_rag_service()
message, docs, context = rag.get_context(
    user_message="Como funciona a arquitetura backend?",
    collection_names=["scareverse_docs"]
)
```

## Integração com RAG

Livros são fontes primárias de conhecimento para o sistema RAG:

### Processo de Ingestão

1. **Parsing**: JSON do livro é parseado
2. **Chunking**: Conteúdo dos capítulos é dividido em chunks
3. **Embedding**: Chunks são convertidos em vetores
4. **Indexing**: Vetores são indexados no Chroma DB
5. **Metadata**: Informações do livro são mantidas como metadata

### Configuração de Busca

```python
# Buscar por livro específico
results = rag.search_similar(
    query="arquitetura backend",
    collection_names=["scareverse_docs"],
    filter={"book_id": "scareverse-architecture-guide"}
)
```

## Tipos de Livros

### 1. Documentação Técnica
- Manuais de API
- Guias de arquitetura
- Especificações técnicas

### 2. Base de Conhecimento
- Tutoriais e how-tos
- Best practices
- Troubleshooting guides

### 3. Referência de Projeto
- Decisões de design (ADRs)
- Roadmaps
- Release notes

### 4. Material Educacional
- Cursos e tutoriais
- Exercícios práticos
- Estudos de caso

## Versionamento de Livros

Livros seguem SemVer (Semantic Versioning):
- **Major (1.0.0)**: Mudanças estruturais significativas
- **Minor (1.1.0)**: Novos capítulos ou seções
- **Patch (1.0.1)**: Correções e melhorias de conteúdo

### Migração de Versões

Ao atualizar versão de livro:
1. Criar novo arquivo com nova versão
2. Manter versão antiga para compatibilidade
3. Atualizar referências no sistema
4. Re-ingerir conteúdo atualizado no RAG

## Relacionado

- [../tipos_celula/](../tipos_celula/) - Tipos de células que podem referenciar livros
- [../agents/](../agents/) - Agentes que utilizam livros como contexto
- [../workflows/](../workflows/) - Workflows de processamento de livros
- [Backend RAG Service](../../../backend/app/services/rag_service.py) - Serviço de RAG
- [Ingest Script](../../../ingest.py) - Script de ingestão de documentos

## Exemplos

### Livro de Arquitetura

```json
{
  "id": "architecture-guide-v1",
  "title": "ScareVerse Architecture Guide",
  "version": "1.0.0",
  "description": "Comprehensive guide to ScareVerse architecture",
  "chapters": [
    {
      "id": "overview",
      "title": "System Overview",
      "content_path": "docs/architecture/overview.md"
    },
    {
      "id": "backend",
      "title": "Backend Architecture",
      "content_path": "docs/architecture/backend.md"
    },
    {
      "id": "frontend",
      "title": "Frontend Architecture",
      "content_path": "docs/architecture/frontend.md"
    }
  ]
}
```

### Livro de Tutoriais

```json
{
  "id": "getting-started-v1",
  "title": "Getting Started with ScareVerse",
  "version": "1.0.0",
  "description": "Step-by-step tutorials for new users",
  "chapters": [
    {
      "id": "installation",
      "title": "Installation Guide",
      "content_path": "docs/tutorials/installation.md"
    },
    {
      "id": "first-notebook",
      "title": "Creating Your First Notebook",
      "content_path": "docs/tutorials/first-notebook.md"
    }
  ]
}
```

## Notas

- Livros devem ter IDs únicos no sistema
- Conteúdo dos capítulos deve ser armazenado separadamente
- Use caminhos relativos para content_path
- Considere size limits para capítulos individuais (< 500 linhas)
- Metadados são importantes para busca e filtragem eficazes
