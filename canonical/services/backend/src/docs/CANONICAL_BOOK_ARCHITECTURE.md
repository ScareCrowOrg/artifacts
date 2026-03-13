---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - architecture
  - data-model
  - validation
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Canonical Book Architecture - Technical Documentation

## Overview

This document describes the **Canonical Book** pattern implemented in ScareVerse to protect reference books from direct cell array manipulation, ensuring data integrity and architectural consistency.

## Problem Statement

Previously, the `book-issues-queue-v1` book was treated as both:
1. A **reference** (cells pointed to it via `origemLivroId`)
2. A **container** (cells were added to its `celulas` array)

This dual nature created potential inconsistencies where:
- The book's `celulas` array could become stale or corrupted
- Direct manipulation violated single-source-of-truth principles
- The relationship between cells and books was ambiguous

## Solution: Canonical Book Pattern

A **canonical book** is a reference-only book that acts as an immutable organizational artifact. Cells reference the book, but the book does not maintain a list of cells.

### Key Principles

1. **Canonical books are reference-only**: They exist to be referenced by cells via `origemLivroId`
2. **No direct cell array manipulation**: The `celulas` array must remain empty for canonical books
3. **Query-based association**: To get cells in a canonical book, query cells by `origemLivroId`
4. **Validation enforcement**: Pydantic validators prevent accidental violations

## Implementation

### 1. Model Definition

```python
# backend/app/models.py

class Livro(BaseModel):
    """Modelo de livro (conjunto de células)."""
    id: str = Field(default_factory=generate_uuid)
    name: str = Field(...)
    description: str = Field(...)
    tipo: TipoLivro = Field(...)
    origem: Optional[str] = Field(None)
    intencao: str = Field(...)
    filhos: List[str] = Field(default_factory=list)
    celulas: List[str] = Field(default_factory=list)
    
    # NEW: Canonical book flag
    is_canonical: bool = Field(
        default=False,
        description="Se True, este livro é canônico e seu array de células não pode ser manipulado diretamente"
    )
    
    dataCriacao: datetime = Field(default_factory=datetime.utcnow)
    dataAtualizacao: datetime = Field(default_factory=datetime.utcnow)
    
    @model_validator(mode='after')
    def check_celulas_for_canonical(self) -> 'Livro':
        """
        Valida que livros canônicos não podem ter células manipuladas diretamente.
        
        Livros canônicos devem ser apenas referência - as células devem referenciar
        o livro através do campo origemLivroId, não através do array celulas.
        """
        if self.is_canonical and self.celulas:
            raise ValueError(
                'Livro canônico não pode ter array de células instanciado ou modificado. '
                'Use o campo origemLivroId nas células para referenciar este livro.'
            )
        return self
```

### 2. Seed Data Configuration

```python
# backend/app/seed_data.py

def seed_livros():
    """Seed initial books, marking canonical books."""
    issues_queue_book_id = "book-issues-queue-v1"
    
    # ... existing code ...
    
    issues_queue_book = Livro(
        id=issues_queue_book_id,
        name="issues-queue",
        description="A volatile queue for processing various cells...",
        tipo=TipoLivro.VOLATIL,
        intencao="Track and manage execution demands",
        celulas=[],  # Empty array
        is_canonical=True  # Marked as canonical
    )
    
    db.insert("livros", issues_queue_book, is_canonical=True)
```

### 3. API Protection

```python
# backend/app/livros_router.py

@livros_router.post("/{id_livro}/adicionar_celula", response_model=Livro)
async def adicionar_celula_livro(
    id_livro: str,
    request: AdicionarCelulaLivroRequest,
    current_user: Usuario = Depends(get_current_user_required)
):
    """
    Adicionar uma célula a um livro.
    
    Nota: Livros canônicos não podem ter células adicionadas diretamente.
    Para livros canônicos, use o campo origemLivroId da célula.
    """
    livro = db.find_one("livros", id_livro, Livro)
    
    if not livro:
        raise HTTPException(status_code=404, detail=f"Livro {id_livro} não encontrado")
    
    # Check if book is canonical
    if getattr(livro, 'is_canonical', False):
        raise HTTPException(
            status_code=400,
            detail=f"Livro canônico '{livro.name}' não pode ter células adicionadas diretamente ao array. "
                   f"Use o campo origemLivroId da célula para referenciar este livro."
        )
    
    # ... rest of implementation for non-canonical books
```

## Usage Patterns

### ✅ Correct Pattern: Reference via origemLivroId

```python
# Creating a cell that references the canonical book
cell = Celula(
    id="cell-1",
    assignee_id="agent-1",
    tipoCelulaId="ingestion-issue",
    origemLivroId="book-issues-queue-v1",  # Reference to canonical book
    data={"file_path": "/docs/example.md"}
)

# Save the cell
db.insert("celulas", cell, is_canonical=False)

# Query cells belonging to the canonical book
pending_cells = [
    c for c in db.find_many("celulas", Celula, is_canonical=False)
    if c.origemLivroId == "book-issues-queue-v1" and c.estado == EstadoCelula.PENDENTE
]
```

### ❌ Incorrect Pattern: Direct Array Manipulation

```python
# This will raise a ValidationError
canonical_book = Livro(
    id="book-issues-queue-v1",
    name="issues-queue",
    tipo=TipoLivro.VOLATIL,
    intencao="Queue",
    celulas=["cell-1", "cell-2"],  # ❌ ERROR: Canonical book cannot have cells
    is_canonical=True
)

# This will raise an HTTPException (400)
response = client.post(
    "/livros/book-issues-queue-v1/adicionar_celula",
    json={"celulaId": "cell-1"}
)
# Error: "Livro canônico 'issues-queue' não pode ter células adicionadas..."
```

