---
processed: true
processed_date: 2025-12-09
themes:
  - backend
  - data-model
  - idempotency
modules:
  - backend
code_verified: true
dead_docs_found: false
---
# Idempotent Canonical Cell Generation

## Overview

This document explains the idempotent canonical cell generation feature implemented in the ScareVerse system. This feature ensures that calling the cell generation function multiple times does not create duplicate canonical cell type files.

## What is Idempotence?

In the context of canonical cell generation, **idempotence** means that calling the generation function multiple times with the same parameters produces the same result as calling it once. Specifically:

- First call: Creates 5 canonical cell types
- Second call: Returns the same 5 canonical cell types (no new files created)
- Nth call: Still returns the same 5 canonical cell types

## Why Idempotence Matters

### Before Idempotence

Without idempotence, each call to `seed_tipos_celula()` would:
- Generate new UUIDs for each cell type
- Create new JSON files with duplicate content
- Cause confusion about which cell type to reference
- Make tracking and management difficult

Example: After 8 calls, you'd have 40 files (8 × 5 unique types) with identical content but different UUIDs.

### After Idempotence

With idempotence, multiple calls:
- Check for existing cell types before creating new ones
- Reuse existing cell types when they match
- Only create new cell types when they don't exist
- Maintain referential integrity across the system

## How It Works

### 1. Content-Based Lookup

The `find_by_fields()` method in `JSONDatabase` searches for existing canonical cells by comparing:

```python
search_fields = {
    "descricao": "Editor de Artefatos",
    "scripts": {"python": "...", "js": "..."},
    "markup": "<div>...</div>",
    "views": ["editor", "preview"],
    "workflows": "# Workflow...",
    "versao": "1.0.0"
}
```

If a cell with all matching fields exists, it's returned. Otherwise, a new cell is created.

### 2. Seed Function Logic

The updated `seed_tipos_celula()` function:

```python
def seed_tipos_celula():
    # Define cell specifications
    tipos_celula_specs = [...]
    
    tipos_celula_criados = []
    
    for spec in tipos_celula_specs:
        # Build search criteria (all fields except 'id')
        search_fields = {...}
        
        # Check if cell already exists
        existing_tipo = db.find_by_fields(
            "tipos_celula",
            search_fields,
            TipoCelula,
            is_canonical=True
        )
        
        if existing_tipo:
            # Return existing cell
            logger.info(f"Cell already exists: {existing_tipo.id}")
            tipos_celula_criados.append(existing_tipo)
        else:
            # Create new cell
            tipo = TipoCelula(**spec)
            db.insert("tipos_celula", tipo, is_canonical=True)
            logger.info(f"Cell created: {tipo.id}")
            tipos_celula_criados.append(tipo)
    
    return tipos_celula_criados
```

## Usage

### Basic Usage

```python
from app.seed_data import seed_tipos_celula

# First call - creates cells if they don't exist
tipos = seed_tipos_celula()
# Returns 5 cell types

# Second call - finds existing cells
tipos = seed_tipos_celula()
# Returns the same 5 cell types (no new files created)
```

### Via API Endpoint

The seed endpoint is also idempotent:

```bash
# First call
curl -X POST http://localhost:8000/seed

# Second call - safe to call again
curl -X POST http://localhost:8000/seed
```

Both calls will result in the same 5 canonical cell types.

## Testing

Comprehensive tests validate the idempotent behavior:

### Test Suite

Located in `backend/tests/test_idempotent_cell_generation.py`:

1. **test_seed_tipos_celula_is_idempotent**
   - Calls seed function 3 times
   - Verifies only 5 files exist after each call
   - Confirms same IDs returned on each call

2. **test_seed_tipos_celula_returns_correct_cell_types**
   - Verifies correct number of cell types
   - Checks for expected descriptions
   - Ensures uniqueness

3. **test_find_by_fields_method**
   - Tests the underlying search functionality
   - Verifies correct matching behavior
   - Tests non-matching scenarios

4. **test_no_duplicate_content_after_multiple_seeds**
   - Runs seed multiple times
   - Verifies no duplicate content exists
   - Uses content hashing to detect duplicates

### Running Tests

```bash
cd backend
python -m pytest tests/test_idempotent_cell_generation.py -v
```

All tests should pass, confirming idempotent behavior.

## Benefits

### 1. Consistency

- Same cell types across all environments
- Predictable UUIDs for references
- No confusion about which cell to use

### 2. Safety

- Multiple deployments won't create duplicates
- Seed operations can be run repeatedly
- No data pollution

### 3. Traceability

- Clear lineage of canonical cells
- Easy to track references
- Simplified debugging

### 4. Efficiency

- No unnecessary file creation
- Reduced storage usage
- Faster seed operations (after first run)