## Examples from the Codebase

### Orchestrator: Correctly Using origemLivroId

```python
# backend/app/orchestrator.py

class Orchestrator:
    def get_pending_cells(self) -> List[Celula]:
        """
        Get all PENDING cells whose origemLivroId matches the issues-queue book.
        """
        all_cells = db.find_many("celulas", Celula, is_canonical=False)
        
        # Filter by origemLivroId - NOT by book's celulas array
        pending_cells = [
            cell for cell in all_cells
            if cell.origemLivroId == self.issues_queue.id 
            and cell.estado == EstadoCelula.PENDENTE
        ]
        
        return pending_cells
```

### Ingest Script: Creating Cells with Book Reference

```python
# ingest.py

def create_ingestion_cell(file_path: Path, agent_id: str, book_id: str) -> Celula:
    """Create an ingestion-issue cell for a file."""
    cell = Celula(
        id=generate_uuid(),
        assignee_id=agent_id,
        tipoCelulaId="ingestion-issue",
        origemLivroId=book_id,  # Reference to canonical book
        data={
            'file_path': str(file_path.absolute()),
            'file_type': file_path.suffix.lstrip('.').lower(),
        },
        estado='pendente',
    )
    
    # Save cell - do NOT add to book's celulas array
    db.insert("celulas", cell, is_canonical=False)
    
    return cell
```

### Issues Dashboard: Querying Canonical Book Cells

```python
# backend/app/issues_dashboard_router.py

@router.get("/cells", response_model=List[Dict[str, Any]])
async def get_issue_cells():
    """Get all cells in the issues queue."""
    cells = db.find_many("celulas", Celula, is_canonical=False)
    
    # Filter by origemLivroId and type
    filtered_cells = [
        c for c in cells 
        if c.tipoCelulaId == "ingestion-issue" 
        and c.origemLivroId == "book-issues-queue-v1"
    ]
    
    return [cell.model_dump() for cell in filtered_cells]
```

## Testing

Comprehensive tests validate canonical book behavior:

```python
# tests/unit/backend/test_canonical_book_protection.py

def test_canonical_book_cannot_have_cells_in_array():
    """Test that canonical books cannot have cells in their array."""
    with pytest.raises(ValidationError):
        livro = Livro(
            id="book-issues-queue-v1",
            name="issues-queue",
            tipo=TipoLivro.VOLATIL,
            intencao="Queue",
            celulas=["cell-1", "cell-2"],  # Should fail
            is_canonical=True
        )

def test_canonical_book_can_be_created_with_empty_cells():
    """Test that canonical books can be created with empty cell array."""
    livro = Livro(
        id="book-issues-queue-v1",
        name="issues-queue",
        tipo=TipoLivro.VOLATIL,
        intencao="Queue",
        celulas=[],  # Empty is OK
        is_canonical=True
    )
    assert livro.is_canonical is True

def test_non_canonical_book_can_have_cells():
    """Test that non-canonical books can have cells normally."""
    livro = Livro(
        id="regular-book-1",
        name="regular-book",
        tipo=TipoLivro.VOLATIL,
        intencao="Regular purposes",
        celulas=["cell-1", "cell-2"],  # OK for non-canonical
        is_canonical=False
    )
    assert len(livro.celulas) == 2
```

## Migration Guide

### For Existing Code

If you have existing code that manipulates the canonical book's array:

**Before:**
```python
# ❌ Old approach
livro = get_livro('book-issues-queue-v1')
for celula in livro.celulas:
    process_cell(celula)
```

**After:**
```python
# ✅ New approach
cells = get_celulas_by_origem_livro_id('book-issues-queue-v1')
for celula in cells:
    process_cell(celula)

# Implementation
def get_celulas_by_origem_livro_id(book_id: str) -> List[Celula]:
    all_cells = db.find_many("celulas", Celula, is_canonical=False)
    return [c for c in all_cells if c.origemLivroId == book_id]
```

### For New Books

When creating new books, decide if they should be canonical:

```python
# Canonical book (reference-only)
canonical_book = Livro(
    id="book-special-queue-v1",
    name="special-queue",
    tipo=TipoLivro.VOLATIL,
    intencao="Special processing queue",
    is_canonical=True,  # Mark as canonical
    celulas=[]  # Must be empty
)

# Regular book (can have cells array)
regular_book = Livro(
    id="user-notebook-1",
    name="My Notebook",
    tipo=TipoLivro.MESTRE,
    intencao="Personal workspace",
    is_canonical=False,  # Regular book
    celulas=["cell-1", "cell-2"]  # Can have cells
)
```

## Benefits

1. **Data Integrity**: Single source of truth for cell-book relationships
2. **Performance**: No need to maintain bidirectional references
3. **Scalability**: Queries scale better than array updates
4. **Clarity**: Clear architectural pattern for reference vs. container
5. **Safety**: Pydantic validation prevents accidental violations

## Future Considerations

1. **Database Indexing**: Index `origemLivroId` field for query performance
2. **Monitoring**: Add metrics for canonical book query patterns
3. **Documentation**: Keep this doc updated as pattern evolves
4. **Additional Canonical Books**: Apply pattern to other reference-only books

## References

- **Issue**: [#XXX] Garantir Integridade Canônica do Livro `book-issues-queue-v1`
- **Model**: `backend/app/models.py` - `Livro` class
- **Tests**: `tests/unit/backend/test_canonical_book_protection.py`
- **API Router**: `backend/app/livros_router.py`
- **Orchestrator**: `backend/app/orchestrator.py`

## Summary

The Canonical Book pattern provides a clear, validated, and maintainable approach to managing reference-only books in ScareVerse. By enforcing this pattern through Pydantic validation and API protection, we ensure architectural consistency and prevent data integrity issues.