## Migration from Non-Idempotent Version

If you have an existing installation with duplicate canonical cells:

1. **Backup your data** (optional but recommended)
2. **Run the cleanup script** to remove duplicates
3. **Verify** that only 5 canonical cell files remain
4. **Test** that the seed function is now idempotent

See [CANONICAL_CELL_CLEANUP.md](./CANONICAL_CELL_CLEANUP.md) for detailed migration instructions.

## API Reference

### JSONDatabase.find_by_fields()

```python
def find_by_fields(
    self,
    collection: str,
    fields: Dict[str, Any],
    model_class: Type[T],
    is_canonical: bool = False
) -> Optional[T]
```

**Parameters:**
- `collection`: Collection name (e.g., "tipos_celula")
- `fields`: Dictionary of field names and values to match
- `model_class`: Pydantic model class to deserialize into
- `is_canonical`: Whether to search canonical artifacts

**Returns:**
- First matching document or `None` if not found

**Example:**

```python
from app.database import db
from app.models import TipoCelula

search_fields = {
    "descricao": "Editor de Artefatos",
    "versao": "1.0.0"
}

tipo = db.find_by_fields(
    "tipos_celula",
    search_fields,
    TipoCelula,
    is_canonical=True
)

if tipo:
    print(f"Found: {tipo.id}")
else:
    print("Not found")
```

### seed_tipos_celula()

```python
def seed_tipos_celula() -> List[TipoCelula]
```

**Returns:**
- List of `TipoCelula` instances (existing or newly created)

**Behavior:**
- Checks for existing cell types before creating
- Returns existing cells if found
- Creates new cells only when needed
- Logs operations for traceability

**Example:**

```python
from app.seed_data import seed_tipos_celula

tipos = seed_tipos_celula()
print(f"Available cell types: {len(tipos)}")

for tipo in tipos:
    print(f"- {tipo.descricao}: {tipo.id}")
```

## Best Practices

### 1. Always Use Seed Function

Don't create canonical cell types manually. Always use `seed_tipos_celula()`:

```python
# ✅ Good
from app.seed_data import seed_tipos_celula
tipos = seed_tipos_celula()

# ❌ Bad
from app.models import TipoCelula
tipo = TipoCelula(descricao="...")
db.insert("tipos_celula", tipo, is_canonical=True)
```

### 2. Call Seed Early

Call the seed function during application startup or initialization:

```python
# In main.py or startup script
from app.scripts.seed_data import init_seed_data

@app.on_event("startup")
async def startup_event():
    init_seed_data()  # Includes seed_tipos_celula()
```

### 3. Monitor for Duplicates

Periodically check for duplicates using the cleanup script:

```bash
cd backend
python scripts/cleanup_duplicate_cells.py --dry-run
```

### 4. Test Before Deployment

Always run the idempotent tests before deploying:

```bash
cd backend
python -m pytest tests/test_idempotent_cell_generation.py
```

## Troubleshooting

### Issue: Duplicates Still Created

**Symptoms:** Multiple files with same content but different IDs

**Possible Causes:**
1. Not using the updated seed function
2. Direct insertion without checking
3. Concurrent execution race conditions

**Solutions:**
1. Ensure you're using the latest version of `seed_data.py`
2. Always call `seed_tipos_celula()` instead of direct insertion
3. Use application-level locking for concurrent scenarios

### Issue: Seed Function Slow

**Symptoms:** `seed_tipos_celula()` takes several seconds

**Cause:** The function searches all existing cells for each cell type

**Solutions:**
1. This is expected behavior after the first run
2. Subsequent runs return existing cells quickly
3. Consider caching if performance is critical

### Issue: Wrong Cell Returned

**Symptoms:** Seed function returns a cell with unexpected content

**Possible Causes:**
1. Cell type definition changed but existing cell still matches some fields
2. Manual modification of canonical cell files

**Solutions:**
1. If cell content should change, manually delete the old canonical cell file first
2. Avoid manual modification of canonical cells
3. Use version numbers to distinguish between iterations

## Related Files

- `backend/app/database.py` - Database operations including `find_by_fields()`
- `backend/app/seed_data.py` - Seed functions including `seed_tipos_celula()`
- `backend/app/models.py` - Data models including `TipoCelula`
- `backend/tests/test_idempotent_cell_generation.py` - Test suite
- `backend/scripts/cleanup_duplicate_cells.py` - Cleanup utility
- `backend/docs/CANONICAL_CELL_CLEANUP.md` - Cleanup documentation

## See Also

- [CANONICAL_CELL_CLEANUP.md](./CANONICAL_CELL_CLEANUP.md) - Cleanup strategy and migration guide
- [ScareVerse_Project.md](../../ScareVerse_Project.md) - Overall project documentation
